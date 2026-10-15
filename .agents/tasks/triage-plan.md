# Implementation Plan: Triage Agent matches the user spec

Repo root: `c:\Users\b0079\Desktop\return-detective` (Windows, PowerShell). Work directly in the repo. No git commits.
Do not touch `legacy/`, `data/private`, `data/raw`, `data/synthetic`. Do not change any signature or return
JSON shape in `rd/tools.py` (it is not edited at all by this plan).

## Decisions (made after reading the code)

1. Output shape: single object per triage run, or no object when nothing is flagged.
   The pipeline (`rd/agents/pipeline.py`, `rd/offline.py`, `app.py`, `run_demo.py`) runs once per incoming return.
   A return belongs to exactly one style, and the Investigator takes one (style, category), so each run produces at most
   one spec object. When nothing is flagged, Triage emits no spec object: the triage "decision" event has
   `data: None` and a `text` note, and the pipeline result has `"triage": None`. The spec object always has exactly
   these keys, in this order: `sku, severity, return_rate, baseline_rate, units_returned, where, escalate, reason`.
   Routing data the spec does not carry (category, route, open case id) travels in a separate `handoff` dict and
   never appears inside the spec object.

2. Field mapping. These come from the data that actually exists (see the Gaps section):
   - `sku` = the return's `style`. The screen, cases and Investigator all work per style. In this data `sku` is a
     size/colour variant: 82,268 SKUs vs 6,847 styles in data/cleaned. Screening variants would split every signal
     into small-sample noise.
   - `return_rate` = `category_share` from `detect.screen()`. This is the category's share of the style's returns in the
     trailing 28 days (`WINDOW_DAYS`), as a fraction rounded to 3 decimals.
   - `baseline_rate` = `company_baseline_share` from `detect.screen()`, the company-wide share of the category.
   - `units_returned` = `category_returns`, the number of return lines in the window. This is the same count the gates use.
   - `where` = the category's top stores (up to 8, as `"store <id>"`) followed by every channel (as
     `"channel <name>"`), all from the same 28-day window. No region column exists.

3. Gates and severity live in code (KIRO rule 4). The existing thresholds are reused unchanged.
   - Flag levels come from the existing `rd/detect.py` screen, unchanged: `MIN_COUNT[cat]`, `MIN_LIFT[cat]`,
     `MIN_Z = 4.0` → SIGNAL; `k >= max(2, MIN_COUNT//2)` and `lift >= 2` → WATCH.
   - New constants in `rd/detect.py`:
     - `LOW_MIN_Z = 2.0`: a WATCH must also be statistically clear (z ≥ 2, about one-sided p < 0.025) to be flagged
       LOW. This adds the spec's "clearly above baseline" test to the lower tier. WATCH alone has no z gate.
     - `HIGH_MIN_LOCATIONS = 5`: the anomaly is "spreading across stores". This matches the existing `widespread`
       heuristic in `rd/offline.py`, which uses ≥5 stores.
     - `HIGH_COUNT_MULT = 2.0`, `HIGH_LIFT_MULT = 2.0`: a "big" jump or volume is twice the category's own SIGNAL
       gate, so it scales with each category's noise level, which is already encoded in MIN_COUNT/MIN_LIFT.
     - `WHERE_MAX_STORES = 8`, the same top-8 limit as `spread_analysis`.
     - `ESCALATE_SEVERITIES = ("HIGH", "MEDIUM")`.
   - Severity bands (`detect.severity(s, locations)`, a pure function on a `screen()` dict plus the category-level
     distinct location count):
     - HIGH: `level == "SIGNAL"` and `locations >= 5` and (`k >= 2*MIN_COUNT[cat]` or `lift >= 2*MIN_LIFT[cat]`)
     - MEDIUM: any other `level == "SIGNAL"`
     - LOW: `level == "WATCH"` and `z_score >= 2.0`
     - None (not flagged): everything else
   - `escalate = severity in ESCALATE_SEVERITIES`. Because MEDIUM/HIGH ⇔ SIGNAL, the escalation set equals the old
     `INVESTIGATE` set. `evaluation/backtest.py` (which counts first-SIGNAL days with the same constants) therefore
     still matches what Triage escalates, and no backtest code change is needed.
   - `locations` = `count(distinct coalesce(cast(store as varchar), channel))` over the *category's* returns in the
     window. This is the same definition as the screen's `distinct_locations`, but per category instead of style-wide.
   - Expected results (measured during planning; `loc` is the category-level location count):

     | Scenario | Level | k | lift | z | loc | Severity | Escalate |
     |---|---|---|---|---|---|---|---|
     | syn_isolated (940 @ 2026-01-07) | NORMAL | 1 | 10.9 | 3.1 | 1 | not flagged | – |
     | syn_quality (6027 @ 2026-01-31) | SIGNAL | 16 | 21.7 | 18.2 | 11 | HIGH | true |
     | syn_fit (1068 @ 2026-01-31) | SIGNAL | 20 | 8.5 | 12.2 | 6 | HIGH | true |
     | syn_damage (3699 @ 2026-01-31) | SIGNAL | 12 | 41.0 | 21.9 | 2 | MEDIUM | true |
     | isolated (cleaned, 212632 @ 2024-10-22) | NORMAL | 1 | 6.6 | 2.2 | 1 | not flagged | – |
     | quality (cleaned, 243470 @ 2024-11-23) | SIGNAL | 7 | 12.9 | 8.9 | 6 | HIGH | true |
     | fit (cleaned, 165717 @ 2024-09-01) | SIGNAL | 20 | 4.6 | 8.3 | 3 | MEDIUM | true |
     | LOW example: SYNTH-TrailRunner "Fit: too big" @ 2026-01-13 | WATCH | 9 | 8.5 | 8.2 | – | LOW | false |

   - Target category per return. This keeps the existing preference in `offline.py`: rank the flagged categories by
     `(0 if escalates else 1, 0 if category == return's category else 1, severity rank HIGH<MEDIUM<LOW, -z_score)`
     and take the first. "Preference" is not in `WATCHED`, so it is never flagged. This keeps the old rule.

