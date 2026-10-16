# Return Detective

ALDO / BSRM hackathon prototype: **Triage → Investigator → Response**, with Strands agents on Amazon Bedrock, evidence tools, a written playbook and human approval gates.

The application runs from the repository root. The `new-ui-code` branch adds the three-page [operations workspace](docs/UI_WORKSPACE.md); `agent` retains the preceding interface. See the [current structure](docs/REPOSITORY_STRUCTURE.md) for entry points and responsibilities.

## Quick start: local demo, no AWS

Use Python 3.12. Run from the repository root:

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python scripts/generate_synthetic_data.py
python run_demo.py syn_quality --scripted
python -m streamlit run app.py
```

On Windows PowerShell, create the environment with `python -m venv .venv` and activate it with `.\.venv\Scripts\Activate.ps1`; the remaining `python` commands are the same.

The generator writes deterministic fake records into ignored `data/synthetic/`. The UI starts with daily processing; prepared synthetic scenarios remain in a backup drawer. Select **Scripted baseline (no model)** to exercise tools without Bedrock. Scripted mode calls real local tools in a fixed sequence; it does not demonstrate autonomous model reasoning. Actions update a local JSON demo store, not a connected retail system.

```sh
python run_demo.py syn_isolated --scripted
python run_demo.py syn_fit --scripted
python run_demo.py syn_damage --scripted
```

## Live agents and authorized data

Copy `.env.example` to `.env` for non-secret settings. Set your own Workshop AWS credentials in the terminal and choose an enabled `RD_MODEL_ID`. Local DuckDB data can still be used with Bedrock:

```sh
python run_demo.py syn_quality
```

For the Athena backend and ALDO scenarios (`isolated`, `quality`, `fit`), follow [AWS setup](docs/AWS_SETUP.md). Live runs require your own model access and may incur AWS charges. This branch's offline checks do not establish live AWS connectivity.

To create a private S3 bucket, Glue database, Athena workgroup and three DynamoDB demo tables, use the [storage stack and setup steps](docs/AWS_SETUP.md#create-s3-glue-athena-and-dynamodb-demo-resources). The stack template and synthetic upload script are prepared, but no AWS resources have been created from this checkout. Keep `RD_BACKEND=duckdb` and `RD_STORE_BACKEND=json` until the storage check succeeds.

The complete official **v2** snapshot is included under [`data/cleaned/`](data/cleaned/README.md): all six business CSVs, nine analytical tables, 649,745 return rows and 8,701,520 transaction rows. Customer identifiers are removed and business keys are consistently tokenized. Transaction-level fees, dated orders, quality flags and prior-day history replace the earlier four-table assumptions. To run it locally without AWS:

```sh
python scripts/validate_cleaned_data.py
RD_BACKEND=duckdb RD_DATA_DIR=data/cleaned python run_demo.py quality --scripted
RD_BACKEND=duckdb RD_DATA_DIR=data/cleaned python -m streamlit run app.py
```

See the snapshot README for PowerShell settings and provenance. The application continues to default to synthetic data unless `RD_DATA_DIR` is set explicitly.

[V2 build, acceptance and AWS upload guide](docs/OFFICIAL_DATA_V2.md) · [Data contracts](docs/DATA_CONTRACTS.md). The checked-in 2025 v2 replay uses prior-day baselines and eligible arrivals: 889 signals and a 55.46% persistence proxy, not model accuracy. Missing currency/policy facts, population sales coverage and truth labels remain unavailable.

## Repository layout

```text
app.py                     Streamlit entry point
run_demo.py                CLI entry point, live or --scripted
rd/                        Agent package, tools, detection, data access, local case store
  agents/                  triage.py, investigator.py, response.py
    pipeline.py            Sequential stage coordination
    shared.py              Shared Bedrock configuration, trace hooks and result parsing
    __init__.py            Compatible run_pipeline and model-checker imports
  config.py                .env loading and repository-relative paths
  scenarios.py             Shared CLI/UI scenario definitions
  verification.py          Dated outcome checks, case closing and reopening
  workflow.py              Grouped daily screening, signal dispatch and replay-date guards
  ui.py                    Monitor, case workspace and approvals/follow-up pages
  policy/                  Response playbook and authority matrix
scripts/                   Synthetic data, private data preparation, AWS check
tests/                     Current synthetic pipeline and entry-point checks
evaluation/                Backtest code and documented historical results
data/                      Selected cleaned snapshot; other private/generated tables ignored
docs/                      Architecture, contracts, setup, team workflow and demo guide
aws/                       Cloud integration status
.github/workflows/ci.yml    Offline checks for agent and team branches
```

## Demo interface and model routing

The monochrome interface has three pages: **Returns monitor**, **Case workspace**, and **Approvals & follow-up**. The main entry point processes a historical day with grouped statistics. Technical traces and supporting analyses are secondary drawers. See [workspace behavior and limits](docs/UI_WORKSPACE.md).

The case workspace includes a transparent planning-value calculator and dated
assessment changes. A measured six-case Bedrock/rules comparison is available in
the supporting analysis. See the [final demonstration guide](docs/FINAL_DEMO.md)
for the evidence, rehearsal sequence and remaining evaluation limits.

- RD_MODEL_ID selects the Investigator model.
- RD_FAST_MODEL_ID optionally selects another model for Triage and Response. If unset, they use RD_MODEL_ID too.
- Daily screening makes zero model calls. Selecting an anomaly starts the existing Investigator and Response. Prepared single-return examples retain the Triage → Investigator → Response pipeline.
- An agent may make several model requests while using tools. Historical signal counts are not measured daily model-call counts or costs.
- Cases, actions and approvals use local JSON by default; `RD_STORE_BACKEND=dynamodb` persists the same demo records in the configured DynamoDB store. SNS and real retail execution remain unimplemented.

## Verification

The **Approvals & follow-up** page includes dated checks; **Agent evaluation** remains in the supporting-analysis drawer.
Persistent signals reopen the existing case and feed its previous hypothesis and
new evidence back into the Investigator. See [verification and comparison guide](docs/VERIFICATION_DEMO.md).
The follow-up is triggered from the UI/CLI; it is not a background AWS schedule.

```sh
python -m unittest discover -s tests -v
python -m compileall -q rd app.py run_demo.py scripts tests evaluation
```

Tests generate temporary synthetic and official-schema fixtures without AWS/Bedrock. V2 fee grain, unknowns, IDs, time cutoffs, AWS layout and chronological follow-up have regression coverage. The committed snapshot reproduces the v2 rule replay; see [evaluation notes](evaluation/README.md).

## Data decision

At the user's explicit request, this private branch includes the complete pseudonymized official v2 snapshot, cleaning/validation code, manifest and aggregate replay results. Raw customer identifiers, original business numbers, raw CSVs, HMAC keys, credentials and runtime traces stay outside Git. Details: [data assessment](docs/DATA_POLICY.md), [data contracts](docs/DATA_CONTRACTS.md).

Further reading: [architecture and limitations](docs/ARCHITECTURE.md) · [team workflow](docs/TEAM_WORKFLOW.md) · [verification and agent comparison](docs/VERIFICATION_DEMO.md).
