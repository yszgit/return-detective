# Return Detective

ALDO / BSRM hackathon project: screen unusual return patterns, investigate their evidence with Strands agents on Amazon Bedrock, request a human decision, and revisit the same case when later observations arrive.

**main is the final integrated project.** Start the single application from the repository root with `python -m streamlit run app.py`.

[Team workflow](docs/TEAM_WORKFLOW.md) · [UI guide](docs/UI_WORKSPACE.md) · [AWS setup](docs/AWS_SETUP.md) · [Final demo](docs/FINAL_DEMO.md) · [Architecture](docs/ARCHITECTURE.md)

## Quick start without AWS

Python 3.11 or 3.12 is supported; CI uses 3.12.

Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python scripts/generate_synthetic_data.py
python -m streamlit run app.py
```

macOS / Linux:

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python scripts/generate_synthetic_data.py
python -m streamlit run app.py
```

An existing conda environment can be used instead of creating a venv. If local `.env` or terminal settings already select AWS, explicitly select the local settings below before running. A fresh clone has no `.env`; copy `.env.example` only when creating a new local configuration.

Select **Scripted baseline (no model)** in the UI. Generated fixtures are deterministic, labeled synthetic, and ignored by Git. This mode calls the real local tools in a fixed sequence and does not demonstrate autonomous model reasoning.

## Choose a dataset and case store

For the generated synthetic demo:

```dotenv
RD_BACKEND=duckdb
RD_DATA_DIR=data/synthetic
RD_DATASET_VERSION=1
RD_STORE_BACKEND=json
RD_RUNTIME_DIR=runtime/synthetic-demo
RD_STORE_NAMESPACE=local-synthetic
```

For the included official snapshot:

```dotenv
RD_BACKEND=duckdb
RD_DATA_DIR=data/cleaned
RD_DATASET_VERSION=2
RD_STORE_BACKEND=json
RD_RUNTIME_DIR=runtime/official-demo
RD_STORE_NAMESPACE=local-official
```

These are entries in a local `.env`, without `export`. Terminal values take precedence over `.env`; restart the application after changing configuration.

The authorized pseudonymized v2 snapshot contains nine analytical tables built from all six official sources, including **649,745 return records** and **8,701,520 transaction records**. Validate it with:

```sh
python scripts/validate_cleaned_data.py
```

See [data contracts](docs/DATA_CONTRACTS.md), [snapshot provenance](data/cleaned/README.md), and the [data policy](docs/DATA_POLICY.md). Customer identifiers and original business keys are removed or tokenized; raw sources and the HMAC key are outside Git. The supplied snapshot remains restricted to this private repository and authorized team storage.

## Three-page workflow

1. **Returns monitor**: choose a historical date and process its returns. Grouped SQL makes zero model calls. Flagged return records are grouped into style/category investigation tasks.
2. **Case workspace**: inspect the original signal, dated evidence, competing explanations, tool calls, owner and proposed actions. Open **Review pending proposals** for this case.
3. **Approvals & follow-up**: record a named demo decision, save a future manual review plan, or expand **Historical follow-up replay** to inspect later historical observations.

The left sidebar's **Delete / restore cases** button opens scoped backup, deletion and restoration controls. Cases are preserved across runs. Historical operations move forward within a workspace so later case knowledge cannot leak into an earlier replay.

A future calendar review plan saves date, time, time zone and an optional contact note. In Live mode, explicitly enable **Email reminder to confirmed SNS subscribers** to create a durable AWS EventBridge Scheduler task. The contact field does not route mail. A plan without this option remains manual; no plan schedules an Agent run. See [reminder setup](aws/REVIEW_REMINDERS.md).

## Live AWS configuration

Use the actual Workshop region, permitted model/profile ID and authorized resources. [AWS setup](docs/AWS_SETUP.md) covers Athena over private S3/Glue and JSON or DynamoDB case storage. A single PK/SK DynamoDB table is supported through `RD_STATE_TABLE`; see the [single-table guide](docs/DYNAMODB_SINGLE_TABLE.md).

