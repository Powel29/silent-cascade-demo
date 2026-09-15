# Silent Cascade Decision Firewall — Streamlit App: Pages, Implementation & Results

`app.py` is a thin UI over the repository's pure functions. Every decision it shows is produced
by `src/decision_firewall.py` (the same code `src/evaluate_firewall.py` scores), every cascade
by `src/cascade.py`, every classifier result by `src/d2_language.py`. Nothing is reimplemented
in the app layer, nothing is fetched at runtime except OpenStreetMap map tiles, and nothing
dispatches, messages or mutates a real system.

```bash
pip install -r requirements.txt
streamlit run app.py
```

Navigation (sidebar, each option carries a one-line caption): **Live intervention** (default) ·
**Evidence** · **Scenario explorer** · **Methodology & limitations**.

## Design rule: structure explains itself

The app is built so a judge can read it cold, with no narrator and no paragraphs of
explanation. Prose is replaced by structure:

| Instead of text saying | The app shows |
|---|---|
| how the pipeline works | a six-tile **pipeline ribbon** carrying the live value of every stage |
| why the verdict is Red | each reason as a short chip **inside the stage that produced it** |
| what the Firewall adds | AI-only and Firewall panels side by side, always on screen |
| what a control does | a self-describing label plus a `help` tooltip |
| what just changed | a one-line **delta banner**: `CHANGED · GREEN → YELLOW · new reason: …` |
| what safe mode does | a **counterfactual** in the quality-check tile: `if healthy → GREEN` |

Two rules follow from this and are enforced by `tests/test_app.py`:

1. **No feature is hidden behind an expander.** Every control stays on the page. Expanders hold
   justification and appendices only, never a feature.
2. **The verdict renders before any control.** Controls are read from `st.session_state` at the
   top of the page and their widgets are rendered lower down, so the decision leads.

Measured on the canonical scenario at 1400×900, against the previous layout:

| | Before | After |
|---|---|---|
| Scrolling before the verdict appears | 2.3 screens | none, visible on load |
| Visible words, Live intervention | 1,010 | 592 |
| Visible words, Evidence | 560 | 249 |
| Page length, Live intervention | 4.6 screens | 3.4 screens |

---

## 1. Live intervention (`page_live`)

### Layout, in render order

1. **Header** — title and the one question the product asks.
2. **Guided demo** — three buttons that drive the whole story with no instructions:
   ① The dangerous miss (loads the canonical scenario, produces Red),
   ② A routine complaint (loads a clean low-risk scenario, produces Green, proving the
   Firewall does not escalate everything),
   ③ Nobody accepts it (advances the acknowledgement clock into re-escalation).
3. **Delta banner** — appears only when the verdict changes, naming the before, the after and
   the first new reason code.
