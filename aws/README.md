# AWS integration

Use shared rd/data.py for data access, rd/agents.py for models and the root .env.example. See [setup](../docs/AWS_SETUP.md).

Remaining work: verify real Athena/Glue/S3 and Bedrock access; implement shared storage behind rd/store.py; add authenticated approvers, real executors, receipts, notifications and scheduling.

Local action records simulate operations. GitHub CI does not deploy resources.
