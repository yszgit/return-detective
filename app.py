"""Team demo UI; all business behavior comes from the shared rd package."""
import datetime as dt
import json
import queue
from concurrent.futures import ThreadPoolExecutor
import streamlit as st
from rd import data, store, tools
from rd.agents import preview_return, run_pipeline
from run_demo import SCENARIOS

def _live_run(return_id, as_of):
    events = queue.Queue()
    latest = st.empty()
    history = []
    with st.status("Running Triage → Investigator → Response", expanded=True) as status:
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(run_pipeline, return_id, as_of, events.put)
            while not future.done() or not events.empty():
                try:
                    event = events.get(timeout=0.15)
                except queue.Empty:
                    continue
                history.append(event)
                label = event.get("text") or event.get("tool") or event["type"]
                latest.write(f"{event['agent']}: {str(label)[:1000]}")
            result = future.result()
        status.update(label="Investigation complete", state="complete", expanded=False)
    return result, history

def main():
    st.set_page_config(page_title="Return Detective", layout="wide")
    st.title("Return Detective")
    st.caption("Detect a return pattern · investigate evidence · review response proposals")
    st.info("Retail actions and approvals are a local simulation. No money, stock, email or cloud schedule is changed.")
    with st.sidebar:
        scenario = st.selectbox("Scenario", list(SCENARIOS), index=1)
        default_id, default_day = SCENARIOS[scenario]
        return_id = st.number_input("Return ID", min_value=1, value=default_id, step=1, key="rid:" + scenario)
        as_of = st.date_input("Replay date", value=dt.date.fromisoformat(default_day), key="day:" + scenario)
        st.caption("Data source: " + ("local Parquet" if data.BACKEND == "duckdb" else "AWS Athena"))
        st.caption("Evidence includes records on or before the replay date.")
    investigation_tab, cases_tab, verification_tab = st.tabs(["Investigation", "Cases and approvals", "Verification"])
    with investigation_tab:
        left, right = st.columns(2)
        if left.button("Preview evidence", width="stretch"):
            try:
                st.session_state["result"] = preview_return(int(return_id), as_of.isoformat())
                st.session_state["trace"] = []
            except Exception as error:
                st.error(f"Evidence could not load ({type(error).__name__}). Check the return/date and data setup.")
        if right.button("Run AI investigation", width="stretch"):
            try:
                result, trace = _live_run(int(return_id), as_of.isoformat())
                st.session_state["result"], st.session_state["trace"] = result, trace
            except Exception as error:
                st.error(f"Investigation could not complete ({type(error).__name__}). See docs/AWS_SETUP.md.")
        result = st.session_state.get("result")
        if result:
            if result.get("mode") == "offline_preview":
                st.caption("Rule-based evidence preview. No AI investigation was performed.")
            st.subheader("Triage decision")
            st.write(result["triage"])
            if "return" in result:
                st.write({key: result["return"].get(key) for key in ["return_id", "style", "category", "return_date", "raw_reason"]})
            if result.get("screens"):
                st.dataframe(result["screens"], hide_index=True, width="stretch")
                st.caption("Category shares are shares of observed returns, not sales-cohort return rates.")
            if result.get("finding"):
                st.subheader("Investigation findings")
                st.write(result["finding"])
            if result.get("briefing"):
                st.subheader("Response briefing")
                st.write(result["briefing"])
        history = st.session_state.get("trace", [])
        if history:
            with st.expander("Agent activity and tool evidence"):
                for index, event in enumerate(history):
                    st.markdown(f"**{index + 1}. {event['agent']} · {event['type']}**")
                    st.write(event.get("data") or event.get("output") or event.get("text") or event.get("input"))
    with cases_tab:
        db = store.snapshot()
        if not db["cases"]:
            st.caption("No cases yet. A live investigation opens a case when evidence supports a signal.")
        else:
            case_id = st.selectbox("Case", list(db["cases"]))
            case = db["cases"][case_id]
            st.write({key: case.get(key) for key in ["case_id", "style", "category", "status", "confidence", "root_cause", "verification_due_date"]})
            st.write("Linked return IDs:", case["linked_return_ids"])
            st.subheader("Approval queue")
            reviewer = st.text_input("Reviewer name (simulation)", value="Demo reviewer")
            acknowledged = st.checkbox("I am reviewing this request in the local simulation.")
            for approval in [item for item in db["approvals"] if item["case_id"] == case_id]:
                with st.expander(f"{approval['action']} · {approval['status']}", expanded=approval["status"] == "PENDING"):
                    st.write({"approver": approval["approver"], "proposal": approval["detail"]})
                    if approval["status"] == "PENDING":
                        a, b = st.columns(2)
                        disabled = not acknowledged or not reviewer.strip()
                        if a.button("Approve proposal", key="approve:" + approval["approval_id"], disabled=disabled):
                            store.decide_approval(approval["approval_id"], True, reviewer.strip())
                            st.rerun()
                        if b.button("Reject proposal", key="reject:" + approval["approval_id"], disabled=disabled):
                            store.decide_approval(approval["approval_id"], False, reviewer.strip())
                            st.rerun()
            st.subheader("Simulation records")
            st.write([item for item in db["actions"] if item["case_id"] == case_id])
    with verification_tab:
        cases = store.snapshot()["cases"]
        if not cases:
            st.caption("Open a case before comparing a later observation window.")
        else:
            case_id = st.selectbox("Case to verify", list(cases), key="verify_case_id")
            case = cases[case_id]
            default_day = case.get("verification_due_date") or case["opened_as_of"]
            verify_day = st.date_input("Verification replay date", value=dt.date.fromisoformat(default_day), key="verify_day:" + case_id)
            st.caption("Follow-up dates are recorded locally. Run this comparison manually; no AWS scheduler is configured.")
            if st.button("Compare observed evidence"):
                try:
                    with tools.replay_context(verify_day.isoformat()):
                        st.session_state["verification"] = json.loads(tools.verify_case(case_id=case_id))
                except Exception as error:
                    st.error(f"Verification could not complete ({type(error).__name__}). Check the data source.")
            if st.session_state.get("verification"):
                st.write(st.session_state["verification"])
                st.caption("A signal change is an observation; this simulation does not establish avoided returns or savings.")

if __name__ == "__main__":
    main()