4. **Pipeline ribbon** — six tiles: Complaint, AI prediction, Independent scan, Asset
   consequence, AI quality check, Firewall decision. Each shows a live value, a secondary
   detail, a colour, and the reason chips that fired at that stage. The decision tile is wider
   and heavier than the rest. Reason chips are short plain language ("direct hazard", "very
   high consequence", "input cut off"); the stable machine code is the chip's tooltip and is
   listed verbatim in the reasons expander, so nothing is lost.
5. **Verdict card** — `RED — IMMEDIATE EMERGENCY DISPATCH` / `YELLOW — HUMAN VERIFICATION
   BEFORE ROUTING` / `GREEN — AUTOMATIC ROUTING ALLOWED`, with the top reason in plain
   language and an expander holding all reasons with their codes.
6. **Contrast panels** — AI only versus With Decision Firewall: route, response time and the
   simulated physical outcome for each.
7. **Work order and acknowledgement** — work-order type, department, priority, whether review
   runs in parallel, live status and what happens if nobody accepts. Buttons: *Crew accepts*,
   *Nobody accepts*, reset. The card is rendered into a container reserved above the buttons so
   a click updates the status in the same rerun.
8. **Controls** — one bordered block, every input visible: scenario, complaint, submitted
   language, AI input condition (labelled *full text* / *cut to 40 chars* / *smaller model*),
   affected asset, AI quality check (*auto* / *healthy* / *degraded* / *no signal*), hazard
   boxes ticked at intake, immediate-danger flag, and the optional assumed failure window.
9. **Safe mode banner** — `SAFE MODE ACTIVE` or `SAFE MODE OFF`, stated as behaviour.
10. **Evidence behind the verdict** — four cards in two rows: the complaint as submitted with
    hazard hits marked, what the AI saw with the cut-off text struck through, the independent
    scan hits with their source, and the asset context with provenance pills.
11. **Cascade map** — rendered only when the AI-only branch actually fails.
12. **Two expanders** — the all-green operations dashboard as the problem illustration, and
    provenance and caveats for the page.

### Canonical scenario (SC-01), as the ribbon reads it

```text
1 COMPLAINT        Kannada · 185 chars · intake flags: 2      [immediate danger]
2 AI PREDICTION    none — unparseable · margin 0 · saw 40 of 185 chars
                                          [unparseable] [low margin] [input cut off]
3 INDEPENDENT SCAN 2 direct hazards · electrical sparking, fire or burning +1 more
                                          [direct hazard] [dangerous downgrade]
4 ASSET CONSEQUENCE very high · rank 2/190 · 2,729,047 exposed
                                          [very high consequence] [repair too late]
5 AI QUALITY CHECK degraded · automatic routing restricted   [quality degraded]
6 FIREWALL DECISION RED · dispatch now · review in parallel
```

AI-only responds at 336 h, at or after the assumed failure window, so the cascade runs.
The Firewall responds at 4 h, so the initiating failure is prevented under the stated
scenario assumption.

### Presenter moments

- Click ② then set **AI quality check** to `degraded`: Green becomes Yellow, the delta banner
  names `RELIABILITY_DEGRADED`, and the tile shows `if healthy → GREEN`.
- Click ② then change **Affected asset** from MUSS NGEF (normal tier) to LR Bande (very high):
  consequence alone moves the verdict to Yellow.
- Set **Affected asset** to `(no asset context)`: `ASSET_CONTEXT_MISSING`, because unknown
  consequence is never treated as low consequence.
- Click ③: the Red work order re-escalates to the control room supervisor.

---

## 2. Evidence (`page_evidence`)

One question as the headline, one line of context, then a single comparison table: six metrics
by three configurations, every cell a count over its denominator, best value green and worst
red. One sentence states the trade-off. Then the comparison chart.

Everything else is an expander: the per-condition workload breakdown, mapped-scenario simulated
outcomes, how each configuration works and how response time is modelled, the full five-
configuration table including the escalate-everything reference, the legacy D2 accuracy
experiment with bootstrap intervals, and the cascade robustness sweep with the legacy D4 table.

## 3. Scenario explorer (`page_explorer`)

Pick a substation to fail. Shows its rank, percentile and tier from the full ranking, the
simulated outcome summary, and the client-side Leaflet animation of the corrected cascade: grey
healthy, amber overloaded or on backup, red tripped or in service outage. The top-10 ranking is
in an expander. The page exists to show that consequence depends on which asset is hit, which is
the input the Firewall reads when it scores an asset.

## 4. Methodology & limitations (`page_method`)

The provenance table (Observed / Inferred / Assumed / Synthetic / Measured / Simulated / Cited)
and four expanders: what the evidence does and does not support, what changed in the physical
model, known limitations, and the commands to reproduce every number.

---

## Cross-cutting implementation notes

- **Caching.** `st.cache_data` / `st.cache_resource` are keyed on the modification times of
  `data/processed/graph.gpickle`, `outputs/d1_criticality.csv` and `config.yaml`.
- **Fail loudly.** A missing graph, ranking, scenario file or evaluation CSV produces an error
  naming the exact command to run. A legacy top-10 `d1_criticality.csv` without
  `rank`/`criticality_percentile` is rejected the same way. No asset is ever chosen on a
  complaint's behalf.
- **Escaping.** Complaint text, OSM names and scenario notes go through `html.escape`; the map's
  node list is JSON-encoded with `</` escaped and names render through Leaflet tooltips.
- **State.** Control values live in `st.session_state` and are seeded from the canonical
  scenario on first load. Selecting a scenario resets its dependent controls. The
  acknowledgement demo keeps `ack` and `ack_min`, reset whenever the decision changes.
- **No runtime ground truth.** The app never passes `true_dept` to the Firewall;
  `assess_risk()` raises if it ever receives it.
- **Tests.** `tests/test_app.py` drives the app with `streamlit.testing.v1.AppTest` and covers:
  the canonical scenario renders Red; the ribbon shows all six stages with chips and tooltips;
  no feature is hidden behind an expander; the guided buttons drive the demo and the delta
  banner announces the change; language and condition changes recompute; changing the asset
  changes the consequence context; changing reliability changes AI autonomy and surfaces the
  counterfactual; an unacknowledged Red order re-escalates; rendered text is escaped; a missing
  ranking file yields an actionable error.
