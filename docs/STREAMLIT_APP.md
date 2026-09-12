# Silent Cascade — Streamlit App: Pages, Implementation & Results

`app.py` is an interactive Streamlit prototype layered on top of the repo's pure
functions (`src/cascade.py`, `src/d2_language.py`, `src/d4_intervention.py`). It does not
reimplement any logic — every number it shows comes from the same code that writes
`outputs/*.csv`.

> **Note on scope vs. CLAUDE.md:** [CLAUDE.md](../CLAUDE.md) specifies four static demo
> assets (PNG/GIF/CSV) and explicitly says *"No Streamlit, no Flask, no database, no web
> server."* This app is a later, additional interactive layer built on top of that
> pipeline — it is not part of the original build spec. It's documented here as-is,
> since it exists on this branch and is runnable.

Run it with:

```bash
pip install -r requirements.txt
streamlit run app.py
```

It has four pages, selected from the sidebar radio (`PAGES` dict, [app.py:779](../app.py:779)):

1. Overview
2. Cascade simulator
3. Language routing
4. Intervention comparison

---

## 1. Overview (`page_overview`, [app.py:433](../app.py:433))

### Purpose
Pitch framing for the whole demo: states the thesis ("nothing monitors the AI that
decides which asset gets fixed first"), walks through the causal chain from a citizen
complaint to a physical cascade, shows one concrete misrouted ticket next to a fake
"all green" monitor, and closes with a provenance table so every number in the app is
labeled real / inferred / assumed / simulated.

### Implementation
- **Hero header** — static HTML/CSS block (hackathon eyebrow, title, one-line thesis,
  metadata row).
- **Causal chain** (`sc-flow` grid) — a fixed 7-step list (`steps` local variable):
  Intake → AI layer → Ops → Delay → T+14d equipment fails → Cascade → Impact. The last
  three steps get a red ("bad") style. This is narrative scaffolding, not computed data.
- **"No alarm fired" section** — two columns:
  - Left: `MONITOR_HTML` ([app.py:357](../app.py:357)) embedded via
    `st.components.v1.html`. This is the same fake "all green" dashboard as D3
    (`src/d3_dashboard.py`), reimplemented inline as a self-contained HTML/CSS/JS
    snippet so it can animate client-side (sparklines drift, a request log scrolls,
    a clock ticks) without triggering Streamlit reruns. It is explicitly a mock: metric
    values are randomized with a simple linear-congruential PRNG seeded at 7, not real
    telemetry.
  - Right: a static "what the classifier actually did" card, hard-coded to complaint
    `c01` — a Kannada transformer-spark complaint that the keyword classifier fails to
    parse and drops to a general queue with a 14-day SLA.
- **Provenance table** (`sc-prov` list) — a fixed list of 9 rows, each tagged
  `real` (observed), `inf` (inferred), `sim` (assumed/simulated), or `syn` (synthetic),
  e.g. "Substation locations (190) — OpenStreetMap — Observed" vs. "Capacity, load,
  population served — config.yaml seeded draws — Assumed." This mirrors the
  provenance discipline CLAUDE.md requires on every node/edge (`provenance` column) but
  presents it as a human-readable legend for the whole app.

### Result
No computation happens on this page — it's pure presentation over static content and
values pulled from the other three pages' underlying data (counts like 190 substations /
1,217 hospitals+pumps, sourced from `data/processed/nodes.csv`). It sets up the vocabulary
("observed / inferred / assumed / simulated") that recurs on every other page's captions.

---

## 2. Cascade simulator (`page_cascade`, [app.py:507](../app.py:507))

