# Return Detective

ALDO / BSRM hackathon: observe a return signal, investigate competing explanations, review proposals and compare later evidence.

[中文 GitHub 指南](docs/GITHUB_TEAM_GUIDE_ZH.md) · [协作流程](docs/TEAM_WORKFLOW.md) · [AWS setup](docs/AWS_SETUP.md) · [Data contracts](docs/DATA_CONTRACTS.md) · [Integration notes](docs/INTEGRATION.md)

## One project, one shared package

~~~text
app.py                 Streamlit entry point
run_demo.py            CLI entry point
rd/                    agents, tools, data, detection, store, policy
scripts/               connection check and data preparation
aws/                   cloud resource and deployment work
tests/                 shared-package and UI regression checks
evaluation/            historical exports and methodology
data/                  supplied Parquet dataset and data notes
docs/                  setup and team documentation
examples/legacy_demo/  isolated original synthetic demonstration
~~~

## 本地启动 / Local setup

Use your existing Conda environment. Python 3.11 and 3.12 are the CI targets.

~~~powershell
conda activate aldo-hackthon
python -m pip install -r requirements.txt
python scripts/check_aws.py --data-only
python -m streamlit run app.py
~~~

Run from the repository root. Default backend: local DuckDB, reading `data/`. Configure `RD_DATA_DIR` for an approved alternative directory.

**Preview evidence** runs a deterministic preview without a model call or case mutation. **Run AI investigation** uses Bedrock and requires your own valid AWS credentials, region and model ID.

## Command-line preview

~~~sh
python run_demo.py isolated --offline
python run_demo.py quality --offline
python run_demo.py fit --offline
~~~

Remove `--offline` to use Bedrock. Custom records require both `--return-id` and `--as-of`. Local cases persist; `--reset-cases` explicitly clears the local store.

## AWS configuration

Copy `.env.example` to your local `.env`. Set `AWS_REGION` and `RD_MODEL_ID`. For Athena also set `RD_BACKEND=athena`, `RD_ATHENA_DB`, `RD_ATHENA_WORKGROUP` and, unless provided by the workgroup, `RD_ATHENA_OUTPUT`.

Use your own Workshop credentials, including the temporary session token. Then run `python scripts/check_aws.py`. It verifies identity, reads the configured backend and makes one small Bedrock call. See [AWS setup](docs/AWS_SETUP.md).

## Checks

~~~sh
python -m pip check
python -m unittest discover -s tests -v
~~~

CI installs dependencies and checks the shared package, replay dates, structured hand-offs, approvals, Athena adapter and Streamlit UI. Model/AWS calls are mocked. The supplied scenarios and original synthetic example are also checked.

## Prototype boundaries

- Retail actions are **simulations**. Approval does not prove that money, inventory or external messages changed.
- Follow-up dates are local plans, with manual evidence comparison; no cloud scheduler is deployed.
- JSON storage supports one application process. Runs serialize across replay dates. Shared persistence and authenticated approvers remain cloud work.
- Sales aggregates lack dated order cohorts; sales-cohort return rates are unavailable.
- Historical backtest exports used the earlier full-period baseline. Recompute them before presenting current performance or savings.
- Supplied data provenance and fee-grain limits are documented in [data notes](data/README.md). The playbook is a team prototype policy.
- Live Bedrock/Athena has not been certified by offline checks.

## Team workflow

Work branches → PR into `develop` → integrated validation → PR into `main`. See [ownership](docs/TEAM_WORKFLOW.md). Keep shared business logic in `rd/`; the old demonstration is under `examples/legacy_demo/`.
