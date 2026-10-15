"""The three Return Detective agents (Strands Agents SDK on Amazon Bedrock) and the pipeline
that chains them: Triage -> Investigator -> Response.

Every model message and tool call is streamed to an `emit(event)` callback so the UI can
show the agents' reasoning live.
"""
import json
import os
import re

from strands import Agent
from strands.hooks import AfterToolCallEvent, BeforeToolCallEvent, HookProvider, HookRegistry, MessageAddedEvent
from strands.models import BedrockModel

from . import tools

MODEL_ID = os.environ.get("RD_MODEL_ID")  # e.g. us.anthropic.claude-sonnet-4-5-20250929-v1:0 ; None = Strands default
REGION = os.environ.get("AWS_REGION", os.environ.get("AWS_DEFAULT_REGION", "us-east-1"))
GUARDRAIL_ID = os.environ.get("RD_GUARDRAIL_ID")            # optional Bedrock Guardrail
GUARDRAIL_VERSION = os.environ.get("RD_GUARDRAIL_VERSION", "DRAFT")

TRIAGE_PROMPT = """You are the Triage Agent of Return Detective, working for ALDO Group's returns operations.
For every new return you decide one thing: is this an isolated case, or an early signal of a systemic problem?

Steps:
1. Call get_return to read the return.
2. Call screen_style for its style. Look at the category of this return first, but also note any other category at SIGNAL.
3. If a category is at SIGNAL, call find_open_case for it.

Decision rules:
- SIGNAL and no open case -> "INVESTIGATE".
- SIGNAL and an open case exists -> "ATTACH_TO_CASE".
- WATCH -> "WATCH" (keep monitoring, no case yet).
- NORMAL -> "ISOLATED" (handle the return normally).
Never treat "Preference" returns (changed mind) as a product problem.

Explain your reasoning in 2-4 short sentences that cite the numbers (count, share vs company baseline, z-score, locations).
End with a JSON object on its own line:
{"decision": "...", "style": "...", "category": "...", "rationale": "..."}"""

INVESTIGATOR_PROMPT = """You are the Investigator Agent of Return Detective at ALDO Group. A statistical screen flagged a
style and return category. Statistics only raise a flag: your job is to find the most likely root cause and how sure we are.

Work like a detective:
1. Read the playbook (read_playbook) for root-cause classes and confidence levels.
2. Generate at least three competing hypotheses, e.g. product quality defect, fit/sizing, expectation gap
   (photo/description), fulfilment error, transit damage, local store handling, normal noise.
3. Test them with the tools: style_reason_mix (is this category abnormal vs the company?), weekly_timeline
   (when did it start, is it growing, has it persisted 3+ weeks?), spread_analysis (one store, one channel or one SKU,
   or widespread?), sample_returns (cite concrete return IDs and raw reasons), sku_return_rate, fee_audit
   (were customers charged a restocking fee for something that was ALDO's fault?).
4. Rule hypotheses in or out with evidence. Say clearly what the data cannot tell us (for example, there are no
   production-lot or supplier fields, so a lot-level cause is inferred from timing and spread, not proven).
5. Assign confidence Low / Medium / High strictly following the playbook definitions.

Write a short case narrative for a merchandiser (5-8 sentences, numbers and return IDs cited).
End with a JSON object on its own line:
{"root_cause_class": "...", "root_cause": "...", "confidence": "Low|Medium|High", "owner_team": "...",
 "hypotheses": [{"hypothesis": "...", "verdict": "supported|ruled out|inconclusive", "evidence": "..."}],
 "key_evidence": ["..."], "customers_charged_fees": 0, "recommended_actions": ["..."]}"""

RESPONSE_PROMPT = """You are the Response Agent of Return Detective at ALDO Group. You receive an investigation result and
act on it strictly within the playbook's action tiers and authority limits.

Steps:
1. Read the playbook (read_playbook).
2. open_case with a one-line summary and the key evidence, then record_findings with the investigator's root cause,
   confidence, owner team and hypotheses.
3. notify_owner_team.
4. Take every action the playbook allows for this root-cause class and confidence, and no more:
   - ALDO-fault categories with confidence Medium or High: waive_restocking_fees.
   - Fit or expectation issues with confidence Medium or High: request_fit_guidance_update with a concrete,
     customer-friendly proposed text.
   - Quality with confidence High: request_stock_hold, draft_supplier_claim (write the claim text with evidence),
     request_proactive_outreach (write the offer).
5. schedule_verification (21 days).
The tools enforce authority: if a tool refuses or turns your action into an approval request, accept it and report it.
Never deny or restrict a customer's return. Never use customer identity.

Finish with a short briefing (4-6 bullet points) for the owner team: what you did automatically, what is waiting for
human approval and from whom, and what you will check at verification."""


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


def _model():
    kw = {"region_name": REGION, "max_tokens": 16000}
    if MODEL_ID:
        kw["model_id"] = MODEL_ID
    if GUARDRAIL_ID:
        kw.update(guardrail_id=GUARDRAIL_ID, guardrail_version=GUARDRAIL_VERSION, guardrail_trace="enabled")
    return BedrockModel(**kw)


def make_agent(name, prompt, agent_tools, emit):
    return Agent(name=name, model=_model(), system_prompt=prompt, tools=agent_tools,
                 hooks=[TraceHook(name, emit)], callback_handler=None)


def extract_json(text):
    """Return the last top-level JSON object in the text."""
    for m in reversed(list(re.finditer(r"\{", text))):
        depth, start = 0, m.start()
        for i in range(start, len(text)):
            depth += text[i] == "{"
            depth -= text[i] == "}"
            if depth == 0:
                try:
                    return json.loads(text[start:i + 1])
                except json.JSONDecodeError:
                    break
    return {}


def run_pipeline(return_id, as_of, emit=print):
    """Run Triage, then (if needed) Investigator and Response, for one incoming return."""
    tools.AS_OF.set(str(as_of)[:10])
    emit({"agent": "System", "type": "stage", "text": f"New return #{return_id} received on {as_of}"})

    triage = make_agent("Triage Agent", TRIAGE_PROMPT, tools.TRIAGE_TOOLS, emit)
    t_out = str(triage(f"New return_id {return_id} was just created. Today's date is {as_of}. Triage it."))
    t = extract_json(t_out)
    emit({"agent": "Triage Agent", "type": "decision", "data": t})
    if t.get("decision") != "INVESTIGATE":
        return {"triage": t}

    emit({"agent": "System", "type": "stage", "text": "Signal confirmed: opening an investigation"})
    inv = make_agent("Investigator Agent", INVESTIGATOR_PROMPT, tools.INVESTIGATOR_TOOLS, emit)
    i_out = str(inv(f"Today is {as_of}. Investigate style '{t['style']}', category '{t['category']}'. "
                    f"Triage note: {t.get('rationale', '')}"))
    finding = extract_json(i_out)
    emit({"agent": "Investigator Agent", "type": "decision", "data": finding})

    emit({"agent": "System", "type": "stage", "text": "Acting on the findings within the playbook"})
    resp = make_agent("Response Agent", RESPONSE_PROMPT, tools.RESPONSE_TOOLS, emit)
    r_out = str(resp(f"Today is {as_of}. Style '{t['style']}', category '{t['category']}'.\n"
                     f"Investigation result JSON:\n{json.dumps(finding)}\n\nInvestigator narrative:\n{i_out}"))
    emit({"agent": "Response Agent", "type": "briefing", "text": r_out})
    return {"triage": t, "finding": finding, "briefing": r_out}