4. The model only writes `reason`. Code computes the assessment before calling the model, puts the authoritative fields
   in the request, and then overwrites every field except `reason` with the code values. The model's reason is
   accepted only if it is a single sentence of 10–300 chars that does not match a root-cause regex. Otherwise a code
   template reason is used. The model is not called when nothing is flagged, which saves a fast-model call.

5. "Log LOW cases": add `store.log_triage(entry)` to `rd/store.py`. It appends to a new top-level `triage_log` list in
   the same `cases.json`. LOW entries are logged, emitted to the trace as a System stage, and never passed to the
   Investigator. No new infrastructure is added. `reset()` and the empty default include `"triage_log": []`. All readers
   use `db.get("triage_log", [])`, so stores and saved traces without the key keep working.

6. Open case: if the result escalates but `store.find_open_case(style, category)` already returns an open case, route
   `ATTACH_TO_CASE`. The pipeline stops without a new investigation, which is the existing pipeline behaviour.
   `offline.py` now does the same, because it previously ignored the lookup. CI resets the store, so no scenario changes.

7. Consumers adapt to the new shape. The UI, CLI and tests read `severity`/`escalate`/`reason` instead of
   `decision`/`rationale`. The UI keeps a legacy branch so old saved live traces (`runtime/traces/*.json`) still render.
   The existing `rd.agents` exports are unchanged. `assess_return` and `TRIAGE_FIELDS` are added.

## Gaps and assumptions (documented in code and docs, not blocking)

- There is no region column, so `where` lists stores and channels only.
- No dated sales denominator exists (`sku_sales` is static; see docs/DATA_CONTRACTS.md). The "return rate" is therefore
  the category share of the style's returns, and the baseline is the static company-wide category share rather than a
  trailing 8-week average.
- The spec describes a daily batch over all SKUs. This prototype triages per incoming return. Model-free batch
  pre-screening is still future work, as README already states.
- Local interpreter is Python 3.14 (CI uses 3.12). The global interpreter lacks `python-dotenv`, so use a `.venv` (step 0).

## Steps

- [ ] 0. Set up a local environment, a medium-risk step. Create `.venv` (gitignored) and install the pinned ranges from
      `requirements.txt` into it. Do not install into the global interpreter. Use `.\.venv\Scripts\python.exe` for every
      later command (written as `python` below).
      Files: none (creates `.venv/`)
      Verify: `python -m venv .venv; .\.venv\Scripts\python.exe -m pip install -r requirements.txt; .\.venv\Scripts\python.exe -m unittest discover -s tests -v` completes. It runs the existing tests unchanged and establishes the baseline. If a pre-existing test fails, record it in the plan notes before changing code.

