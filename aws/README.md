# AWS workstream

Owner branch: `feature/aws`.

Implement S3 input loading, DynamoDB case/inventory persistence, and the `return-detective-actions` Lambda against the shared contracts. The starter creates no cloud resources and deploys no infrastructure.

Suggested action contract:

```json
{
  "case_id": "CASE-001",
  "action_id": "backend-generated-id",
  "stock_id": "SHOE-001:DC-A:AUG-2026",
  "quantity": 10
}
```

The backend reads an approval from trusted storage and verifies the exact action scope. It must reject unapproved actions, prevent repeat execution, atomically check remaining inventory, and return an operation ID. A separate inventory read verifies execution. Approval identity must come from authenticated application context, never a model-supplied field.

Use a small Lambda handler with the built-in AWS SDK where possible; keep statistical analysis in the data tools. Document resource names and permissions in `docs/AWS_SETUP.md`. Ask the mentor to resolve restricted lab permissions rather than adding credentials to source files.
