# Return Detective

ALDO / BSRM hackathon team workspace: detect a return pattern, investigate evidence, request approval, act through a retail tool, and verify the result.

**Start here:** [Team workflow / 团队协作](docs/TEAM_WORKFLOW.md) · [AWS setup](docs/AWS_SETUP.md) · [Data contracts](docs/DATA_CONTRACTS.md) · [Architecture and delivery status](docs/ARCHITECTURE.md)

## Imported cleaned-data starter

The `feature/data` branch imports the team's supplied `return_detective_starter`: DuckDB data access, statistical screening, agent tool definitions, a local case store, and cleaned Parquet datasets. Read [the import guide and known issues](docs/STARTER_IMPORT.md) before integrating these modules. The existing demo commands below still use the original synthetic fixtures in `data/sample/`.

## Run without AWS

Python 3.12 is the recommended shared development version. Run from the repository root:

```sh
python -m return_detective.demo
python -m unittest discover -s tests -v
```

These commands use only the Python standard library and synthetic fixtures. The demo is a deterministic starter, **not a live AI investigation**.

## Launch the interface

Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m streamlit run app.py
```

macOS / Linux:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m streamlit run app.py
```

The interface starts with local synthetic data and a clearly labeled in-memory inventory simulation. Set your own Workshop credentials, region, and `BEDROCK_MODEL_ID` to use its separate Bedrock investigation button. Live AWS access is not needed for the fixture demo.

## Shared branches

| Branch | Purpose | Main files |
| --- | --- | --- |
| `main` | Stable demo / presentation version | Integrated project |
| `develop` | Team integration | Reviewed changes from work branches |
| `feature/data` | Linked data, validation, cohort analysis | `data/`, `return_detective/data.py`, `scripts/` |
| `feature/agent` | Strands tools, prompts, investigation loop | `return_detective/agent.py`, `prompts/` |
| `feature/aws` | S3, DynamoDB, Lambda, IAM | `aws/`, `return_detective/check_aws.py` |
| `feature/frontend` | Streamlit, evidence display, approvals | `app.py` |
| `feature/evaluation` | Scenarios, baselines, tests, impact assumptions | `tests/`, `evaluation/`, `docs/` |

Work on your branch, open a pull request **into `develop`**, and integrate the verified demo from `develop` into `main`. One person should coordinate changes to shared contracts and dependencies. These are team conventions; remote enforcement depends on the repository's available protection features.

## What's implemented

- Reproducible synthetic orders, returns, reviews, and inventory.
- Sales denominators, a 30-day observation window, an as-of date, and an explicit minimum-evidence screen.
- Local approval / hold / verification simulation with duplicate-execution protection.
- Streamlit starter interface and optional read-only Strands / Bedrock investigation code.
- AWS connection checker, task templates, PR template, and offline CI.

## Team build work

Live AWS connectivity must be verified in the competition account. S3 loading, DynamoDB persistence, Lambda execution, authenticated approvals, model evaluation, and production deployment remain team work. No savings, defect root cause, or deployed AWS capability is claimed by the starter.

The original `data/sample/` fixtures are synthetic. The separate cleaned dataset in `data/*.parquet` was supplied in the team's local starter; its provenance is recorded in the import guide without assuming it is synthetic. Keep temporary AWS credentials and private raw inputs outside Git. Original competition PDFs remain outside this source repository.