- [ ] 1. Add severity bands and category spread to `rd/detect.py`.
      Files: `rd/detect.py`, new `tests/test_triage.py`
      - Extend the module docstring with the severity bands and their rationale, as listed in Decision 3.
      - Add constants after `WATCHED`: `LOW_MIN_Z = 2.0`, `HIGH_MIN_LOCATIONS = 5`, `HIGH_COUNT_MULT = 2.0`,
        `HIGH_LIFT_MULT = 2.0`, `WHERE_MAX_STORES = 8`, `ESCALATE_SEVERITIES = ("HIGH", "MEDIUM")`,
        `SEVERITY_RANK = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}`.
      - `def severity(s, locations):` returns "HIGH" | "MEDIUM" | "LOW" | None. It uses `s["level"]`, `s["category"]`,
        `s["category_returns"]`, `s["lift_vs_baseline"]` and `s["z_score"]`, with `MIN_COUNT`/`MIN_LIFT` looked up by
        category, exactly as specified in Decision 3. It runs no SQL.
      - `def escalates(sev): return sev in ESCALATE_SEVERITIES`
      - `def category_spread(style, category, as_of, window_days=WINDOW_DAYS, max_stores=WHERE_MAX_STORES):` runs three
        portable queries using `lit()` and the existing `window_sql()` (no `::`, no DuckDB-only functions, and dates from
        `window_sql`, so data stays ≤ as_of). It reads the `store` and `channel` columns only, so there are no customer
        identifiers. It returns `{"distinct_locations": int, "where": [...]}`:
        ```python
        w = f"style = {lit(style)} and category = {lit(category)} and {window_sql(as_of, window_days)}"
        loc = one(f"select count(distinct coalesce(cast(store as varchar), channel)) as n from returns where {w}")
        stores = rows(f"""select cast(store as varchar) as k, count(*) as n from returns where {w} and store is not null
                          group by cast(store as varchar) order by n desc, k limit {int(max_stores)}""")
        chans = rows(f"""select channel as k, count(*) as n from returns where {w} and channel is not null
                         group by channel order by n desc, k""")
        where = [f"store {x['k']}" for x in stores] + [f"channel {x['k']}" for x in chans]
        ```
        `rows` is already imported lazily inside `style_window_counts`. Import it at module top with
        `from .data import one, rows, lit, dlit, days_before, baseline_share`.
      - Leave `screen`, `screen_all`, `MIN_*` and `WINDOW_DAYS` unchanged, because the backtest imports them.
      - In `tests/test_triage.py`, add `SeverityTests` (pure, no data) built from fake screen dicts for category "Quality"
        (MIN_COUNT 5, MIN_LIFT 4):
        - NORMAL → None
        - WATCH z=1.9 → None
        - WATCH z=2.0 → LOW
        - SIGNAL k=5, lift=4, loc=10 → MEDIUM
        - SIGNAL k=10, lift=4, loc=4 → MEDIUM
        - SIGNAL k=10, lift=4, loc=5 → HIGH
        - SIGNAL k=5, lift=8, loc=5 → HIGH
        - `escalates` is true only for HIGH and MEDIUM, and false for LOW and None.
      Verify: `python -m unittest tests.test_triage -v` passes, and `python -m unittest discover -s tests -v` still passes.

- [ ] 2. Add LOW-case logging to `rd/store.py`.
      Files: `rd/store.py`, `tests/test_triage.py`
      - Add a module constant `_EMPTY = lambda: {"cases": {}, "actions": [], "approvals": [], "triage_log": []}` (or a
        small function). Use it in the `_load()` default and in `reset()`.
      - Add:
        ```python
        def log_triage(entry):
            """Record a triage flag that was logged but not escalated (LOW severity)."""
            with _lock:
                db = _load()
                e = {"log_id": "TRI-" + uuid.uuid4().hex[:6].upper(), "at": _now(), **entry}
                db.setdefault("triage_log", []).append(e)
                _save(db)
                return e
        ```
      - Leave every existing function and JSON key unchanged.
      - Test: `StoreLogTests` patches `store._PATH` and `store.RUNTIME_DIR` to a `tempfile.TemporaryDirectory`. It checks
        that `reset()` then `log_triage({...})` appends exactly one entry, that `cases`, `actions` and `approvals` stay
        empty, and that a pre-existing file without `triage_log` (written via `restore({"cases": {}, "actions": [], "approvals": []})`)
        accepts `log_triage`.
      Verify: `python -m unittest tests.test_triage -v` passes.

