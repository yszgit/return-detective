"""Smoke test: Athena returns the real data and Bedrock answers. Run before anything else.
   python scripts/check_aws.py"""
import os, sys, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ.setdefault("RD_BACKEND", "athena")
from rd.data import one
t = time.time()
print("Athena returns:", one("select count(*) as n from returns")["n"], f"({time.time()-t:.1f}s)  expected 649745")
print("Glindafied quality returns:", one("select count(*) as n from returns where style='Glindafied' and category='Quality'")["n"], " expected 97")
from strands import Agent
from rd.agents import _model
print("Bedrock says:", str(Agent(model=_model(), callback_handler=None)("Reply with exactly: Bedrock OK")).strip())
