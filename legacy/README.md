# Preserved earlier implementations

All earlier code is retained for reference. The supported full application is now at the repository root.

| Path | Purpose |
| --- | --- |
| `starter/` | Original root prototype, standard-library fixtures, simulation, tests and original docs |
| `backtest_original.py` | Earlier machine-specific analysis, including original absolute paths; historical only |
| `agent_app_README.md`, `agent_app.gitignore` | Original nested application's documentation/ignore configuration, preserved for provenance |

Run the early starter in its own directory so its package and fixture paths resolve:

```sh
cd legacy/starter
python -m return_detective.demo
python -m unittest discover -s tests -v
```

The archived documents describe that earlier layout and may mention obsolete paths or planned features. Current instructions are in the root README and `docs/`.
