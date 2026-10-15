"""Public entry points for the three-agent pipeline.

The original ``from rd.agents import run_pipeline`` and AWS checker imports
continue to work after splitting implementation into role modules.
"""
from .pipeline import run_pipeline
from .triage import TRIAGE_PROMPT, create_triage_agent
from .investigator import INVESTIGATOR_PROMPT, create_investigator_agent
from .response import RESPONSE_PROMPT, create_response_agent
from .shared import (
    FAST_MODEL_ID, GUARDRAIL_ID, GUARDRAIL_VERSION, MODEL_ID, REGION,
    TraceHook, _model, extract_json, make_agent,
)

__all__ = [
    "run_pipeline", "create_triage_agent", "create_investigator_agent", "create_response_agent",
    "TRIAGE_PROMPT", "INVESTIGATOR_PROMPT", "RESPONSE_PROMPT",
    "TraceHook", "_model", "make_agent", "extract_json",
    "MODEL_ID", "FAST_MODEL_ID", "REGION", "GUARDRAIL_ID", "GUARDRAIL_VERSION",
]
