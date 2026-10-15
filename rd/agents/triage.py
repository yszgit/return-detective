"""Triage Agent: its prompt, allowed tools and construction."""
from .. import tools
from .shared import make_agent

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


def create_triage_agent(emit=print):
    """Build the Triage Agent with its role-specific tools."""
    return make_agent("Triage Agent", TRIAGE_PROMPT, tools.TRIAGE_TOOLS, emit, fast=True)
