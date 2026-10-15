# Return Detective — ALDO × BSRM Retail Gen AI Hackathon 2026

Every return is a clue. Three agents (Strands Agents SDK on Amazon Bedrock) read each return on the
real ALDO return data, decide whether it is an isolated case or an emerging systemic issue, investigate
the root cause and act within a written authority matrix, with humans approving high-stakes steps.

## Architecture
- **Data**: ALDO CSVs → `scripts/prepare_data.py` → Parquet in **S3** → **Glue/Athena** tables in `aldo_returns`
- **Agents**: `rd/agents.py` — Triage → Investigator → Response, Claude on **Amazon Bedrock**
- **Tools**: `rd/tools.py` — read tools query Athena *as of the replay date* (no peeking at the future);
  action tools enforce the playbook (fee authority CA$500, approval gates) **in code**
- **Policy**: `rd/policy/response_playbook.md` — read by the agents at run time
- **Case store**: `rd/store.py` — JSON for now (swap for DynamoDB)
- **Detection**: `rd/detect.py` — 28-day binomial screen; backtest results in `evaluation/cases_backtest.csv`

## Setup (Windows PowerShell)
```powershell
python -m venv .venv; .venv\Scripts\activate
pip install -r requirements.txt
# paste the 3 lines from Workshop Studio > "Get AWS CLI credentials" (PowerShell version)
$env:AWS_REGION="us-east-1"
$env:RD_BACKEND="athena"
$env:RD_MODEL_ID="<model or inference-profile id from Bedrock console>"
python scripts/check_aws.py
```

## Run the demo scenarios (real data)
```powershell
python run_demo.py isolated   # 2024-10-22: first 'Defective' Glindafied return -> isolated
python run_demo.py quality    # 2024-11-23: Glindafied defect pattern -> case, fee waiver, approvals
python run_demo.py fit        # 2024-09-01: Sperry Wellsloafer_wm runs big -> fit-guidance fix
```
Local fallback without AWS data access: put the Parquet files in `data/` and set `RD_BACKEND=duckdb`.

## Key numbers (reproducible: `RD_BACKEND=duckdb python evaluation/backtest.py`)
- The Triage screen raises **1,391** systemic signals over two years of returns (same thresholds as `rd/detect.py`).
- On the **142 comparable cases** that a monthly report would also catch, the agent flags at the **14th** related
  return (median) vs the **84th** for the report: **59 days earlier**.
- **1,249** signals never reach a monthly-report threshold (too small per month).
- False-alarm proxy (no ground truth exists): **47%** of raw flags are still present 28 days later (quality: 31%).
  This is why statistics only open a case: the Investigator assigns confidence and costly actions need High
  confidence plus human approval.
- Glindafied: flagged 2024-10-28 at the 5th defect return; a monthly report would flag it 2024-12-31 at the 52nd.
- 26-41% of online customers returning for quality, wrong item or transit damage were still charged a restocking fee.

## Demo UI
```powershell
streamlit run app.py
```
Opens in the browser. Pick a scenario, choose **Live (Bedrock)** and press Run. Every live run is saved under
`runtime/traces/`; switch to **Replay saved live run** to show it again instantly during the pitch.
Optional speed-up: `$env:RD_FAST_MODEL_ID="<faster model id>"` runs Triage and Response on a faster model
while the Investigator keeps `RD_MODEL_ID`.

## Synthetic data (local demo, no AWS)

For a fully local demo there is a deterministic **synthetic** data generator. It writes the
four Parquet files the tools expect (`returns`, `sku_sales`, `exchanges`, `baseline`) into
`data/`, labelled SYNTHETIC and containing no customer identifiers. The data is seeded so three
scenarios cross the **unchanged** detection thresholds in `rd/detect.py`:

| Scenario | Style | Category | Screen |
| --- | --- | --- | --- |
| Quality defect | `SYNTH-RiverLoafer` | Quality | SIGNAL |
| Fit (runs big) | `SYNTH-TrailRunner` | Fit: too big | SIGNAL |
| Operational / transit damage | `SYNTH-CoastalBoot` | Damaged in transit | SIGNAL |
| Negative control | `SYNTH-EverydaySneaker` | — | never SIGNAL |

```sh
cd agent_app
python scripts/generate_synthetic_data.py                 # writes data/*.parquet (+ _SYNTHETIC.txt)
RD_BACKEND=duckdb python -m unittest tests.test_synthetic_pipeline -v   # no AWS, no Bedrock
```

Run the full Triage → Investigator → Response pipeline on the synthetic data (needs
`RD_MODEL_ID` and AWS credentials for Bedrock; the data layer stays local via DuckDB):

```sh
RD_BACKEND=duckdb python run_demo.py syn_quality     # Quality defect cluster
RD_BACKEND=duckdb python run_demo.py syn_fit         # runs-big fit issue
RD_BACKEND=duckdb python run_demo.py syn_damage      # transit damage
RD_BACKEND=duckdb python run_demo.py syn_isolated    # single early return, judged isolated
```

The generator and the unit test need no AWS. The existing real-data scenarios
(`isolated`, `quality`, `fit`) and the Athena backend are unchanged.