- [ ] 3. Rewrite `rd/agents/triage.py`: spec prompt plus deterministic assessment helpers. Depends on steps 1–2.
      Files: `rd/agents/triage.py`, `rd/agents/__init__.py`, `tests/test_triage.py`
      - Add `TRIAGE_FIELDS = ("sku", "severity", "return_rate", "baseline_rate", "units_returned", "where", "escalate", "reason")`.
      - `TRIAGE_PROMPT` = the user spec text verbatim (the block from "You are the Triage Agent for ALDO's Return
        Detective." through the OUTPUT JSON skeleton), followed by a blank line and this deployment section:
        ```
        How this deployment works:
        - Each request is one incoming return. Code has already screened the return's style (the product-level SKU in
          this data) over the last 28 days and computed sku, severity, return_rate (share of the style's returns in the
          flagged return category), baseline_rate (company-wide share of that category), units_returned, where and
          escalate. Those values and the severity/escalation decision are fixed by code: copy them unchanged.
        - You may check the numbers with get_return, screen_style and find_open_case.
        - Your only contribution is "reason": exactly one sentence that describes the anomaly (the return category,
          rate versus baseline, units and how many stores/channels). Never state or hint at a cause: no "because",
          "due to", "likely", "defect", "supplier", "sizing" or similar.
        - "Preference" returns (changed mind) are never a product problem.
        - Reply with the JSON object only.
        ```
      - Keep `create_triage_agent(emit=print)` unchanged (same tools, `fast=True`).
      - Add model-free helpers. Import `json` and `re`, `from .. import store`,
        `from ..data import one`, and `from .. import detect`.
        - `assess_return(return_id, as_of)`:
          - `row = one(f"select style, category from returns where return_id = {int(return_id)}")`. Select only these two
            columns and no customer data. Raise `ValueError(f"return {return_id} not found")` if missing.
          - `scr = detect.screen_all(style, as_of)`.
          - For each row with level != NORMAL: `spread = detect.category_spread(style, cat, as_of)` and
            `sev = detect.severity(s, spread["distinct_locations"])`. Keep the rows where sev is not None.
          - Choose the target with the rank key from Decision 3.
          - If there is no target, return
            `{"flagged": False, "route": "NOT_FLAGGED", "style", "return_id", "as_of", "return_category", "category": None, "result": None, "open_case_id": None, "note": <not_flagged_note>}`.
            The note is one sentence. For a watched category:
            `f"Not flagged: {k} {cat} returns for {style} in the last 28 days ({share:.1%} vs {base:.1%} company baseline) are below the flag thresholds."`.
            Otherwise: `f"Not flagged: '{cat}' returns are not screened as a product signal and no watched category for {style} is above its baseline."`
          - If there is a target, build `result` as a dict in `TRIAGE_FIELDS` order: `sku=style`, `severity=sev`,
            `return_rate=s["category_share"]`, `baseline_rate=s["company_baseline_share"]`,
            `units_returned=int(s["category_returns"])`, `where=spread["where"]`, `escalate=detect.escalates(sev)`,
            `reason=template_reason(...)`.
          - `open_case = store.find_open_case(style, cat) if escalate else None`.
          - `route = "ATTACH_TO_CASE" if open_case else ("INVESTIGATE" if escalate else "LOG")`.
          - Return `{"flagged": True, "route", "style", "category": cat, "return_category", "return_id", "as_of", "screen": s, "distinct_locations": ..., "result": result, "open_case_id": open_case["case_id"] if open_case else None}`.
        - `template_reason(category, style, s, locations)` returns exactly one sentence with no cause:
          `f"{category} returns for {style} reached {s['category_share']:.1%} of its returns in the last {detect.WINDOW_DAYS} days versus a {s['company_baseline_share']:.1%} company baseline ({s['lift_vs_baseline']:g}x, z={s['z_score']:g}), {s['category_returns']} units across {locations} locations."`
        - `ROOT_CAUSE_RE = re.compile(r"\b(because|due to|caus\w*|root|likely|probabl\w*|suggest\w*|indicat\w*|point\w* to|defect\w*|supplier\w*|manufactur\w*|sizing|runs (?:small|big|large)|batch|lot|packag\w*|carrier\w*|courier\w*)\b", re.I)`
        - `clean_reason(text, fallback)`: if not a str → fallback. Collapse whitespace and take the first sentence with
          `re.split(r"(?<=[.!?])\s+", text.strip(), maxsplit=1)[0]`. Append "." if the sentence lacks end punctuation.
          Return fallback if `len < 10`, `len > 300`, or `ROOT_CAUSE_RE.search(sentence)`.
        - `triage_request(a)` builds the user message for the model. It contains the return id, the as_of date, the
          style and the flagged category, `json.dumps({k: v for k, v in a["result"].items() if k != "reason"})` labelled
          as authoritative, and the screen detail (k of n returns, lift, z, locations). It ends with
          `Reply with the JSON object only, adding a one-sentence "reason".`
        - `finalize_result(a, model_text)`:
          `model = extract_json(model_text) if isinstance(model_text, str) else {}`, then
          `out = dict(a["result"]); out["reason"] = clean_reason(model.get("reason"), a["result"]["reason"])`, and
          `return {k: out[k] for k in TRIAGE_FIELDS}`. Import `extract_json` from `.shared`.
        - `handoff(a)` returns `{"route": a["route"], "style": a["style"], "category": a["category"], "case_id": a["open_case_id"]}`.
        - `triage_log_entry(a, result)` returns `{"return_id": a["return_id"], "as_of": a["as_of"], "category": a["category"], "triage": result}`.
      - `rd/agents/__init__.py`: also import and export `assess_return` and `TRIAGE_FIELDS` (add them to `__all__`). Keep
        every existing export.
      - Tests (`TriageHelperTests` in `tests/test_triage.py`, pure, using a hand-built assessment dict):
        - `finalize_result` returns exactly `TRIAGE_FIELDS` in order. Code values override a model JSON that has a wrong
          severity, wrong escalate, wrong numbers and extra keys. A clean model reason is kept, and only its first
          sentence is used when it has two.
        - A reason such as "Returns spiked because of a supplier defect." falls back to the template.
        - Missing or empty reason, or non-JSON model text, falls back to the template.
        - `template_reason` for every category in `detect.WATCHED` (style "SYNTH-RiverLoafer") contains one sentence
          and does not match `ROOT_CAUSE_RE`.
        - `TRIAGE_PROMPT` contains the spec sentences verbatim, for example
          "Escalate only HIGH and MEDIUM cases to the Investigator. Log LOW cases." and
          "Do not guess the root cause. That is the Investigator's job.".
      Verify: `python -m unittest tests.test_triage tests.test_agents -v`. The new tests pass and
      `test_roles_keep_their_tools_models_and_trace_callback` still passes. The old pipeline tests in test_agents are
      replaced in step 4, so they may fail here. If they do, do step 4 immediately before running the full suite.

- [ ] 4. Rewrite the coordinator `rd/agents/pipeline.py` and its tests. Depends on step 3.
      Files: `rd/agents/pipeline.py`, `rd/agents/investigator.py`, `tests/test_agents.py`
      - Imports: `from .. import store, tools` and
        `from .triage import create_triage_agent, assess_return, triage_request, finalize_result, handoff, triage_log_entry`.
        Importing these by name lets tests patch them on the pipeline module.
      - Flow:
        ```python
        tools.AS_OF.set(str(as_of)[:10]); emit(stage "New return #… received on …")
        a = assess_return(return_id, str(as_of)[:10]); h = handoff(a)
        if not a["flagged"]:
            emit({"agent": "Triage Agent", "type": "decision", "data": None, "text": a["note"]})
            return {"triage": None, "handoff": h}
        t = finalize_result(a, str(create_triage_agent(emit)(triage_request(a))))
        emit({"agent": "Triage Agent", "type": "decision", "data": t})
        if not t["escalate"]:
            store.log_triage(triage_log_entry(a, t))
            emit(stage f"{t['severity']} severity: logged for monitoring, not escalated to the Investigator")
            return {"triage": t, "handoff": h}
        if a["route"] == "ATTACH_TO_CASE":
            emit(stage f"Case {h['case_id']} is already open for {h['style']} / {h['category']}: attached, no new investigation")
            return {"triage": t, "handoff": h}
        emit(stage f"{t['severity']} severity: escalating {h['style']} / {h['category']} to the Investigator")
        investigator prompt: f"Today is {as_of}. Investigate style '{h['style']}', category '{h['category']}'. Triage result JSON: {json.dumps(t)}"
        ... Investigator and Response exactly as today, using h['style'] / h['category'] ...
        return {"triage": t, "handoff": h, "finding": finding, "briefing": r_out}
        ```
      - `rd/agents/investigator.py`: add one sentence to `INVESTIGATOR_PROMPT` after the first paragraph: "Triage hands
        you a severity-rated flag (HIGH or MEDIUM) with rate, baseline, units and locations but no cause; treat its
        numbers as the starting point." Change nothing else.
      - `tests/test_agents.py`: replace the two pipeline tests. Keep `test_roles_…` and `test_parser_…` unchanged.
        - Add a helper `fake_assessment(route, severity)`. It returns a dict with `flagged`, `route`, `style="TestStyle"`,
          `category="Quality"`, `return_id`, `as_of`, `open_case_id`, `note`, and `result` (all 8 fields,
          `escalate = severity in ("HIGH","MEDIUM")`, template reason "Quality returns … ."). It also patches
          `self.pipeline.assess_return` with this value and `self.pipeline.store`, and runs `triage_request`/`finalize_result`
          for real.
        - `test_not_flagged_skips_model_and_downstream_agents`: `create_triage_agent`, investigator, response and
          `store.log_triage` are not called. The result is `{"triage": None, "handoff": {...route "NOT_FLAGGED"}}`. The last
          event is a Triage decision with `data is None`, and `AS_OF.set` was called once with "2026-01-31".
        - `test_low_is_logged_not_escalated`: the triage mock returns `json.dumps({..., "reason": "Quality returns rose to 30% versus 2% baseline across 3 locations."})`.
          `store.log_triage` is called once with `{"return_id", "as_of", "category": "Quality", "triage": result["triage"]}`.
          The result's `triage["escalate"] is False` and its severity is "LOW". The investigator and response are not called.
        - `test_open_case_attaches_without_investigation`: route ATTACH_TO_CASE, severity HIGH. The investigator is not
          called and `log_triage` is not called.
        - `test_escalated_case_reaches_investigator_and_response_in_order`: keep the old nested-finding assertions. Call
          order is triage → investigator → response. The investigator prompt contains "TestStyle", "Quality" and the
          triage reason. The response prompt contains `json.dumps(finding)` and the narrative. `result["triage"]` has
          exactly `TRIAGE_FIELDS`, the decision events equal `[result["triage"], finding]`, and a model severity
          "LOW" in the mock output is overridden by the code value "HIGH".
      Verify: `python -m unittest tests.test_agents tests.test_triage -v`. All tests pass.

- [ ] 5. Adapt the scripted (offline) pipeline `rd/offline.py` and the synthetic tests. Depends on steps 3–4.
      Files: `rd/offline.py`, `tests/test_synthetic_pipeline.py`
      - Keep the `_call` traces for `get_return` and `screen_style`. Then
        `a = assess_return(return_id, as_of)` (from `.agents.triage`, which also provides `handoff` and
        `triage_log_entry`; import `store` from `.`). Its queries hit the same `rows()` cache.
      - If not flagged: emit the Triage decision with `data: None, text: a["note"]` and return
        `{"triage": None, "handoff": h}`.
      - If flagged: `_call(emit, T, tools.find_open_case, style=a["style"], category=a["category"])` for the trace. Then
        `t = a["result"]` (template reason, labelled scripted) and emit the decision `data=t`.
        - LOW: call `store.log_triage(triage_log_entry(a, t))`, emit the same stage text as the pipeline, and return.
        - ATTACH_TO_CASE: emit the same stage text and return.
        - Otherwise emit the stage "… escalating …" and continue the existing investigation/response sequence with
          `st, cat = a["style"], a["category"]`. Replace both uses of `t["rationale"]` with `t["reason"]` (`open_case`
          evidence and the supplier claim text).
      - Return `{"triage": t, "handoff": h, "finding": finding}` on the full path.
      - `tests/test_synthetic_pipeline.py`:
        - In `test_cli_runs_after_relocation_from_another_directory`, replace `'"decision": "INVESTIGATE"'` with
          `'"severity": "HIGH"'` and `'"escalate": true'`. Keep the `APPROVAL` check.
        - In `test_ui_handles_missing_data_and_scripted_synthetic_run`, replace
          `.get("data", {}).get("decision") == "INVESTIGATE"` with
          `(event.get("data") or {}).get("escalate") is True and event["data"].get("severity") in ("HIGH", "MEDIUM")`.
        - Add `test_triage_severity_for_seeded_scenarios`. After `self.store.reset()` and `self.tools.AS_OF.set`, import
          `rd.agents.triage` inside the test (after `_reload_rd`). `assess_return` gives 6027 → HIGH, 1068 → HIGH and
          3699 → MEDIUM, all on 2026-01-31, each with `escalate is True`, `route == "INVESTIGATE"`, keys ==
          `TRIAGE_FIELDS`, a non-empty `where` that contains a `"channel "` entry, and `"customer_uid" not in json.dumps(a)`.
        - Add `test_triage_isolated_return_not_flagged`: 940 @ 2026-01-07 → `flagged False`, `result None` and route
          `NOT_FLAGGED`.
        - Add `test_triage_low_is_logged_not_escalated`. Use `self.data.one(...)` to find the latest `return_id` with
          style `SYNTH-TrailRunner`, category `Fit: too big` and `return_date <= DATE '2026-01-13'`. Reset the store, run
          `rd.offline.run_scripted(rid, "2026-01-13", events.append)`, and check that triage severity is "LOW",
          `escalate is False`, no event comes from "Investigator Agent", `store.snapshot()["triage_log"]` has one entry
          whose `triage` equals the result, and `cases` is empty.
      Verify: `python -m unittest tests.test_synthetic_pipeline -v`. All tests pass, including the CLI and UI subprocess
      tests. Then run `python -m unittest discover -s tests -v`, which must be fully green.

- [ ] 6. Adapt the CLI and Streamlit UI consumers. Depends on step 5.
      Files: `run_demo.py`, `app.py`
      - `run_demo.py` `emit`: for `type == "decision"` with `e.get("data") is None`, print `f"{tag} ✅ {e.get('text', '')}"`.
        Otherwise keep `json.dumps(e['data'])`, raising the slice from 600 to 900 chars so `escalate`/`reason` are not
        cut. After the approvals loop, print
        `f"  TRIAGE LOG {x['triage']['severity']} {x['triage']['sku']} | {x['category']} | {x['triage']['reason']}"`
        for `x in db.get("triage_log", [])`. Update the docstring examples: "isolated" → "not flagged", "quality" →
        "HIGH, escalated".
      - `app.py` `render_event`, Triage branch:
        - If `"severity" in d` or `d == {}` with `e.get("text")`, use the new shape.
          - `sev = d.get("severity") or "Not flagged"`
          - `tone = "investigate" if d.get("escalate") else "isolated"`
          - `heading = f'<span class="v">{_esc(sev)}</span>'`, with " · escalated", or " · logged" for LOW, appended
            outside the span.
          - `meta = " · ".join(_esc(x) for x in [d.get("sku", "")] + (d.get("where") or [])[:4] if x)`, plus
            `" · +N more"` when more than 4 entries exist.
          - The body is `_esc(d.get("reason") or e.get("text", ""))`, plus a second line
            `f"Return rate {rr:.1%} vs baseline {br:.1%} · {units} units"` when the fields exist.
          - The kicker stays `f"{num} · Triage decision"`.
        - Otherwise keep the current `decision`/`rationale` rendering unchanged for old saved traces.
        - Escape all dynamic text with `_esc`, as today.
      - `app.py` `case_panel`: read `log = db.get("triage_log", [])`.
        - If there are no cases, show the notice "No case open. Returns that are not flagged are handled normally; LOW
          flags are logged without an investigation."
        - Whenever `log` is non-empty (with or without cases), render `_label("Logged triage flags (not escalated)")` and
          an `st.dataframe` of `[{"sku", "severity", "return_rate", "baseline_rate", "units_returned", "where": ", ".join(where), "reason"}]`.
      - `app.py` static copy:
        - In the stage table, change "When Triage returns INVESTIGATE" to "When Triage escalates a HIGH or MEDIUM flag".
        - Change the agent strip's Triage subtitle from "isolated or pattern" to "flag and severity".
      Verify: `python -m unittest tests.test_synthetic_pipeline -v` passes (its UI test runs app.py through
      `streamlit.testing.AppTest`). Then run the scripted LOW example from step 8, which prints a `TRIAGE LOG LOW` line.

- [ ] 7. Update the docs and the backtest docstring to describe the contract. Do not change backtest code.
      Files: `docs/DATA_CONTRACTS.md`, `docs/ARCHITECTURE.md`, `README.md`, `evaluation/backtest.py` (docstring only)
      - DATA_CONTRACTS: add a "Triage output" paragraph covering:
        - the 8 fields and their mapping (Decision 2), including that sku means style
        - return_rate/baseline_rate as category share vs company share
        - single object or none per return
        - the severity bands and constants in `rd/detect.py`
        - escalate = HIGH/MEDIUM
        - LOW entries in the `triage_log` list of `cases.json` via `store.log_triage`
        - the gaps: no region, static baseline
      - ARCHITECTURE: one sentence noting that Triage severity and escalation are computed in `rd/detect.py`/
        `rd/agents/triage.py` and the model writes only the reason, and that LOW flags are logged, not investigated.
      - README "Demo interface and model routing": change the Investigator bullet to say it runs only for HIGH/MEDIUM
        triage flags.
      - backtest docstring: add a note that the first SIGNAL day equals the first day Triage escalates (severity MEDIUM or
        HIGH).
      Verify: `python -m compileall -q rd app.py run_demo.py scripts tests evaluation legacy` succeeds and
      `python -m unittest discover -s tests -v` is green.

- [ ] 8. Run the full CI-equivalent verification in PowerShell from the repo root with the `.venv` Python.
      Files: none
      ```powershell
      python -m compileall -q rd app.py run_demo.py scripts tests evaluation legacy
      python scripts/validate_cleaned_data.py
      python -m unittest discover -s tests -v
      $env:RD_BACKEND="duckdb"; $env:RD_DATA_DIR="data/cleaned"; $env:RD_RUNTIME_DIR="runtime/cleaned-ci"
      python run_demo.py isolated --scripted   # expect "Not flagged: ..." and no case
      python run_demo.py quality --scripted    # expect "severity": "HIGH", "escalate": true, a CASE and APPROVAL lines
      python run_demo.py fit --scripted        # expect "severity": "MEDIUM", "escalate": true, a fit-guidance APPROVAL
      # Synthetic runs: generate into ignored runtime/, NOT data/synthetic (that directory must not be touched)
      python scripts/generate_synthetic_data.py --out runtime/synthetic-ci
      $env:RD_DATA_DIR="runtime/synthetic-ci"; $env:RD_RUNTIME_DIR="runtime/synthetic-ci-runtime"
      python run_demo.py syn_isolated --scripted   # not flagged
      python run_demo.py syn_quality --scripted    # HIGH, escalated
      python run_demo.py syn_fit --scripted        # HIGH, escalated
      python run_demo.py syn_damage --scripted     # MEDIUM, escalated
      # LOW logging check (rid = latest SYNTH-TrailRunner 'Fit: too big' return on/before 2026-01-13; the step-5 test shows how to find it)
      python run_demo.py --return-id <rid> --as-of 2026-01-13 --scripted   # expect "severity": "LOW", "escalate": false, a "TRIAGE LOG LOW" line, no Investigator output
      Remove-Item Env:RD_BACKEND, Env:RD_DATA_DIR, Env:RD_RUNTIME_DIR
      ```
      All commands must exit 0 with the expected severities from the Decision 3 table. CI's `legacy/starter` step is
      unaffected because legacy/ is not modified. Running it is optional.
      Clean up `runtime/synthetic-ci*` and `runtime/cleaned-ci` afterwards. They are gitignored, but leave no
      verification artifacts behind.

## Focused tests added (summary)

- `tests/test_triage.py` (new, no data needed):
  - severity band matrix and the LOW z gate
  - `escalates`
  - `store.log_triage` persistence and backward compatibility
  - the `finalize_result` exact shape and code-overrides-model behaviour
  - the root-cause guard and fallbacks
  - the template reason contains no cause words
  - the prompt contains the spec text verbatim
- `tests/test_agents.py` (rewritten pipeline tests):
  - not flagged → no model and no downstream agents
  - LOW → logged, not escalated
  - open case → attach
  - HIGH → Investigator and Response in order, with code overriding the model's severity
- `tests/test_synthetic_pipeline.py`:
  - real-DuckDB severities for the seeded scenarios
  - the isolated return is not flagged
  - LOW scripted run logged to `triage_log`
  - updated CLI and UI assertions for the new shape
