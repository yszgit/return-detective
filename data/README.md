# Data workflows

The active real-data release is the authorized, pseudonymized official **v2**
snapshot under [cleaned/](cleaned/README.md). Its manifest and quality report define
nine analytical tables covering all six supplied business CSVs.

| Workflow | Location | Entry point |
| --- | --- | --- |
| Default synthetic demo | `data/synthetic/` (ignored) | `python scripts/generate_synthetic_data.py` |
| Supplied official v2 snapshot | `data/cleaned/` (committed) | `python scripts/validate_cleaned_data.py` |
| Rebuild from authorized raw inputs | New private output directory outside Git | `scripts/prepare_official_data.py`; follow the [v2 guide](../docs/OFFICIAL_DATA_V2.md) |
| Cloud historical data | Private S3 + Glue + Athena | `scripts/export_aws_dataset.py` and the [AWS setup guide](../docs/AWS_SETUP.md) |

Select local data with `RD_BACKEND=duckdb` and `RD_DATA_DIR=<chosen-directory>`.
Synthetic generation never writes to the official cleaned release. Keep original
CSV files, HMAC keys, working databases and other private/generated data outside
Git. See [data policy](../docs/DATA_POLICY.md) for the selected release exception.
