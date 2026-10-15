# Verification note (iteration 2)

App was not started (the user said not to run it). Streamlit installed locally: 1.66.0.

## Findings addressed
1. Missing verification note: this file.
2. Unused `short`: `render_event` now prints `short` in the thought header ("I TRIAGE") and in the tool expander label. `System` keeps its own name ("System"), so nothing is renamed.
3. Theme keys vs `streamlit>=1.40`: kept as is. `requirements.txt` is out of scope for this task. The HEAD app already uses `width="stretch"` on `st.button`, which needs a newer Streamlit than 1.40, so the floor was already stale before the redesign. Older Streamlit only logs a warning for unknown theme keys, and in that case the injected CSS still applies the full look. Recommendation: raise the floor separately.
4. Gold notice: the Investigator result now uses the `neutral` (grey) left border, as the brief asks for non-verdict notices. The unused `.rd-note.gold` CSS rule is removed. Gold is still used for the Medium-confidence chip.

## Checks run
- `python -m py_compile agent_app\app.py`: exit 0.
- Regex `st\.(metric|error|success|warning|info)\b`: 5 matches, all in a CSS comment (line 134) and the `_notice` docstring (line 201). No calls remain.
- Non-ASCII codepoints in app.py: U+00B7 (·) x15, U+2014 (—) x2, U+2264 (≤) x1, U+2192 (→) x2. All typographic, no emoji.
- Hex colours in app.py + config.toml: #15120F #4A443C #7D7366 #8C1D2F #8E8578 #A8803C #E3DCD2 #FAF8F4 #FFFFFF. No blue; the words blue/navy/cyan match 0 times.
- `git diff --stat`: only agent_app/app.py and agent_app/.streamlit/config.toml changed.
- `def` lines HEAD vs now: all 12 original functions have identical names and signatures. Added helpers: `_esc`, `_notice`, `_label`, `_metric`.
- Import lines: identical to HEAD (`from rd import store, tools`, `from rd.data import rows, lit`).
- Approve/Decline: keys `"ap"+id` / `"rj"+id` and `store.decide_approval(id, True|False, "Demo reviewer")` + `st.rerun()` are unchanged.
- Sliders: cost 10..80 default 30; prevent 10..80 default 40, `format="%d%%"`. Unchanged.
