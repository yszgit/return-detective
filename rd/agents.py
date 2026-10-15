"""Triage -> Investigator -> Response with validated SDK outputs."""
import json
import os
from typing import Literal
from pydantic import BaseModel, Field
from strands import Agent
from strands.hooks import AfterToolCallEvent, BeforeToolCallEvent, HookProvider, HookRegistry, MessageAddedEvent
from strands.models import BedrockModel
from . import store, tools
from .config import model_settings
from .detect import screen

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
            self.emit({"agent": self.agent_name, "type": "assistant_update", "text": text})


# The SDK asks the model for a validated object; no brace-scanning parser.
TRIAGE_PROMPT = TRIAGE_PROMPT.split("End with a JSON object")[0]
INVESTIGATOR_PROMPT = INVESTIGATOR_PROMPT.split("End with a JSON object")[0]
RESPONSE_PROMPT += """
This prototype records SIMULATIONS and approval proposals only. No refund, inventory
hold, email, supplier claim or cloud schedule is actually executed. State that clearly.
Use the supplied case_id. Record the follow-up plan, but do not claim it is scheduled in AWS.
"""

class TriageDecision(BaseModel):
    decision: Literal["INVESTIGATE", "ATTACH_TO_CASE", "WATCH", "ISOLATED"]
    style: str = Field(min_length=1)
    category: str = Field(min_length=1)
    rationale: str = Field(min_length=1)
    case_id: str | None = None

class Hypothesis(BaseModel):
    hypothesis: str
    verdict: Literal["supported", "ruled out", "inconclusive"]
    evidence: str

class InvestigationFinding(BaseModel):
    root_cause_class: str = Field(min_length=1)
    root_cause: str = Field(min_length=1)
    confidence: Literal["Low", "Medium", "High"]
    owner_team: str = Field(min_length=1)
    hypotheses: list[Hypothesis] = Field(min_length=3)
    key_evidence: list[str] = Field(min_length=1)
    customers_charged_fees: int = Field(default=0, ge=0, description="Legacy field: return orders with candidate fees, not unique customers")
    recommended_actions: list[str] = Field(default_factory=list)

def _model():
    region, model_id = model_settings()
    settings = {"region_name": region, "model_id": model_id, "max_tokens": 8000}
    if os.getenv("RD_GUARDRAIL_ID"):
        settings.update(guardrail_id=os.environ["RD_GUARDRAIL_ID"],
                        guardrail_version=os.getenv("RD_GUARDRAIL_VERSION", "DRAFT"))
    return BedrockModel(**settings)

def make_agent(name, prompt, agent_tools, emit):
    return Agent(name=name, model=_model(), system_prompt=prompt, tools=agent_tools,
                 hooks=[TraceHook(name, emit)], callback_handler=None)

def _structured(agent, prompt, schema):
    result = agent(prompt, structured_output_model=schema)
    payload = result.structured_output
    if payload is None:
        raise ValueError("Agent did not return the required structured result")
    return schema.model_validate(payload).model_dump()

def preview_return(return_id, as_of):
    """Deterministic evidence preview: no model call and no case/action mutation."""
    with tools.replay_context(as_of):
        incoming = json.loads(tools.get_return(return_id=int(return_id)))
        if "error" in incoming:
            raise ValueError("Return not found on or before the replay date")
        screens = json.loads(tools.screen_style(style=incoming["style"]))
        candidate = next((item for item in screens if item["level"] == "SIGNAL"), None)
        if candidate is None:
            candidate = next((item for item in screens if item["level"] == "WATCH"), None)
        category = candidate["category"] if candidate else incoming["category"]
        existing = store.find_open_case(incoming["style"], category, as_of)
        decision = ("ATTACH_TO_CASE" if existing else "INVESTIGATE") if candidate and candidate["level"] == "SIGNAL" else (
            "WATCH" if candidate else "ISOLATED")
        return {"mode": "offline_preview", "return": incoming, "screens": screens,
                "triage": {"decision": decision, "style": incoming["style"], "category": category,
                           "rationale": "Rule-based preview of observed evidence; no AI investigation performed."}}

def run_pipeline(return_id, as_of, emit=print):
    """Run one live Bedrock investigation. Prototype runs serialize across replay dates."""
    with tools.replay_context(as_of):
        incoming = json.loads(tools.get_return(return_id=int(return_id)))
        if "error" in incoming:
            raise ValueError("Return not found on or before the replay date")
        emit({"agent": "System", "type": "stage", "text": f"Return #{return_id}; replay date {as_of}"})
        triage_agent = make_agent("Triage Agent", TRIAGE_PROMPT, tools.TRIAGE_TOOLS, emit)
        triage = _structured(triage_agent,
            f"Triage return_id {int(return_id)} as of {as_of}. Its style is {incoming['style']}.", TriageDecision)
        if triage["style"] != incoming["style"]:
            raise ValueError("Triage style does not match the observed return")
        emit({"agent": "Triage Agent", "type": "decision", "data": triage})
        if triage["decision"] in {"ISOLATED", "WATCH"}:
            return {"triage": triage}
        evidence = screen(triage["style"], triage["category"], as_of)
        if evidence["level"] != "SIGNAL":
            raise ValueError("An observed SIGNAL is required before investigation or case attachment")
        existing = store.find_open_case(triage["style"], triage["category"], as_of)
        if existing:
            store.link_returns(existing["case_id"], [return_id])
            triage.update(decision="ATTACH_TO_CASE", case_id=existing["case_id"])
            emit({"agent": "System", "type": "case_linked", "data": {"case_id": existing["case_id"], "return_id": return_id}})
            return {"triage": triage, "case_id": existing["case_id"]}
        if triage["decision"] == "ATTACH_TO_CASE":
            raise ValueError("The proposed existing case could not be found")
        emit({"agent": "System", "type": "stage", "text": "Testing competing explanations"})
        investigator = make_agent("Investigator Agent", INVESTIGATOR_PROMPT, tools.INVESTIGATOR_TOOLS, emit)
        finding = _structured(investigator,
            f"Investigate style {triage['style']}, category {triage['category']}, as of {as_of}. "
            f"Triage rationale: {triage['rationale']}", InvestigationFinding)
        emit({"agent": "Investigator Agent", "type": "decision", "data": finding})
        case = store.open_case(triage["style"], triage["category"], as_of, finding["root_cause"],
                               finding["key_evidence"])
        case_id = case["case_id"]
        store.update_case(case_id, root_cause=finding["root_cause"], confidence=finding["confidence"],
                          owner_team=finding["owner_team"], hypotheses=finding["hypotheses"])
        store.link_returns(case_id, [return_id])
        emit({"agent": "System", "type": "stage", "text": "Recording response proposals and approval requests"})
        response = make_agent("Response Agent", RESPONSE_PROMPT, tools.RESPONSE_TOOLS, emit)
        briefing = str(response(f"Case {case_id}. Style {triage['style']}, category {triage['category']}. "
                               f"Replay date {as_of}. Investigation:\n{json.dumps(finding)}"))
        # Always keep the promised follow-up plan even if the model omits its tool call.
        tools.schedule_verification(case_id=case_id)
        emit({"agent": "Response Agent", "type": "briefing", "text": briefing})
        return {"triage": triage, "finding": finding, "briefing": briefing, "case_id": case_id}
