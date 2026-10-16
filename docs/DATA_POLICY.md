# Should data be committed?

**Recommendation: keep reproducibility in Git; keep real business records in controlled storage.** The repository is private as checked during this reorganization, but Git history is copied to every clone and is a poor distribution mechanism for restricted customer or commercial records.

At the user's explicit subsequent request to completely clean the official dataset and push it to GitHub, this private branch includes the complete **v2 pseudonymized analytical release** in `data/cleaned/`. This expands the former four-file exception to nine v2 tables, monthly transaction shards, manifest and quality report. Customer/profile identifiers and postal codes are removed; order/return/transaction numbers are consistently tokenized. Raw CSVs, the raw working DuckDB database and the key remain outside Git. See [current release](../data/cleaned/README.md) and [v1 provenance](ALDO_V1_PROVENANCE.md).

## Decision by data type

| Item | Git decision | Reason / alternative |
| --- | --- | --- |
| Schemas, category normalization, generation/preparation code, fixed seed, scenario IDs | Commit | Enough to recreate and understand the local demo |
| Current synthetic Parquet | Generate locally; ignore | Reproducible from one command; avoids binary churn and confusion with real data |
| Raw ALDO CSVs and customer/order-level derived data | Do not add | Use the v2 builder's privacy transformations; raw identifiers and working databases stay outside Git |
| Complete official v2 snapshot | Include explicitly allowlisted v2 tables/shards and metadata under `data/cleaned/` | User-requested private release; identifiers removed/tokenized; still private commercial data |
| Other real prepared Parquet / DuckDB databases | Do not add by default | Use private S3 with team access or ignored `data/private/` |
| Existing `evaluation/results/cases_backtest.csv` | Retain with a provenance note | Already tracked; 1,391 style/category aggregate rows, no customer/order/return identifiers; still contains commercially sensitive style-level results |
| New evaluation outputs | Write to ignored `runtime/evaluation/` first | Review provenance, sensitivity and claims before selecting an aggregate artifact to commit |
| Runtime cases and model traces | Ignore | They can contain return IDs, case evidence and commercially sensitive tool results |
| AWS credentials, `.env`, keys | Never commit | Use each member's temporary competition credentials; `.env.example` contains configuration fields only |
| Organizer PDF | Keep outside the source repository | Reference material, unnecessary for running the code |

## Relevance of the final instructions

The supplied *Hackathon Final Instructions* asks for at least one end-to-end working prototype scenario, visible decisions/actions, a quantified or estimated business impact, and attention to privacy, fairness, financial authority and human oversight. The supplied document does **not** require uploading raw data or publishing the dataset in GitHub, and does not establish permission to redistribute ALDO data.

Therefore a reproducible synthetic demo plus authorized access to real data is enough for repository setup. Whether real-data results may be shared with judges or beyond the team still depends on the organizer/data owner's separate permissions. This is an engineering distribution recommendation, not a finding about an unseen license or agreement.

## Limits of the existing evaluation

The historical CSV was copied unchanged from `feature/agent`. A prepared, pseudonymized input snapshot is now available in `data/cleaned/`; original raw files and the prior run environment remain outside Git. Historical business claims are not independently validated by adding these tables. Style names, dates and counts make them internal business artifacts even without customer identifiers. Do not present synthetic demo output as validation of these results or as realized savings.

Legacy v1 used a full-history baseline and undated flag-file sales counts. V2 uses eligible return history strictly before the replay day, event triggers and complete follow-up. Supplied orders are dated but incomplete; shipped quantities remain undated snapshot attributes, so population return rates are unavailable. Currency/policy facts and true root-cause labels remain absent. See `evaluation/README.md`.

Ignore rules prevent accidental untracked additions; they do not remove already committed history. The selected snapshot has exact file exceptions; raw data, other Parquet files, credentials and runtime state stay ignored. No history rewriting or original raw-data upload is part of this change.