- `RD_MODEL_ID`: Investigator model; also the fallback for the other roles.
- `RD_FAST_MODEL_ID`: optional alternative for Triage and Response.
- `RD_BACKEND=athena`, `RD_DATASET_VERSION=2`: query the nine-table official dataset.
- `RD_STORE_BACKEND=dynamodb`, `RD_STORE_NAMESPACE=<unique-demo-name>`: persist one isolated demo workspace.
- `RD_SNS_TOPIC_ARN`: optional Standard SNS topic for immediate internal alerts after new live UI investigations; [setup and delivery semantics](aws/SNS.md).
- `RD_SCHEDULER_ROLE_ARN`: optional exact-topic publisher role for future review emails. `RD_SCHEDULER_GROUP` defaults to `return-detective-reviews`.

Checks:

```sh
python scripts/check_storage.py
python scripts/check_aws.py
python scripts/check_aws.py --model-only
```

The first two commands do not invoke a model. Athena queries can incur query usage. `--model-only` explicitly makes a Bedrock check; `--allow-model-call` includes a model check alongside identity/Athena. Never paste credentials into Git, screenshots or chat. Keep local `.env`, profiles, keys and runtime files private.

The repository contains an optional [storage template](aws/return-detective.yaml), four-table synthetic uploader and nine-table [v2 exporter](docs/OFFICIAL_DATA_V2.md). They are not automatic deployment steps. Reuse the team's existing authorized resources rather than creating duplicates.

## CLI and independent replays

```sh
python run_demo.py syn_quality --scripted
python run_demo.py syn_quality --scripted
python run_demo.py --verify-case CASE-ID --as-of YYYY-MM-DD --scripted
```

The repeated signal attaches to its existing case. CLI runs preserve cases by default and share the UI's historical date guards. `--keep-cases` remains accepted for compatibility.

For an intentionally independent replay, use a separate runtime/namespace, or explicitly back up and clear the current populated workspace:

```sh
python run_demo.py syn_isolated --scripted --reset-cases
```

Named ALDO scenarios use dates from the supplied snapshot: `fit` (2024-09-01), `isolated` (2024-10-22), `quality` (2024-11-23). Use separate workspaces or an explicit reset when running them out of order. CLI runs do not publish the UI's SNS case alerts.

## Verification and evidence

```sh
python -m unittest discover -s tests -v
python -m compileall -q rd app.py run_demo.py scripts tests evaluation
python scripts/validate_cleaned_data.py
```

CI runs isolated offline tests and all seven prepared official/synthetic scenarios. It does not invoke Bedrock or SNS. [Evaluation notes](evaluation/README.md) describe the fixed-rule replay and six-case paired synthetic acceptance results.

The supplied 2025 v2 replay has 889 statistical signals and a 55.46% persistence proxy. These are not confirmed root-cause accuracy or incremental LLM value. The value calculator uses explicit planning assumptions rather than realized savings.

## Project boundaries

- Daily screening is statistical; selected cases use Investigator → Response. Prepared single-return examples retain Triage → Investigator → Response.
- Date-bounded evidence and prior-day baselines exclude future observations. Undated fees, final statuses and flags do not authorize historical financial decisions.
- Approval gates are enforced in code. Reviewer names are demo audit labels; approvals, refunds, stock holds, supplier claims and outreach are simulated retail records.
- Optional SNS publishing is real when configured. SNS acceptance does not prove inbox delivery.
- Physical root causes need independent evidence. Partial sales coverage does not establish a population return rate.
- JSON/DynamoDB persistence is a single-process demo store, without transactional multi-user updates or authenticated approvals. Optional email reminders run in AWS; historical Agent follow-ups remain manually triggered.

[Repository structure](docs/REPOSITORY_STRUCTURE.md) · [Verification loop](docs/VERIFICATION_DEMO.md) · [Release review](docs/RELEASE_REVIEW.md)
