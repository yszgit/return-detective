import streamlit as st

from return_detective.agent import investigate
from return_detective.config import SNAPSHOT_DATE
from return_detective.data import evidence, screen
from return_detective.mock_retail import DemoRetail

st.set_page_config(page_title="Return Detective", layout="wide")
st.title("Return Detective")
st.caption("Team starter · synthetic data · snapshot " + SNAPSHOT_DATE)
st.info("Default view: deterministic screening and an in-memory retail simulation. Live Bedrock investigation is a separate action.")

sku = st.selectbox("Product", ["SHOE-001", "SHOE-002", "SHOE-003"])
result = screen(sku)
st.subheader("Evidence")
st.write("Screening status:", result["status"])
st.dataframe(result["cohorts"], hide_index=True, use_container_width=True)
with st.expander("Return records and product reviews"):
    st.dataframe(evidence("returns", sku), hide_index=True)
    st.dataframe(evidence("reviews", sku), hide_index=True)

if st.button("Run live Bedrock investigation"):
    try:
        with st.spinner("Querying evidence with the configured Bedrock model..."):
            st.session_state["investigation:" + sku] = investigate(sku)
    except Exception as error:
        # Do not expose raw provider responses or environment details in the UI.
        st.error(f"Investigation could not complete ({type(error).__name__}). Check AWS setup locally.")
if "investigation:" + sku in st.session_state:
    st.write(st.session_state["investigation:" + sku])

st.subheader("Simulated approval and inventory hold")
st.caption("Local session only. A production approval must authenticate the reviewer in a trusted backend.")
if "retail" not in st.session_state:
    st.session_state.retail = DemoRetail()
retail = st.session_state.retail
stocks = [key for key, row in retail.inventory.items() if row["sku"] == sku]
stock_id = st.selectbox("Stock group", stocks)
st.json(retail.read_inventory(stock_id))
quantity = st.number_input("Pairs to hold", min_value=1, max_value=100, value=10)
if st.button("Create a simulated hold request", disabled=result["status"] != "possible_pattern"):
    try:
        action = retail.propose_hold("DEMO-" + sku, stock_id, int(quantity))
        st.session_state["action:" + sku] = action["action_id"]
    except ValueError as error:
        st.error(str(error))

action_id = st.session_state.get("action:" + sku)
if action_id:
    action = retail.actions[action_id]
    st.json(action)
    if action["status"] == "PENDING_APPROVAL":
        acknowledged = st.checkbox("I am acting as the simulated QA reviewer for this exact request.", key="qa:" + action_id)
        if st.button("Approve and execute in simulation", disabled=not acknowledged):
            try:
                retail.approve(action_id, "SIMULATED-QA-USER")
                retail.execute_hold(action_id)
                st.rerun()
            except (ValueError, PermissionError) as error:
                st.error(str(error))
    elif action["status"] == "EXECUTED":
        st.success("Simulation executed. Independently re-read inventory below.")
        st.json(retail.read_inventory(action["stock_id"]))
        st.caption("This verifies inventory state, not a reduction in future returns.")
