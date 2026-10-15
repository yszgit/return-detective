# Return Detective

ALDO / BSRM hackathon prototype: **Triage → Investigator → Response**, with Strands agents on Amazon Bedrock, evidence tools, a written playbook and human approval gates.

This `agent` branch is organized from `feature/agent` at `f8008f0`. The complete agent implementation now runs from the repository root. The earlier starter is preserved under [`legacy/starter/`](legacy/starter/). See the [migration map](docs/REPOSITORY_STRUCTURE.md).

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

The generator writes deterministic fake records into ignored `data/synthetic/`. The UI offers synthetic scenarios and defaults to **Scripted (no LLM)** with this dataset. Scripted mode calls real local tools in a fixed sequence; it does not demonstrate autonomous model reasoning. Actions update a local JSON demo store, not a connected retail system.

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
  policy/                  Response playbook and authority matrix
scripts/                   Synthetic data, private data preparation, AWS check
tests/                     Current synthetic pipeline and entry-point checks
evaluation/                Backtest code and documented historical results
data/                      Selected cleaned snapshot; other private/generated tables ignored
docs/                      Architecture, contracts, setup, migration and data decision
aws/                       Cloud integration status
legacy/                    Original starter and archived prototype materials
.github/workflows/ci.yml    Offline checks for agent and team branches
```

## Demo interface and model routing

The interface uses a monochrome layout with numbered agent stages, styled case/approval cards and business-impact charts. The sidebar shows the selected data backend and each model assignment.

- RD_MODEL_ID selects the Investigator model.
- RD_FAST_MODEL_ID optionally selects another model for Triage and Response. If unset, they use RD_MODEL_ID too.
- The current pipeline starts Triage for the selected return; the statistical screen is a tool called within that stage. Automatic model-free filtering before Triage is future work.
- An agent may make several model requests while using tools. Historical signal counts are not measured daily model-call counts or costs.
- Cases, actions and approvals use local JSON by default; `RD_STORE_BACKEND=dynamodb` persists the same demo records in three deployed tables. SNS and real retail execution remain unimplemented.

## Verification

The UI now includes dated follow-up checks and an **Agent evaluation** tab.
Persistent signals reopen the existing case and feed its previous hypothesis and
new evidence back into the Investigator. See [verification and comparison guide](docs/VERIFICATION_DEMO.md).
The follow-up is triggered from the UI/CLI; it is not a background AWS schedule.

```sh
python -m unittest discover -s tests -v
python -m compileall -q rd app.py run_demo.py scripts tests evaluation legacy
cd legacy/starter
python -m unittest discover -s tests -v
python -m return_detective.demo
```

Tests generate temporary synthetic and official-schema fixtures without AWS/Bedrock. V2 fee grain, unknowns, IDs, time cutoffs, AWS layout and chronological follow-up have regression coverage. The committed snapshot reproduces the v2 rule replay; see [evaluation notes](evaluation/README.md).

## Data decision

At the user's explicit request, this private branch includes the complete pseudonymized official v2 snapshot, cleaning/validation code, manifest and aggregate replay results. Raw customer identifiers, original business numbers, raw CSVs, HMAC keys, credentials and runtime traces stay outside Git. Details: [data assessment](docs/DATA_POLICY.md), [data contracts](docs/DATA_CONTRACTS.md).

Further reading: [architecture and limitations](docs/ARCHITECTURE.md) · [team workflow](docs/TEAM_WORKFLOW.md) · [legacy starter](legacy/README.md).
