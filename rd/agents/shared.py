"""Shared model configuration, trace hooks and result parsing."""
import json
import os
import time

from strands import Agent
from strands.hooks import AfterToolCallEvent, BeforeToolCallEvent, HookProvider, HookRegistry, MessageAddedEvent
from strands.models import BedrockModel

MODEL_ID = os.environ.get("RD_MODEL_ID")
FAST_MODEL_ID = os.environ.get("RD_FAST_MODEL_ID")
REGION = os.environ.get("AWS_REGION", os.environ.get("AWS_DEFAULT_REGION", "us-east-1"))
GUARDRAIL_ID = os.environ.get("RD_GUARDRAIL_ID")
GUARDRAIL_VERSION = os.environ.get("RD_GUARDRAIL_VERSION", "DRAFT")


class TraceHook(HookProvider):
    """Forward the agent's text and tool calls to the UI."""

    def __init__(self, agent_name, emit):
        self.agent_name, self.emit = agent_name, emit

    def register_hooks(self, registry: HookRegistry, **kwargs):
        registry.add_callback(BeforeToolCallEvent, self._before)
        registry.add_callback(AfterToolCallEvent, self._after)
        registry.add_callback(MessageAddedEvent, self._message)

    def _before(self, event):
        tu = event.tool_use
        self.emit({"agent": self.agent_name, "type": "tool_call", "tool": tu.get("name"), "input": tu.get("input")})

    def _after(self, event):
        res = event.result or {}
        text = " ".join(c.get("text", "") for c in res.get("content", []) if isinstance(c, dict))
        self.emit({"agent": self.agent_name, "type": "tool_result", "tool": event.tool_use.get("name"),
                   "status": res.get("status"), "output": text[:4000]})

    def _message(self, event):
        m = event.message
        if m.get("role") != "assistant":
            return
        text = "".join(c.get("text", "") for c in m.get("content", []) if isinstance(c, dict) and "text" in c).strip()
        if text:
            self.emit({"agent": self.agent_name, "type": "thought", "text": text})


def _model(model_id=None):
    # No temperature by default: newer Claude models on Bedrock (e.g. Opus 5.5) always think and
    # reject a custom temperature. Set RD_TEMPERATURE only for models that accept it.
    kw = {"region_name": REGION, "max_tokens": int(os.environ.get("RD_MAX_TOKENS", "16000"))}
    if os.environ.get("RD_TEMPERATURE"):
        kw["temperature"] = float(os.environ["RD_TEMPERATURE"])
    if model_id or MODEL_ID:
        kw["model_id"] = model_id or MODEL_ID
    if GUARDRAIL_ID:
        kw.update(guardrail_id=GUARDRAIL_ID, guardrail_version=GUARDRAIL_VERSION, guardrail_trace="enabled")
    return BedrockModel(**kw)


def make_agent(name, prompt, agent_tools, emit, fast=False):
    return Agent(name=name, model=_model(FAST_MODEL_ID if fast else None), system_prompt=prompt, tools=agent_tools,
                 hooks=[TraceHook(name, emit)], callback_handler=None)


def invoke_agent(agent, prompt, name, emit):
    """Keep measured SDK token/cycle usage; missing telemetry stays unknown."""
    started = time.perf_counter()
    result = agent(prompt)
    metrics = getattr(result, "metrics", None)
    summary = metrics.get_summary() if metrics is not None and hasattr(metrics, "get_summary") else {}
    summary = summary if isinstance(summary, dict) else {}
    usage = summary.get("accumulated_usage") or {}
    emit({"agent": name, "type": "usage", "data": {
        "seconds": round(time.perf_counter() - started, 3),
        "model_cycles": summary.get("total_cycles"),
        "input_tokens": usage.get("inputTokens"), "output_tokens": usage.get("outputTokens"),
        "cache_read_tokens": usage.get("cacheReadInputTokens"),
        "cache_write_tokens": usage.get("cacheWriteInputTokens")}})
    return str(result)


def extract_json(text):
    """Return the last complete JSON object, preserving nested objects and strings."""
    decoder = json.JSONDecoder()
    result, cursor = {}, 0
    while True:
        start = text.find("{", cursor)
        if start == -1:
            return result
        try:
            value, end = decoder.raw_decode(text, start)
        except json.JSONDecodeError:
            cursor = start + 1
        else:
            result, cursor = value, end
