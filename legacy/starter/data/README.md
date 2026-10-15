# Data workstream

Owner branch: `feature/data`. `sample/` contains reproducible synthetic fixtures. Run `python scripts/generate_demo_data.py` to regenerate them.

Use `raw/` and `private/` only for local inputs; both are ignored by Git. Document provenance, time conventions, missing fields, observation windows, and transformations. Agree on schema changes through `docs/DATA_CONTRACTS.md`.