### Purpose
Interactive version of D1 (`src/d1_cascade.py`'s cascade GIF), but scrubbable/playable
in-browser instead of a fixed GIF, plus the criticality ranking table (D1's
`outputs/d1_criticality.csv`).

### Implementation
- Loads `data/processed/graph.gpickle` (`load_graph`, cached with `st.cache_resource`),
  `data/processed/nodes.csv` (`load_nodes`), and `config.yaml` (`load_config`).
- `ranking()` calls `criticality_ranking()` from `src/cascade.py` directly (cached with
  `st.cache_data`), producing the top-10 substations by cascade impact.
- A `st.selectbox` lets the user pick which substation is the *initiating failure*,
  defaulting to the top-ranked one. Selecting a node calls `run_cascade(node)`, which is
  `cascade(load_graph(), [node], max_steps=cfg["d1"]["max_steps"], hours_per_step=...)`
  — the exact same pure function used by the static pipeline, deep-copying the graph so
  nothing is mutated between reruns.
- **Map rendering** ([`cascade_component`](../app.py:328), backed by `MAP_HTML`,
  [app.py:196](../app.py:196)): instead of Streamlit re-rendering per frame (which would
  cause a full page rerun per animation tick), the *entire* timeline is serialized to
  JSON (`node_list`, `edges`, `steps`) and embedded into a self-contained Leaflet.js page
  via `st.components.v1.html`. A `requestAnimationFrame` loop in the browser animates
  node/edge color transitions (healthy → overloaded → failed) against real OpenStreetMap
  tiles, with play/pause, a scrub bar, speed toggle (slow/normal/fast), and a HUD showing
  elapsed time, people affected, hospitals on generator, wards without water, and
  substations tripped. This avoids the "flicker on every rerun" problem Streamlit's
  native `st.pyplot`/`st.image` loop would have (see git log: *"Animate the cascade
  client-side to stop page reruns and flicker"*).
- Below the map: `st.dataframe(rank, ...)` renders the criticality ranking table
  (`node_id, name, people_affected, cascade_size, hospitals_hit`), captioned as "the
  ranking a classification node has to beat."

### Result
With Bengaluru's fetched network (190 substations, 1,060 hospitals, 157 water nodes — see
`data/processed/nodes.csv`), the top-ranked substation by `criticality_ranking()`
(`sub_170`, "MUSS NGEF") produces a final cascade of **3,073,265 people affected**, an
**870-node** failure cascade, and **668 hospitals** hit (`outputs/d1_criticality.csv`).
The UI lets a user pick any of the 190 substations and watch its specific cascade play
out at real coordinates instead of only seeing the single worst-case GIF.

---

## 3. Language routing (`page_language`, [app.py:591](../app.py:591))

### Purpose
The most detailed page: traces one complaint end-to-end through (1) the classifier's
literal decision, (2) a proposed "routing guard" verification checkpoint, (3) what a
misrouted decision does to the physical cascade, and (4) a live canary/alarm that
would have caught the degradation. This is D2 (`src/d2_language.py`) made interactive
and connected to D1's cascade engine and D4's intervention idea.

### Implementation
Uses functions imported directly from `src/d2_language.py`: `classify_one`,
`condition_input`, `route_with_guard`, `canary_report`, `misroute_examples`,
`plot_accuracy`, plus the keyword tables (`FULL_KEYWORDS_EN/KN`,
`SMALL_KEYWORDS_EN/KN`) and `_looks_english`.

Three selectors drive the whole page: complaint ID (from `data/complaints.csv`, 20
rows), language (English vs. Kannada native script), and condition (`clean`,
`truncated`, `small_model` — same three degradation conditions as D2's static
experiment).

**Section 1 — The decision.** `route_with_guard(full, cond, d2_cfg)` runs the keyword
classifier under the chosen condition and returns predicted department, keyword-count
margin, and safety-term hits. `_highlight()` ([app.py:544](../app.py:544)) renders the
complaint text with `<mark>` tags around every keyword hit, colored green if it matches
the true department and red ("wrong") otherwise — visually showing *why* the classifier
picked what it picked. Under `truncated`, the un-seen tail of the text is rendered
struck through. A fake `POST /classify` log line with a synthetic latency is appended
for verisimilitude (mirrors the Overview monitor's request log). The right column shows
true department vs. predicted vs. a verdict (correct / MISROUTED / DROPPED) and the
score margin.

**Section 2 — The routing guard.** Shows `g["naive"]` (today: unparseable falls to
`electrical_maintenance`, i.e. a 14-day SLA) side-by-side with `g["guarded"]` (the
verification-checkpoint logic in `route_with_guard`: unparseable or low-margin
decisions go to a 48-hour verification queue; any safety keyword hit caps the SLA at
the emergency SLA regardless of routed department). Cards are colored red/green based
on whether the resulting SLA is later than `time_to_failure_hours` (336h / 14 days,
from `config.yaml`).

**Section 3 — Cascade linkage.** If the complaint's true department is
`electrical_emergency` (`CASCADE_DEPTS`), the user picks which substation the complaint
"sits on" (defaulting to the #1 criticality-ranked node) and the page calls
`run_cascade(linked)` (same `cascade()` function as page 2) to show the concrete people-
affected number that results if the repair SLA is later than 336h vs. if it's caught in
time. This is the same "same physics, only the decision timing changed" argument as D4.
Non-electrical complaints show a message that the physical model only covers electrical
faults.

**Section 4 — Decision-quality canary.** `canary()` (cached, calls `canary_report()`
from `src/d2_language.py`) re-runs the full 20-complaint golden set across all
conditions/languages and reports accuracy and unparseable rate per language ×
condition. The page computes the English-vs-Kannada accuracy gap for the *current*
condition and raises a visual "ALARM" if that gap exceeds
`d2.canary_language_gap_alarm_pct` (15 points, from `config.yaml`) — this is presented
as "the canary CivicOps never had," i.e. the thing that should have caught the D2
finding automatically instead of a human noticing it in a spreadsheet.

Below the four interactive sections, the page falls back to the static D2 outputs if
present: `outputs/d2_accuracy.csv` plotted via `plot_accuracy()` (same function used by
`d2_language.py`'s `main()`), a pivoted accuracy table, and `misroute_examples()` —
the complaints correctly routed in English but misrouted in native script.

### Result
From `outputs/d2_accuracy.csv` (120 measured classifications: 20 complaints × 2
languages × 3 conditions):

| condition | English accuracy | Native (Kannada) accuracy |
|---|---|---|
| clean | 100.0% | 100.0% |
| truncated | 90.0% | 55.0% |
| small_model | 70.0% | 75.0% |

The `truncated` condition shows a genuine 35-point language gap (native script degrades
far more from truncation than English does) — this is the finding the demo is built
around, and it would trip the page's canary alarm (gap > 15 pts). The `small_model`
condition does *not* show a gap in the direction the pitch expects (Kannada actually
scores higher); per CLAUDE.md's instruction not to tune the experiment to fit the pitch,
this is reported honestly in both the static chart and the interactive canary rather
than hidden. `clean` shows no gap in either language, as expected from a baseline
keyword classifier with full vocabulary in both languages.

---

## 4. Intervention comparison (`page_intervention`, [app.py:750](../app.py:750))

### Purpose
Interactive version of D4 (`src/d4_intervention.py`): lets the user re-run the
baseline/harden/checkpoint comparison live with an adjustable number of runs, instead of
only viewing the static `outputs/d4_comparison.png`.

### Implementation
- `st.slider` for `n_runs` (20–200, default from `config.yaml: d4.n_runs`, step 10).
- On button click (or if already run this session, tracked via `st.session_state.d4`),
  calls `run_interventions(n_runs)` ([app.py:173](../app.py:173)), which:
  1. Loads the graph and `ranking()` to get the top-critical substation.
  2. Draws `n_runs` shared random initial failures via `draw_random_failures()` (paired
     across all three conditions, same seed).
  3. Runs `run_condition()` three times — baseline, on a graph produced by
     `hardened_graph(G, top_node, 1.5)` (capacity × 1.5), and with
     `prevention_rate=cfg["d4"]["verification_checkpoint_prevention_rate"]` (0.4,
     meaning 40% of runs have their initiating failure prevented outright — modeling a
     verification checkpoint catching the misroute before the asset physically fails).
- Renders three `st.metric` columns (mean people affected, % delta vs. baseline,
  illustrative ₹ cost from `config.yaml: assumptions.cost_inr`) and the same
  `plot_comparison()` horizontal bar chart used by the static script.
- If not yet run, falls back to displaying the precomputed `outputs/d4_summary.csv`.

### Result
From `outputs/d4_summary.csv` (100 paired runs per condition, seed 42):

| condition | mean people affected | Δ vs. baseline | illustrative cost |
|---|---|---|---|
| Baseline (no intervention) | 1,470,074 | — | ₹0 |
| Harden substation (capacity ×1.5) | 1,464,398 | −0.4% | ₹8,500,000 |
| Verification checkpoint (40% prevention) | 1,006,309 | −31.5% | ₹150,000 |

The interactive page's headline point: the verification checkpoint (cheap, targets the
AI decision layer) produces a far larger reduction in mean people affected than
physically hardening the top-ranked substation (expensive, targets one piece of
hardware) — at roughly 1.8% of the cost. On the dense 190-substation Bengaluru network,
hardening a *single* node is almost negligible (−0.4%), which sharpens the point: the
cheap decision-layer fix dominates the expensive hardware fix. Both the prevention rate
(40%) and the two cost figures are
explicitly labeled assumptions in `config.yaml`, and the page repeats that label in its
caption rather than presenting them as measured.

---

## Cross-cutting implementation notes

- **Caching.** Every expensive load or computation (`load_config`, `load_graph`,
  `load_nodes`, `run_cascade`, `ranking`, `run_interventions`, `canary`) is wrapped in
  `st.cache_data` / `st.cache_resource` keyed on file mtimes or arguments, so switching
  pages or re-selecting the same substation doesn't re-run the simulation.
- **No client-side reruns for animation.** Both the cascade map (page 2) and the fake
  monitor (page 1) are embedded as self-contained HTML/JS via
  `st.components.v1.html`, animating with `requestAnimationFrame`/`setInterval` inside
  an iframe rather than Streamlit's own rerun loop — this was a deliberate fix for
  flicker (see git history: *"Make the CivicOps monitor on the Overview live,"*
  *"Animate the cascade client-side to stop page reruns and flicker"*).
- **Single source of truth.** No page reimplements simulation or classification logic;
  every number traces back to `src/cascade.py`, `src/d2_language.py`, or
  `src/d4_intervention.py` — the same modules the static `outputs/*.csv`/`*.png` files
  are built from. Where the app shows a number CLAUDE.md would call an "assumption"
  (capacities, populations, SLA hours, prevention rate, costs), the UI labels it as such
  in a caption, matching the provenance discipline in the underlying data schema.
