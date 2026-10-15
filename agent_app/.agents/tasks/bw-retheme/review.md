# Black-and-white re-theme of the Return Detective Streamlit app

The ivory/oxblood theme becomes a strict monochrome retail look, following the user's "我要這種高級色，黑白". All colour comes from one seven-value palette (#000000, #333333, #767676, #BDBDBD, #E6E6E6, #F5F5F5, #FFFFFF), defined as CSS custom properties and as matching Python constants for the Altair chart. Jost replaces Cormorant Garamond and Inter everywhere. The page gets a black announcement strip, an uppercase wordmark over a hairline rule, square buttons (solid black primary, outlined secondary), and verdict notices that use border weight plus a text tag. Behaviour is unchanged: functions, `rd` imports, widget and session-state keys, mode strings, the Approve/Decline → `store.decide_approval` → `st.rerun()` wiring and the slider ranges all match HEAD.

Watch for: the chart legend shows the two annotation rules as solid black and solid grey strokes, so the dashed/solid difference on the plot doesn't appear in the legend (likely). `chartCategoricalColors` is missing from `config.toml` even though the brief asked for it (confirmed). Main-area section labels use #333333 instead of the #767676 in the brief (confirmed).

**Verdict**: APPROVED

## High-level view

The re-theme is a token swap plus a CSS rewrite in `app.py`, backed by a monochrome `config.toml` (`primaryColor = "#000000"`), so any Streamlit accent the CSS misses (radio dot, slider track, tab highlight) still renders black. Because no colour lives outside those tokens, future palette changes are one-line edits.

The chart has one gap: the strokeDash channel hides its legend, so the legend can only tell the two rules apart by black vs grey, even though the plot draws one solid and one dashed.

`config.toml` was trimmed to base, colours, borders, radii and Jost fonts, and `chartCategoricalColors` went with it. Nothing renders with it today, because the Altair chart sets every colour explicitly, but the brief asked for it.

Label size and tracking match the brief (0.7rem, 0.12em). Label colour doesn't: `.rd-label`, main-area widget labels, case-file field keys, table headers and notice kickers use #333333, and only sidebar widget labels and secondary captions use #767676. The verification note cites contrast, but #767676 on white already meets about 4.5:1.

<details>
<summary>Issues (3)</summary>

1. **Legend omits the dash pattern** (likely, non-blocking): `strokeDash=alt.StrokeDash(..., legend=None)` stops Vega-Lite from merging dash into the colour legend, so the legend shows two solid strokes. Drop `legend=None` and give strokeDash the same `alt.Legend(title=None, orient="top", ...)` as the colour channel so the legends merge and the symbols show solid vs dashed.
2. **`chartCategoricalColors` missing from config.toml** (confirmed, non-blocking): the brief asks for a monochrome categorical palette. Add e.g. `chartCategoricalColors = ["#000000", "#767676", "#BDBDBD", "#333333"]` so a future native chart can't fall back to Streamlit's coloured defaults.
3. **Section label colour deviates from brief** (confirmed, non-blocking): `.rd-label` and main-area labels use #333333 where the brief says #767676. Switch `.rd-label` to `var(--grey)` if the brief should win, or keep #333333 and record the choice.

</details>

<details>
<summary>Details</summary>

### Chart legend loses the dash cue

The rules encode `label` on both `color` (black / #767676) and `strokeDash` (`[1,0]` / `[6,4]`), but the dash channel has `legend=None`:

```python
color=alt.Color("label:N", ..., legend=alt.Legend(title=None, orient="top", ..., symbolType="stroke", symbolStrokeWidth=2)),
strokeDash=alt.StrokeDash("label:N", scale=..., legend=None))
```

Vega-Lite only puts dash on the legend symbols when it merges the strokeDash legend into the colour legend. With that legend suppressed, the symbols are two solid strokes, black and mid-grey (likely; based on Vega-Lite's legend-merge behaviour, not checked in a browser). The text labels are still there, unchanged from HEAD, so "both labelled in the legend" holds. In a black-and-white scheme, though, the dash is the strongest cue for telling the lines apart, and the legend doesn't show it.

</details>

<details>
<summary>File map</summary>

- `agent_app/app.py`: palette constants and `:root` tokens switched to monochrome; CSS rewritten (Jost import, announcement bar, wordmark masthead, tabs, buttons, notices, case card, metrics); Altair chart switched to charcoal bars with black/grey solid/dashed rules and Jost axis/legend config. Functions, keys and `rd` imports unchanged.
- `agent_app/.streamlit/config.toml`: theme set to white/#F5F5F5/black, black primary, #E6E6E6 borders, square radii, Jost fonts.

Full diff: `git -C c:\Users\b0079\Desktop\return-detective diff -- agent_app/app.py agent_app/.streamlit/config.toml`

</details>
