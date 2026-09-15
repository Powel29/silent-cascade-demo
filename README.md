# Silent Cascade Decision Firewall

[![SDG 11: Sustainable Cities and Communities](https://img.shields.io/badge/SDG%2011-Sustainable%20Cities-orange.svg)](#)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](#)
[![Theme](https://img.shields.io/badge/Theme-The%20Butterfly%20Effect-red.svg)](#)

> **Manipal Hackathon (M#) — Round 1** · *Cascading Failure: When One Failure Becomes Many* ·
> Disaster Resilience & Critical Infrastructure (UN SDG 11) · Bengaluru, Karnataka

> Silent Cascade is a consequence-aware Decision Firewall for AI-routed civic complaints.
> AI handles routine cases, but when danger, uncertainty, missing data, or infrastructure
> consequence becomes high, the Firewall restricts AI authority, overrides unsafe routes,
> initiates the emergency action, and ensures that someone acknowledges the incident before a
> digital mistake becomes a physical cascade.

**Read [`LIMITATIONS.md`](LIMITATIONS.md) first.** It states the one claim this prototype
supports, labels every number as observed / inferred / assumed / synthetic / measured /
simulated / cited, and reports the operational cost of the Firewall alongside its benefit.

---

## The problem

A citizen reports a sparking transformer in Kannada. The grievance system's AI classifier
returns `200 OK` and routes the complaint to routine maintenance — or returns nothing at all
and the complaint drops into a general queue. Uptime, latency and error-rate dashboards stay
green, because they measure whether the AI *answered*, not whether the decision was *safe to
act on*. Fourteen days later the transformer fails, load shifts to neighbouring substations,
and hospitals fall back to generators.

The safety gap is not merely that an AI can degrade. It is that a high-consequence AI decision
is allowed to control an operational action with no independent check, no override, and no
confirmation that anyone responded.

## The solution

A deterministic safety and dispatch layer between the classifier and operations. The AI
*proposes* a route; the Firewall decides how much authority the AI gets by asking:

> If this decision is wrong, how dangerous is the consequence?

```text
Citizen complaint + location + structured hazard answers
        ↓  (complete original complaint preserved)
┌──────────────────────────────┬───────────────────────────────┐
│ AI department prediction     │ Independent multilingual      │
│ + score margin (uncertainty) │ safety scan of ORIGINAL text  │
└──────────────────────────────┴───────────────────────────────┘
        ↓
Affected asset → criticality tier and simulated consequence (corrected cascade engine)
        ↓
Danger · uncertainty · dangerous downgrade · missing data · repair window · reliability state
        ↓
GREEN  → automatic routing (AI autonomy allowed)
YELLOW → AI route is a recommendation; rapid human verification before final routing
RED    → immediate simulated emergency work order + human review IN PARALLEL; AI overridden
        ↓
Acknowledgement required for Red; unacknowledged incidents re-escalate to the control room
        ↓
AI-only outcome vs. Firewall outcome (simulated)
```

Design rules: the safety scan reads the **complete original complaint** (never the truncated
text the classifier saw) plus structured intake answers, and never the AI prediction;
**unknown risk is not low risk** (missing classifier output, missing asset context or an
unavailable reliability state cannot become Green); **mandatory Red overrides** beat every
score; **routing is not resolution** (Red requires acknowledgement).

## The canonical demonstration (`outputs/decision_trace.json`, scenario `SC-01`)

```text
Kannada complaint: sparks from the transformer box, smell of burning, children nearby
        ↓
Truncated classifier input (40 chars) → no department at all (unparseable)
AI-only workflow: general / maintenance queue, 336 h SLA (assumed)
        ↓
Independent scan of the full complaint: ಕಿಡಿ (sparks), ಸುಟ್ಟ ವಾಸನೆ (burning smell)
Structured intake: "sparking", immediate danger = yes
        ↓
Scenario-selected asset: LR Bande Substation — rank 2 of 190, very-high tier,
2,729,047 simulated service population exposed if it fails (synthetic mapping, simulated outcome)
        ↓
Reliability: Kannada + truncated → degraded → SAFE MODE ACTIVE
        ↓
RED — IMMEDIATE EMERGENCY DISPATCH
  STRUCTURED_IMMEDIATE_DANGER · DIRECT_HAZARD · DANGEROUS_DOWNGRADE ·
  VERY_HIGH_ASSET_CRITICALITY · REPAIR_WINDOW_AT_RISK · RELIABILITY_DEGRADED ·
  UNPARSEABLE_CLASSIFICATION · LOW_MARGIN · TRUNCATED_CLASSIFIER_INPUT
        ↓
Emergency work order → electrical_emergency, P1, human review in parallel, acknowledgement required
Unacknowledged after 30 min (assumed) → re-escalated to control room supervisor
        ↓
AI only: response at 336 h ≥ 336 h window → initiating failure → corrected cascade runs
Firewall: response at 4 h → initiating failure prevented under the stated scenario assumption
```

## Evidence (measured on the controlled set; see `LIMITATIONS.md` for how to read it)

`python src/evaluate_firewall.py` scores 20 complaints × 2 languages × 3 classifier conditions
= 120 cases under five configurations. Counts always carry their denominators.

| metric | AI only | Existing guard | Decision Firewall |
|---|---|---|---|
| Dangerous AI routes intercepted | 0 / 9 | 9 / 9 | **9 / 9** |
| Critical cases with an emergency-speed response | 15 / 24 | 18 / 24 | **24 / 24** |
| Correct low-risk routes kept automatic | 83 / 83 | 73 / 83 | 27 / 83 |
| Decisions needing human review (cost) | 0 / 120 | 25 / 120 | 93 / 120 |
| Unnecessary escalations (cost) | 0 / 83 | 10 / 83 | 56 / 83 |

The existing guard blocks the misroutes too, but leaves 6 critical cases in a 48 h queue; the
Firewall acts immediately on all 24. The Firewall's review load is concentrated in the two
injected-degradation conditions (truncated input, degraded reliability) where the policy
deliberately withdraws AI autonomy; under clean input it keeps 27 of 32 correct low-risk routes
automatic (`outputs/firewall_evaluation_by_condition.csv`). A reference policy that escalates
everything scores 0 / 83 on safe automation.

![Firewall comparison](outputs/firewall_comparison.png)

## Running it

```bash
pip install -r requirements.txt
streamlit run app.py          # Live intervention (default) · Evidence · Scenario explorer · Methodology
```

The demo is built to be read cold, without a narrator. A six-tile **pipeline ribbon** carries the
live value of every stage (complaint, AI prediction, independent scan, asset consequence, quality
check, decision), each reason appears as a short chip inside the stage that produced it, and three
guided buttons drive the whole story: **① The dangerous miss**, **② A routine complaint**,
**③ Nobody accepts it**. Every control stays visible on the page; expanders hold justification and
appendices only. See [`docs/STREAMLIT_APP.md`](docs/STREAMLIT_APP.md).

Offline pipeline (all cached; no network needed unless you re-fetch OSM data):

```bash
python src/build_graph.py         # nodes/edges/graph from cached OSM layers (data/raw/)
python src/d1_cascade.py          # FULL criticality ranking + cascade frames/GIFs (corrected engine)
python src/d1_robustness.py       # topology/headroom sensitivity sweep
python src/d2_language.py         # controlled bilingual classifier experiment (legacy D2, retained)
python src/evaluate_firewall.py   # firewall_decisions.csv, firewall_evaluation.csv, comparison.png, decision_trace.json
python -m pytest tests/ -q        # cascade invariants, Firewall policy, evaluation, app smoke tests
```

## Repository

```text
app.py                      Streamlit prototype: Live intervention · Evidence · Scenario explorer · Methodology
config.yaml                 every assumption and policy parameter (firewall block: confirmed_by_team=false)
src/
  cascade.py                corrected cascade engine (one-time shedding, buffered assets, load conservation)
  decision_firewall.py      safety scan · asset context · reliability state · Green/Yellow/Red · action plan
  evaluate_firewall.py      comparative evaluation (only module that reads ground truth)
  d2_language.py            deterministic EN/KN keyword classifier + legacy guard (baseline)
  build_graph.py, fetch_data.py, d1_cascade.py, d1_robustness.py
  d3_dashboard.py, d4_intervention.py   legacy problem illustration / legacy analysis (appendix only)
data/
  complaints.csv            20 synthetic bilingual complaints with ground truth (evaluation only)
  scenarios.csv             explicit complaint-to-asset demo mappings (synthetic, scenario-selected)
  raw/, processed/          cached OSM layers; nodes/edges/graph
outputs/
  firewall_decisions.csv    one auditable row per case × configuration
  firewall_evaluation.csv   counts, denominators, rates (+ _by_condition.csv)
  firewall_comparison.png   primary evidence chart
  decision_trace.json       canonical scenario, end to end
  d1_criticality.csv        full ranking (rank, percentile, backup/outage counts)
  d1_*.gif, d1_frames/, d1_robustness.csv, d2_*.csv/png, d3_*, d4_*   regenerated / legacy assets
tests/                      test_cascade.py · test_firewall.py · test_evaluation.py · test_app.py
docs/STREAMLIT_APP.md       page-by-page description of the interface
LIMITATIONS.md              claim boundary and provenance
PLAN.md, CLAUDE.md          product direction and implementation specification
silent-cascade-plan.md      historical research and planning notes
```

## What this is not

- Not a production LLM, not an external AI API: the classifier is a deterministic keyword
  proxy for an AI routing layer; the innovation is the controller around it.
- Not a prediction of Bengaluru's real grid: locations are observed, topology is inferred,
  loads and buffers are assumed, and cascade size is highly sensitive to the assumed headroom.
- Not a monitoring product: the reliability state is a supplied signal from a controlled
  quality check, not continuous production monitoring.
- Not real dispatch: work orders, acknowledgements and re-escalations are simulated; nothing is
  sent to anyone. Simulated exposure is service population, not people saved.

## License & attribution

Map data © [OpenStreetMap](https://www.openstreetmap.org/copyright) contributors (ODbL).
Code and synthetic data: hackathon submission, Silent Cascade team.
