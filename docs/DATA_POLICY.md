# Should data be committed?

**Recommendation: keep reproducibility in Git; keep real business records in controlled storage.** The repository is private as checked during this reorganization, but Git history is copied to every clone and is a poor distribution mechanism for restricted customer or commercial records.

At the user's subsequent request, this private branch also includes one explicitly selected prepared snapshot in `data/cleaned/`, supplied in `return_detective_starter.zip`. Its `customer_uid` column is removed and order/return-order numbers are consistently tokenized before committing. The original files and tokenization key remain outside the repository. This exception applies only to those four selected files and their manifest; it does not allow raw/private data generally. See [snapshot provenance](../data/cleaned/README.md).

## Decision by data type

| Item | Git decision | Reason / alternative |
| --- | --- | --- |
| Schemas, category normalization, generation/preparation code, fixed seed, scenario IDs | Commit | Enough to recreate and understand the local demo |
| Tiny, visibly synthetic starter CSVs | Retain under `legacy/starter/data/sample/` | Existing fixtures, about 37 KB total, no real customer records |
| Current synthetic Parquet | Generate locally; ignore | Reproducible from one command; avoids binary churn and confusion with real data |
| Raw ALDO CSVs and customer/order-level derived data | Do not add | `prepare_data.py` preserves `customer_uid` in the private return table; tools omit that column, but the stored file is still sensitive |
| Selected pseudonymized prepared snapshot | Include only the four allowlisted files under `data/cleaned/` | Requested by the user for this private branch; direct customer IDs removed and order numbers tokenized; still private business data |
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

The baseline table is computed over the entire input dataset, and `sku_sales` has no sale dates. Those tables are not point-in-time snapshots, so the current backtest is retrospective and has potential future-information leakage. See `evaluation/README.md`. A larger data release would not fix those methodological limits.

Ignore rules prevent accidental untracked additions; they do not remove already committed history. The selected snapshot has exact file exceptions; raw data, other Parquet files, credentials and runtime state stay ignored. No history rewriting or original raw-data upload is part of this change.
