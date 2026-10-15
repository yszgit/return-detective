# bw-retheme verification (static; Streamlit not started)

Files changed: agent_app/app.py, agent_app/.streamlit/config.toml only.

## 1. Compile
`python -m py_compile agent_app\app.py` -> `py_compile exit: 0`

## 2. Hex sweep (case-insensitive)
- app.py hex: ['000000', '333333', '767676', 'BDBDBD', 'E6E6E6', 'F5F5F5', 'FFFFFF'], disallowed: []
- config.toml hex: ['000000', 'E6E6E6', 'F5F5F5', 'FFFFFF'], disallowed: []
- banned (8C1D2F, A8803C, FAF8F4, 15120F, 4A443C, 8E8578, E3DCD2, 7D7366) present: [] in both
- rgb()/hsl(): [] in both; old constant names OXBLOOD/GOLD/IVORY/MUTED/INK: []
- No text colour lighter than #767676 (#BDBDBD/#E6E6E6 used for borders/rules only).

## 3. Fonts
- app.py: Cormorant 0, Inter 0, Jost 21 (Google Fonts @import Jost 300-600)
- config.toml: Cormorant 0, Inter 0, Jost 4 (font + headingFont)

## 4. Banned calls / emoji
- st.metric/error/success/warning/info: [] ; emoji/symbols: []

## 5. git status --short
```
 M agent_app/.streamlit/config.toml
 M agent_app/app.py
?? agent_app/.agents/
```

## 6. Behaviour vs `git show HEAD:agent_app/app.py`
- defs: all 12 HEAD functions present unchanged; 4 extra are the helpers from the previous pass (_esc, _notice, _label, _metric), signatures kept.
- rd imports: identical (2). decide_approval calls: identical (2). session_state keys: identical (3).
- widget keys: all HEAD keys kept; extra `key="rdcard"+approval_id` on the approval container comes from the previous pass (CSS hook).
- Radio/slider calls (incl. mode labels "Live (Bedrock)", "Replay saved live run", "Scripted (no LLM)"): identical. Only label text differences are from the previous pass: emoji removed from "Run" and tab labels, "Reject" -> "Decline".

## config.toml [theme] (TOML parses)
base, primaryColor #000000, backgroundColor #FFFFFF, secondaryBackgroundColor #F5F5F5, textColor #000000,
borderColor #E6E6E6, baseRadius none, buttonRadius none, font/headingFont Jost. [server] headless = true kept.

## Fixes applied in this pass
1. Icon ligatures: no [class*="st-"] font rule; Material Symbols font forced on stIconMaterial / material-symbols / MaterialIcon.
2. Buttons: colour set on button and all children for normal/hover/focus/disabled; primary black/white (hover #333333), secondary white/black border (hover black/white); covers .stButton, .stDownloadButton, .stFormSubmitButton by kind and data-testid.
3. Theme trimmed to the keys above.
4. Contrast: informational labels, sidebar captions (scenario blurb), case-file field labels, table headers, ISOLATED tag, chips, sub-headings at #333333; #767676 only for secondary captions and sidebar widget labels.
5. Tabs: gap 2.5rem, padding 0 0 .7rem 0, margin 0 (data-baseweb and Streamlit 1.66 role=tablist/tab selectors); selected = 1px black underline.
6. Sidebar "Scenario" label removed; radio label "Incoming return" unchanged.
7. Sidebar return line: single "Return" field showing `#{return_id} · {as_of}` (escaped with _esc).

Not verified here: rendered appearance in a browser (orchestrator restarts the server and checks startup).

## Independent re-run (15:32, after the last write to app.py)
- `python -m py_compile app.py` -> exit 0
- Hex tally (both files, upper-cased): #000000 x4, #333333 x2, #767676 x2, #BDBDBD x2, #E6E6E6 x3, #F5F5F5 x3, #FFFFFF x3. Legacy hexes: 0.
- rgb()/hsl()/named colours: 0. (A CSS comment that said "no red" has been reworded to "no accent".)
- Cormorant/Inter: 0. Jost: 25 references.
- st.metric/error/success/warning/info calls: 0. Emoji: 0.
- `git status --short`: ` M agent_app/.streamlit/config.toml`, ` M agent_app/app.py`, `?? agent_app/.agents/`
- vs HEAD: rd imports, decide_approval calls (2), mode strings (8), sliders (2), session_state uses (12) identical. The only defs added are `_esc/_notice/_label/_metric`; the only key added is `rdcard`. The tab labels differ from HEAD only by the emoji removed in the previous pass.
- `tomllib` parses config.toml. Theme keys: backgroundColor, base, baseRadius, borderColor, buttonRadius, font, headingFont, primaryColor, secondaryBackgroundColor, textColor.
- Chart: bars #333333. Rules: "Return Detective flags (5th defect)" solid #000000 (strokeDash [1,0]) and "Monthly report flags (52nd defect)" dashed #767676 ([6,4]). Font Jost, y grid #E6E6E6, no x grid, transparent background.
