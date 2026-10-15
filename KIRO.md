# Project context

The active project uses root rd/, app.py, run_demo.py and requirements.txt. Read README.md and docs/INTEGRATION.md first.

- Run commands from the root and share tool/data/store contracts across owners.
- Load configuration through rd/config.py; keep credentials local.
- Bound evidence and company baselines by replay date.
- Use tools.replay_context(as_of) for tool calls outside the pipeline.
- Use SDK structured outputs for Agent hand-offs.
- Exclude customer identity fields from model evidence.
- Label local actions/approvals as simulations; approval is not execution.
- Keep the original example isolated in examples/legacy_demo/.
- Update relevant regression checks and documentation for interface changes.
