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

The supplied cleaned ALDO snapshot is now included under [`data/cleaned/`](data/cleaned/README.md), with customer identifiers removed and order numbers tokenized. To run the real-data snapshot locally without AWS:

```sh
python scripts/validate_cleaned_data.py
RD_BACKEND=duckdb RD_DATA_DIR=data/cleaned python run_demo.py quality --scripted
RD_BACKEND=duckdb RD_DATA_DIR=data/cleaned python -m streamlit run app.py
```

See the snapshot README for PowerShell settings and provenance. The application continues to default to synthetic data unless `RD_DATA_DIR` is set explicitly.

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

## Verification

```sh
python -m unittest discover -s tests -v
python -m compileall -q rd app.py run_demo.py scripts tests evaluation legacy
cd legacy/starter
python -m unittest discover -s tests -v
python -m return_detective.demo
```

Tests generate temporary synthetic data and do not call AWS or Bedrock. The historical backtest requires the private inputs to reproduce; see [evaluation notes](evaluation/README.md).

## Data decision

Commit **code, schemas, generators, tiny synthetic fixtures and documented aggregate results**. At the user's request, this private branch also includes the explicitly selected, pseudonymized prepared snapshot in `data/cleaned/`. Raw customer identifiers, original order numbers, raw inputs, other generated Parquet, credentials and runtime traces stay outside Git. Sharing commercial data outside the team needs the data owner's permission. Details: [data assessment](docs/DATA_POLICY.md), [data contracts](docs/DATA_CONTRACTS.md).

Further reading: [architecture and limitations](docs/ARCHITECTURE.md) · [team workflow](docs/TEAM_WORKFLOW.md) · [legacy starter](legacy/README.md).
