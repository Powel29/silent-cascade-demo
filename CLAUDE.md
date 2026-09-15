# CLAUDE.md — Silent Cascade Decision Firewall Implementation Plan

This file is the current build specification for **Silent Cascade**. It supersedes the
original `CLAUDE.md` build spec while preserving the useful context, data, experiments,
assets, constraints, and honesty rules from `PLAN.md`, `LIMITATIONS.md`, and the existing
implementation.

The repository began as a set of four hackathon demonstration assets. It now also contains
an interactive Streamlit prototype. The next implementation must turn those components into
one coherent, active safety solution for the Round 1 submission.

Do not discard the existing work. Reuse it as evidence and infrastructure. The required
pivot is from **detecting and illustrating AI routing degradation** to **preventing a
dangerous routing decision from delaying infrastructure response**.

---

## 1. Project context that must be preserved

- **Project:** Silent Cascade
- **Event:** Manipal Hackathon (M#), Round 1
- **Problem statement:** *Cascading Failure: When One Failure Becomes Many*
- **Domain:** Disaster Resilience and Critical Infrastructure
- **SDG:** UN SDG 11 — Sustainable Cities and Communities
**Theme:** The Butterfly Effect

### Original failure chain

```text
Citizen submits a critical complaint in a regional language
        ↓
AI classifier returns a technically successful but incorrect decision
        ↓
Complaint is routed to a routine department or long repair queue
        ↓
Dangerous infrastructure fault remains unresolved
        ↓
One asset fails
        ↓
Failure propagates through dependent infrastructure
        ↓
Citizens, hospitals, and water services are affected
```

The important insight remains valid: ordinary operational monitoring can report healthy
uptime, latency, and error rates while the system is making unsafe decisions.

### Original implementation

The existing repository contains:

- **D1 — Infrastructure cascade simulation:** real Bengaluru OSM coordinates, inferred
  network topology, assumed capacities/loads, cascade animation, and criticality ranking.
- **D2 — Language-routing experiment:** 20 synthetic bilingual complaints, deterministic
  keyword classifier, English/Kannada comparison, dangerous-downgrade metric, and routing
  guard.
- **D3 — All-green dashboard mock:** illustrates that system-health metrics do not measure
  decision quality.
- **D4 — Intervention comparison:** compares one hardened substation with an assumed
  verification-checkpoint prevention rate.
- **Interactive Streamlit app:** exposes the cascade, classifier, routing guard, canary, and
  intervention analysis.

These are not to be erased. Their role changes:

- D1 becomes the **consequence model and visual evidence**.
- D2 becomes the **controlled failure injection and evaluation dataset**.
- D3 becomes a **brief problem illustration only**, not the solution.
- D4 becomes **legacy supporting analysis** and must be replaced in the primary story by a
  direct evaluation of the Decision Firewall.
- The Streamlit app becomes an **active incident-intervention demonstration**, not a monitor.

---

## 2. Final problem definition

Municipal grievance systems may use AI to assign departments and urgency. A decision can be
wrong because of language handling, truncation, limited model capability, ambiguous text, or
missing context while the API still returns success.

The safety problem is not merely that the AI degraded. The safety problem is that an unsafe
AI decision is allowed to control a high-consequence operational action without an
independent check, immediate override, or confirmation that someone responded.

### Problem statement for the submission

> A silent AI routing error can delay a critical infrastructure repair and allow one
> preventable fault to become a cascading physical failure. Existing system-health monitoring
> cannot stop this because it measures whether the AI responded, not whether the operational
> consequence of its decision is safe.

### What the solution must accomplish

The solution must:

1. detect direct danger independently of the AI department prediction;
2. understand the consequence of delay using affected-infrastructure context;
3. restrict AI autonomy when consequence or uncertainty is high;
4. override dangerous routes and initiate the safer operational action;
5. require acknowledgement and re-escalate if nobody accepts the incident;
6. explain why every override occurred; and
7. demonstrate that it catches dangerous misroutes without escalating every complaint.

---

## 3. Final solution

# Silent Cascade Decision Firewall

> A deterministic, consequence-aware safety and dispatch layer placed between an AI
> complaint classifier and municipal operations. The AI proposes a route; the Decision
> Firewall decides how much authority the AI is allowed to exercise.

The primary question is no longer:

> “Is the AI confident?”

It is:

> “If this decision is wrong, how dangerous is the consequence?”

### Final end-to-end pipeline

```text
Citizen complaint + location + structured hazard answers
        ↓
Preserve the complete original complaint
        ↓
┌──────────────────────────┬────────────────────────────────┐
│ AI department prediction │ Independent multilingual safety│
│ and uncertainty signal   │ scan of the original complaint │
└──────────────────────────┴────────────────────────────────┘
        ↓
Resolve affected infrastructure asset
        ↓
Look up asset criticality and simulated downstream consequence
        ↓
Evaluate urgency, dangerous downgrade, delay, missing data,
asset consequence, and current system-reliability state
        ↓
Decision Firewall assigns GREEN / YELLOW / RED
        ↓
┌───────────────────┬──────────────────────┬────────────────────────────┐
│ GREEN             │ YELLOW               │ RED                        │
│ automatic routing │ rapid human approval │ immediate emergency action │
│                   │ before final routing │ + human review in parallel │
└───────────────────┴──────────────────────┴────────────────────────────┘
        ↓
Create a simulated dispatch/work-order action
        ↓
Require acknowledgement; re-escalate if not accepted
        ↓
Compare AI-only outcome with Decision Firewall outcome
```

The Round 1 implementation is a deterministic, rules-based prototype. It does not need an
LLM, production dispatch integration, real utility telemetry, or a database.

---

## 4. Design principles

### 4.1 The AI is an adviser, not the final authority

The classifier may automatically route only complete, clearly low-risk complaints. A model
must never be the sole decision-maker for a complaint whose incorrect handling could cause
immediate harm or significant infrastructure consequence.

### 4.2 The safety path must be independent

The existing `route_with_guard()` examines the same degraded input shown to the classifier.
That makes the guard vulnerable to the same truncation or preprocessing failure.

The new safety scan must inspect:

- the complete original complaint before degradation;
- the selected/detected language;
- structured hazard answers supplied at intake; and
- asset/location context when present.

The safety scan must not depend on the classifier's department prediction.

### 4.3 Unknown risk is not low risk

Missing classifier output, missing asset context, unavailable safety state, or conflicting
signals must never silently become Green.

### 4.4 Emergency action must not wait for verification

Red incidents trigger the emergency action immediately. Human verification happens in
parallel. Yellow incidents wait for rapid verification. Green incidents may be routed
automatically.

### 4.5 Routing is not resolution

The demonstration must show a dispatch/work-order acknowledgement state. A routed complaint
that nobody accepts remains unsafe. The prototype simulates acknowledgement and re-escalation;
it must never claim to integrate with a real municipal dispatch system.

### 4.6 Prefer explicit rules over a decorative “AI risk score”

The risk policy must be inspectable and deterministic. Mandatory Red overrides take priority
over additive scores. If a numeric score is shown, all weights and thresholds must live in
`config.yaml`, be labelled **assumed policy parameters**, and be accompanied by the actual
reason codes.

### 4.7 Do not solve safety by escalating everything

The evaluation must report false/unnecessary escalations and human-review rate alongside
critical-incident catch rate. A controller that marks every complaint Red is not successful.

---

## 5. Scope and non-goals

### Required for Round 1

- Deterministic bilingual classifier retained as the controlled AI-routing proxy.
- Independent safety scan of the original complaint.
- Asset-context lookup using existing graph and criticality outputs.
- Consequence-aware Green/Yellow/Red policy.
- Active safe-mode behaviour when reliability is degraded or unavailable.
- Explicit reason codes and full decision trace.
- Simulated dispatch, acknowledgement, and re-escalation states.
- One excellent end-to-end Kannada electrical-emergency scenario.
- Before/after safety evaluation with workload and false-escalation metrics.
- Corrected cascade mechanics before new impact figures are produced.
- Updated README, limitations, static assets, and Streamlit story.

### Explicit non-goals

- Do not replace the deterministic classifier with an LLM.
- Do not add voice recognition for Round 1.
- Do not build real-time geocoding.
- Do not claim nearest geographic asset equals true feeder connectivity.
- Do not build a production rollback platform.
- Do not build another generic monitoring dashboard.
- Do not build a database, authentication system, or real municipal integration.
- Do not add vulnerability/underserved-area scoring without credible data.
- Do not present assumed time-to-failure or population values as predictions.
- Do not create more disconnected charts merely to increase feature count.

---

## 6. Required technical architecture

Keep the existing pure-function architecture. Add only two new core modules unless a clear
need appears:

```text
src/
├── cascade.py                 # corrected physical cascade engine
├── d2_language.py             # existing classifier; old guard retained as baseline
├── decision_firewall.py       # NEW: safety scan, asset context, policy, action plan
├── evaluate_firewall.py       # NEW: deterministic comparative evaluation
├── build_graph.py             # existing graph builder
├── d1_cascade.py              # regenerate corrected visual outputs
├── d1_robustness.py           # rerun after cascade correction
├── d3_dashboard.py            # legacy problem illustration only
└── d4_intervention.py         # legacy analysis; remove from primary app/deck

data/
├── complaints.csv             # preserve the existing D2 experiment
├── scenarios.csv              # NEW: explicit complaint-to-asset demo mappings
└── processed/                 # preserve existing graph and tables

outputs/
├── firewall_evaluation.csv    # NEW
├── firewall_decisions.csv     # NEW, one auditable decision per evaluation case
├── firewall_comparison.png    # NEW primary evidence chart
├── decision_trace.json        # NEW canonical demo trace
└── existing D1/D2/D3/D4 files # retain until replacements are verified
```

Do not delete legacy scripts or outputs during the initial migration. First build and verify
their replacements; then remove legacy items only from the primary navigation, README story,
PPT, and video. Keeping old artifacts in the repository preserves provenance and comparison.

---

## 7. Data contracts

### 7.1 Existing complaint data

Preserve `data/complaints.csv` and its current fields:

| field | meaning |
|---|---|
| `id` | stable complaint identifier |
| `text_en` | synthetic English complaint |
| `text_native` | equivalent Kannada complaint in native script |
| `true_dept` | evaluation ground truth |

The complaint dataset remains synthetic and small. It measures this prototype only; it does
not estimate real municipal performance.

### 7.2 New scenario mapping

Add `data/scenarios.csv` rather than contaminating the language experiment with invented
location data.

Required schema:

| field | meaning |
|---|---|
| `scenario_id` | stable scenario identifier |
| `complaint_id` | foreign key into `complaints.csv` |
| `language` | `en` or `native` |
| `condition` | `clean`, `truncated`, or `small_model` |
| `asset_id` | selected existing graph asset |
| `asset_mapping_method` | `scenario_selected`, `reported_asset`, or `nearest_demo_only` |
| `structured_hazard` | explicit intake hazard such as `sparking` |
| `structured_immediate_danger` | boolean |
| `provenance` | normally `synthetic_scenario` |
| `notes` | judge-facing scenario explanation |

At least one canonical scenario must map a Kannada electrical-emergency complaint to a
high-criticality Bengaluru substation. The UI and documentation must say that this is a
scenario-selected mapping, not evidence that the original complaint occurred there.

### 7.3 Firewall input

`decision_firewall.py` should accept a plain dictionary with this conceptual schema:

```python
{
    "complaint_id": str,
    "original_text": str,
    "language": "en" | "native" | "unknown",
    "structured_hazards": list[str],
    "immediate_danger": bool,
    "predicted_dept": str,
    "prediction_margin": int | float | None,
    "classifier_input_complete": bool,
    "asset_id": str | None,
    "asset_criticality_percentile": float | None,
    "simulated_people_exposed": int | None,
    "dependent_hospitals": int | None,
    "dependent_water_assets": int | None,
    "proposed_sla_hours": float | None,
    "scenario_failure_window_hours": float | None,
    "reliability_state": "normal" | "degraded" | "unavailable",
}
```

Avoid classes unless genuine persistent state becomes necessary. Pure functions returning
plain dictionaries/dataframes match the existing repository style and are easy to test.

### 7.4 Firewall output

Every evaluation must return:

```python
{
    "risk_level": "green" | "yellow" | "red",
    "action": "automatic_route" | "human_verification" | "emergency_dispatch",
    "final_department": str,
    "ai_autonomy_allowed": bool,
    "human_review_required": bool,
    "dispatch_immediate": bool,
    "reason_codes": list[str],
    "reason_text": list[str],
    "missing_fields": list[str],
    "provenance": dict[str, str],
}
```

Reason codes must be stable so they can be evaluated and rendered without parsing prose.

---

## 8. Independent multilingual safety scan

Implement in `src/decision_firewall.py`:

```python
def detect_safety_hazards(
    original_text: str,
    language: str,
    structured_hazards: list[str] | None = None,
) -> dict[str, object]:
    """Detect explicit hazards independently of the AI classification path."""
```

Requirements:

- Reuse the existing English and Kannada safety vocabularies where valid.
- Expand only with terms present in the controlled complaints or explicitly documented by
  the team; do not tune hidden terms solely to improve the final metric.
- Scan the complete original text, never `condition_input()`'s truncated text.
- Combine textual hits with structured hazards from the intake form.
- Return matched terms, normalized hazard categories, and whether an immediate-danger signal
  exists.
- Preserve both the text hit and its language for the audit trace.
- Escape all complaint and OSM text before rendering it as HTML.

Suggested normalized hazards:

```text
electrical_sparking
live_wire
electric_shock
fire_or_burning
burst_pipe
active_flooding
unknown_immediate_danger
```

The structured intake path is important. A citizen or call-centre operator should be able to
mark “sparks/fire/exposed wire/immediate danger” without relying on free-text NLP.

---

## 9. Asset context and criticality

Implement:

```python
def build_asset_context(
    graph,
    asset_id: str | None,
    criticality: pandas.DataFrame,
    config: dict,
) -> dict[str, object]:
    """Return consequence context for the selected/reported asset."""
```

Required behaviour:

- Validate that the asset exists in the graph.
- Look up the asset's rank and percentile from a full criticality ranking, not only the
  committed top-10 CSV.
- Include simulated cascade size and dependent-asset counts.
- Preserve provenance separately for location, topology, capacities, population, and outcome.
- Return `context_available=False` when the asset is missing or invalid.
- Never silently select the most critical substation when a mapping is missing.
- “Nearest asset” may be offered only as a clearly labelled demo fallback. Geographic
  proximity is not confirmed electrical connectivity.

Use relative criticality in the decision policy. Suggested policy tiers:

- `very_high`: top 10% of substations by simulated consequence;
- `high`: next 15%;
- `normal`: remaining assets;
- `unknown`: context unavailable.

These percentile boundaries are policy assumptions and must live in `config.yaml`.

Prefer “simulated exposure” or “simulated service population affected” over “people who will
be affected.” The current population values are independently sampled per substation and may
not represent unique people.

---

## 10. Risk policy

Implement:

```python
def assess_risk(
    firewall_input: dict[str, object],
    safety_result: dict[str, object],
    asset_context: dict[str, object],
    policy: dict[str, object],
) -> dict[str, object]:
    """Assign Green, Yellow, or Red and return explicit reason codes."""
```

### 10.1 Mandatory Red overrides

Assign **Red** when any configured high-consequence combination is true. At minimum:

1. structured immediate danger is true;
2. fire, live wire, shock, or active sparking is detected and the affected department is
   electrical;
3. an electrical emergency is predicted/routed into a non-critical department and a direct
   electrical hazard is detected;
4. a direct hazard affects a `very_high` criticality asset;
5. the proposed repair SLA reaches or exceeds the scenario failure window while direct danger
   or high asset consequence exists; or
6. the reliability state is degraded/unavailable and a direct safety hazard exists.

Red action:

```text
final department: appropriate emergency department
dispatch: immediate simulated dispatch/work order
human review: required in parallel
AI autonomy: denied
```

### 10.2 Yellow conditions

Assign **Yellow** when no Red override fired and any of these is true:

- classifier output is empty/unparseable;
- prediction margin is below the configured threshold;
- classifier input was truncated or incomplete;
- asset context is required but unavailable;
- system reliability is degraded or unavailable;
- department and hazard signals conflict;
- asset criticality is `high`; or
- another required field is missing.

Yellow action:

```text
AI route: recommendation only
final routing: waits for human verification
AI autonomy: denied
```

Do not reuse the old 48-hour verification time as if it were a validated service level. If a
review target is shown, put it in `config.yaml` and label it as an assumed prototype policy.

### 10.3 Green conditions

Assign **Green** only when all required context is present and:

- no direct safety hazard is detected;
- the classifier output is parseable;
- the uncertainty signal clears the configured threshold;
- reliability state is normal;
- no dangerous downgrade exists;
- asset consequence is normal or not relevant to the complaint; and
- no missing-data fail-safe applies.

Green action:

```text
final department: classifier recommendation
dispatch: normal routing
human review: not required
AI autonomy: allowed
```

### 10.4 Dangerous downgrade

Do not define dangerous downgrade from prediction correctness alone. It occurs when the true
or independently detected hazard indicates a time-critical category while the predicted route
has a materially slower SLA/non-critical response.

During evaluation, ground truth may be used to measure whether the controller caught a
dangerous downgrade. At runtime/demo decision time, the controller must use the independent
safety evidence rather than hidden ground truth.

### 10.5 Reason codes

Support at least:

```text
DIRECT_HAZARD
STRUCTURED_IMMEDIATE_DANGER
DANGEROUS_DOWNGRADE
LOW_MARGIN
UNPARSEABLE_CLASSIFICATION
TRUNCATED_CLASSIFIER_INPUT
VERY_HIGH_ASSET_CRITICALITY
HIGH_ASSET_CRITICALITY
REPAIR_WINDOW_AT_RISK
RELIABILITY_DEGRADED
RELIABILITY_UNAVAILABLE
ASSET_CONTEXT_MISSING
CONFLICTING_SIGNALS
SAFE_AUTOMATION_ALLOWED
```

The UI must display plain-language explanations generated from these codes.

---

## 11. Active safe mode

The existing canary is not the product. It becomes one possible input to a system-reliability
state that changes behaviour.

Implement:

```python
def reliability_state_from_canary(
    report: pandas.DataFrame | None,
    language: str,
    condition: str,
    config: dict,
) -> str:
    """Return normal, degraded, or unavailable."""
```

Behaviour:

- `normal`: ordinary policy applies;
- `degraded`: relevant complaints cannot become Green automatically;
- `unavailable`: relevant complaints cannot become Green automatically;
- degraded/unavailable plus direct danger: force Red;
- degraded/unavailable without danger: Yellow minimum.

In the app, this may be demonstrated with a clear state toggle or derived from the existing
controlled canary result. Do not build a separate monitoring page. Show only the operational
effect:

```text
SAFE MODE ACTIVE
Kannada automatic routing restricted
Reason: controlled quality check is degraded
```

Do not claim continuous production monitoring. This prototype demonstrates a policy response
to a supplied reliability state.

---

## 12. Dispatch and acknowledgement

Implement deterministic action planning in `decision_firewall.py`:

```python
def build_action_plan(decision: dict[str, object], predicted_dept: str) -> dict[str, object]:
    """Convert the risk decision into a simulated operational action plan."""
```

Output should include:

```text
work_order_type
assigned_department
priority
requires_acknowledgement
human_review_parallel
status
next_action_if_unacknowledged
```

Required semantics:

- Green creates a normal routed ticket.
- Yellow creates a human-verification task and does not finalize an unsafe automatic route.
- Red creates an immediate simulated emergency work order and a parallel human-review task.
- Red requires acknowledgement.
- The demo must expose an “unacknowledged” state and show escalation to a supervisor/control
  room.
- Do not send real messages, create real tickets, or claim real integration.
- Any acknowledgement/re-escalation timing shown must be configured and labelled as an
  assumed prototype policy.

---

## 13. Correct the cascade model before regenerating evidence

The current cascade implementation redistributes every failed substation's full load on every
timestep. This repeatedly adds the same demand to neighbours and can amplify the cascade
artificially. The configured hospital and water buffers are also not applied.

These issues must be corrected before using regenerated impact numbers in the PPT.

### 13.1 One-time load shedding

Required invariant:

> A substation's carried load may be transferred at most once when that substation fails.

Implementation options:

- maintain `unshed_failed` / `shed_nodes`; or
- set the failed node's load to zero immediately after its one-time redistribution.

Newly failed nodes should redistribute their current load in the next propagation step. If no
live neighbour exists, record the load as unserved instead of silently duplicating or losing it.

Snapshots should expose enough state to test load conservation:

```text
live_load
unserved_load
load_shed_this_step
```

### 13.2 Hospital and water buffer states

Do not place dependent assets directly into a generic failed state when the feeder trips.

Use explicit states:

```text
healthy
on_backup
service_outage
```

- Hospital: feeder loss → `on_backup`; after configured generator buffer → `service_outage`.
- Pump/water asset: feeder loss → buffered; after configured reservoir/pump buffer →
  `service_outage`.
- “Hospitals on generator” counts backup state.
- “Hospitals without power” counts expired backup state.
- “Wards without water” counts only expired water-buffer state.

### 13.3 Recompute dependent outputs

After correcting the simulator, regenerate and review:

- `outputs/d1_criticality.csv`;
- both D1 scenario GIFs and frames;
- `outputs/d1_robustness.csv`;
- all app cascade outcomes;
- any new Decision Firewall impact comparison; and
- legacy D4 only if it remains in the appendix.

Never retain old headline numbers after changing the cascade mechanics.

### 13.4 Required simulator tests

Add tests for:

- caller graph is not mutated;
- failed load is shed exactly once;
- total transferred/live/unserved load obeys the declared conservation rule;
- no substation exceeds capacity without failing on the correct step;
- hospital and pump buffers expire on the correct timestep;
- a cascade terminates when no new state changes occur;
- criticality ranking is deterministic for a fixed graph/configuration.

---

## 14. Comparative safety evaluation

Implement `src/evaluate_firewall.py`. The purpose is to prove that the active controller
improves safety without merely escalating every complaint.

### 14.1 Configurations

Evaluate at least:

1. **AI only** — classifier route accepted automatically;
2. **Existing guard** — current uncertainty/safety-keyword guard retained as a baseline;
3. **Decision Firewall** — independent safety scan, consequence context, tiered action,
   fail-safe policy, and active reliability state.

The primary PPT can show AI only versus Decision Firewall if space is tight, but the CSV must
retain all evaluated configurations.

### 14.2 Evaluation matrix

Reuse the existing 20 complaints × 2 languages × 3 conditions where appropriate. Asset-based
impact metrics must be computed only for complaints with explicit scenario mappings. Do not
silently attach every complaint to the most critical asset.

### 14.3 Required metrics

Define and report:

| metric | definition |
|---|---|
| `dangerous_misroutes_allowed` | critical ground-truth cases automatically sent to a non-critical route |
| `dangerous_misroutes_intercepted` | dangerous AI routes blocked by Yellow or Red action |
| `critical_incident_catch_rate` | intercepted dangerous cases / all dangerous cases |
| `human_review_rate` | decisions requiring human review / all decisions |
| `emergency_dispatch_rate` | Red decisions / all decisions |
| `unnecessary_escalation_rate` | non-critical cases escalated beyond their required response |
| `safe_automation_rate` | correctly routed low-risk complaints handled automatically |
| `simulated_incidents_prevented` | mapped scenarios dispatched before their assumed failure window |
| `simulated_exposure_avoided` | mapped scenario consequence avoided under the declared model |

Every metric denominator must be shown. With only 20 complaints, counts such as `3/4` are more
honest than a percentage alone.

### 14.4 Required outputs

- `outputs/firewall_decisions.csv`: one row per case/configuration with prediction, factors,
  decision, reasons, and correctness.
- `outputs/firewall_evaluation.csv`: aggregated counts, rates, and denominators.
- `outputs/firewall_comparison.png`: a simple chart emphasizing dangerous misroutes caught,
  safe automation, and human-review trade-off.
- `outputs/decision_trace.json`: complete canonical demo scenario trace.

Do not headline the old “31% reduction” unless it survives the corrected simulation and is
still explicitly labelled as dependent on an assumed prevention rate. Prefer direct,
deterministic Firewall evaluation metrics.

---

## 15. Streamlit application redesign

The app should feel like an intervention tool, not four disconnected analysis pages.

### Recommended navigation

```text
1. Live intervention        # primary demo
2. Evidence                 # compact comparative metrics
3. Scenario explorer        # optional cascade exploration
4. Methodology & limitations
```

### 15.1 Live intervention page

This is the default and most important page. It must show one continuous trace:

1. original bilingual complaint;
2. optional structured hazard answers;
3. what the degraded classifier saw;
4. AI prediction and uncertainty signal;
5. independent hazard detections from the original complaint;
6. scenario-selected/reported asset and mapping provenance;
7. asset criticality and simulated consequence;
8. reliability/safe-mode state;
9. Green/Yellow/Red Firewall decision;
10. explicit reason codes in plain language;
11. simulated work order and acknowledgement status; and
12. AI-only versus Firewall physical outcome.

The most visually prominent card must be the action:

```text
RED — IMMEDIATE EMERGENCY DISPATCH
AI route overridden
Human review running in parallel
```

### 15.2 Evidence page

Show the comparative safety metrics and one concise methodology note. Include both benefit
and operational cost:

- dangerous misroutes intercepted;
- unnecessary escalation rate;
- human-review rate;
- safe automation rate; and
- simulated outcome for mapped scenarios.

Move the full language accuracy table, bootstrap intervals, robustness sweep, and old D4
analysis into expandable methodology/appendix sections.

### 15.3 Scenario explorer

Keep the existing map and criticality capability, but do not make the full ranking table the
main product. Use the explorer as supporting evidence that consequence depends on which asset
is affected.

### 15.4 Methodology and limitations

Retain the project's strong provenance discipline. Clearly distinguish:

- observed OSM locations;
- inferred topology;
- assumed capacity/load/population/SLA values;
- synthetic complaints and scenarios;
- measured prototype-classifier outputs; and
- simulated cascade outcomes.

### 15.5 UI elements to remove or demote

- Remove the live all-green monitor from the main solution flow. It may appear once as a
  compact problem illustration.
- Remove the standalone canary dashboard. Replace it with an active safe-mode state affecting
  the Firewall decision.
- Remove the hardware-hardening comparison from primary navigation.
- Demote full criticality and language charts to Evidence/Methodology.
- Do not show synthetic HTTP logs as if they are operational evidence.
- Do not lead with accuracy. Lead with the unsafe decision being overridden and acted upon.

---

## 16. Canonical winning demo

Create one stable, rehearsable scenario and make it the default app state.

### Scenario

```text
A citizen submits a Kannada complaint reporting a sparking transformer.
The selected degradation condition causes the classifier to route it as routine maintenance
or return an unparseable result.
The complete original complaint still contains a detectable electrical hazard.
The complaint is scenario-mapped to a high/very-high criticality Bengaluru substation.
The proposed routine SLA reaches the assumed equipment-failure window.
The Decision Firewall assigns Red.
An emergency electrical work order is created immediately.
Human review runs in parallel.
The acknowledgement step confirms or re-escalates the work order.
The AI-only branch permits the initiating failure; the Firewall branch intervenes before it.
```

### Required split-screen result

```text
AI ONLY
Wrong/routine route
Delayed response
Initiating failure occurs
Corrected cascade simulation runs

DECISION FIREWALL
Danger independently detected
High consequence identified
Immediate emergency action
Human review in parallel
Initiating failure prevented under the stated scenario assumption
```

### Safe-mode moment

Allow the presenter to switch the reliability state from normal to degraded. The resulting
effect must be behavioural, not merely visual:

```text
Kannada routing reliability degraded
        ↓
Automatic routing restricted
        ↓
Uncertain Kannada complaints become Yellow
        ↓
Direct-danger Kannada complaints become Red
```

---

## 17. PPT and video story

The presentation must position Silent Cascade as an infrastructure-safety and dispatch
solution, not an AI observability product.

### Recommended slide sequence

1. **Physical consequence:** one delayed infrastructure fault can cascade.
2. **Hidden cause:** a critical Kannada complaint was technically processed but routed poorly.
3. **Why current systems fail:** uptime/latency monitoring cannot authorize a safe response.
4. **Solution:** Silent Cascade Decision Firewall architecture.
5. **Action policy:** Green/Yellow/Red and “unknown is not low risk.”
6. **Live scenario:** complete decision trace and explicit override reasons.
7. **Before/after outcome:** AI-only cascade versus immediate Firewall intervention.
8. **Evidence:** caught-dangerous-route, false-escalation, review-load, and safe-automation
   metrics.
9. **Feasibility:** deterministic rules, existing grievance/GIS integration points, no model
   replacement required.
10. **Honest scope and next step:** scenario-based prototype today; utility/municipal pilot and
    real data required for validation.

### Remove from the headline story

- “We monitor AI degradation.”
- The all-green dashboard as a proposed solution.
- The old 48-hour verification queue as the universal intervention.
- The ₹1.5L versus ₹85L comparison unless sourced and still relevant.
- The assumed 40% prevention rate as primary evidence.
- Claims that one substation collapses the entire Bengaluru network.
- Claims that the prototype continuously monitors or dispatches a real system.

### Final pitch wording

> Silent Cascade is a consequence-aware Decision Firewall for AI-routed civic complaints.
> AI handles routine cases, but when danger, uncertainty, missing data, or infrastructure
> consequence becomes high, the Firewall restricts AI authority, overrides unsafe routes,
> initiates the emergency action, and ensures that someone acknowledges the incident before a
> digital mistake becomes a physical cascade.

---

## 18. Configuration changes

Keep every numeric policy assumption in `config.yaml`. Add a documented `firewall` block. Do
not silently copy these example values; the team must confirm them before implementation.

Conceptual structure:

```yaml
firewall:
  criticality_percentiles:
    very_high: <team-confirmed percentile>
    high: <team-confirmed percentile>

  uncertainty:
    low_margin_threshold: <team-confirmed value>

  reliability:
    language_gap_degraded_pct: <existing or team-confirmed value>

  action_policy:
    yellow_review_target_hours: <team-confirmed assumed policy>
    red_acknowledgement_target_minutes: <team-confirmed assumed policy>
    red_reescalation_target_minutes: <team-confirmed assumed policy>

  mandatory_red_hazards:
    - electrical_sparking
    - live_wire
    - electric_shock
    - fire_or_burning
```

YAML placeholders must be replaced with valid values before running the app. Every such value
must be described as a prototype policy assumption unless supported by a named source.

Do not confuse classifier margin with calibrated confidence. The UI and documentation must
call it a **score margin** or **uncertainty signal**.

---

## 19. Testing requirements

Create a `tests/` directory and add focused unit tests. Avoid large snapshot tests that merely
freeze the current output.

### Firewall tests

- direct structured danger always produces Red;
- explicit electrical hazard plus non-emergency prediction produces Red;
- unparseable classification without direct danger produces at least Yellow;
- degraded/unavailable reliability prevents Green;
- missing required asset context prevents Green;
- clean low-risk complaint can remain Green;
- reason codes match the conditions that fired;
- runtime decision never reads `true_dept`;
- original-text safety scan still works when classifier input is truncated;
- Red produces immediate dispatch plus parallel review;
- Yellow does not create a finalized automatic route;
- unacknowledged Red action produces a re-escalation step.

### Evaluation tests

- metric denominators are correct;
- dangerous misroutes are counted from ground truth only in evaluation code;
- unnecessary escalation excludes true critical cases;
- “escalate everything” has poor safe-automation/false-escalation metrics;
- results are deterministic for a fixed dataset/configuration.

### App smoke tests

- canonical scenario renders without missing data;
- changing language/condition recomputes the decision;
- changing asset changes the consequence context;
- changing reliability state changes permitted autonomy;
- all displayed reason text is escaped;
- missing files produce actionable errors rather than silent defaults.

---

## 20. Implementation order

Follow this sequence so that new presentation claims are never built on invalidated outputs.

### Phase 0 — Preserve and baseline

1. Record current output metrics and screenshots as legacy references.
2. Do not delete existing data or outputs.
3. Add tests around current pure functions where possible.

### Phase 1 — Correct physical consequence model

1. Fix one-time load shedding.
2. Implement hospital/water buffer states.
3. Add simulator invariants and tests.
4. Regenerate D1 and robustness outputs.
5. Review whether the canonical asset remains high criticality.

### Phase 2 — Build Decision Firewall core

1. Create `src/decision_firewall.py`.
2. Implement original-text safety scan.
3. Implement asset-context lookup.
4. Implement reliability-state input.
5. Implement deterministic Green/Yellow/Red policy.
6. Implement reason codes and action plan.
7. Add Firewall unit tests.

### Phase 3 — Add canonical scenario

1. Create `data/scenarios.csv`.
2. Map one Kannada emergency complaint to an existing high-criticality asset.
3. Label mapping and all scenario values as synthetic/assumed.
4. Generate `outputs/decision_trace.json`.

### Phase 4 — Build comparative evidence

1. Create `src/evaluate_firewall.py`.
2. Evaluate AI only, existing guard, and Decision Firewall.
3. Produce counts and rates with denominators.
4. Produce a compact comparison chart.
5. Review false-escalation and human-review trade-offs.

### Phase 5 — Redesign Streamlit app

1. Make Live Intervention the default page.
2. Connect complaint, classifier, original-text safety scan, asset context, risk decision,
   action plan, acknowledgement, and physical outcome.
3. Add active safe-mode behaviour.
4. Move detailed analytics to Evidence/Methodology.
5. Remove D3 and D4 from primary navigation.

### Phase 6 — Refresh submission material

1. Update `README.md` to describe the Decision Firewall.
2. Update `LIMITATIONS.md` with the corrected model and new claim boundary.
3. Update `docs/STREAMLIT_APP.md` after the app is finalized.
4. Replace stale screenshots, charts, GIFs, and numeric claims.
5. Build the PPT/video around the canonical intervention scenario.

---

## 21. Acceptance criteria

The new implementation is complete only when all of the following are true.

### Solution behaviour

- A dangerous Kannada complaint can be misclassified by the controlled classifier but still
  intercepted using independent original-text/structured hazard evidence.
- Asset criticality changes the risk decision when appropriate.
- Green, Yellow, and Red produce materially different operational actions.
- Red dispatch is immediate and human review is parallel.
- Missing context cannot silently become Green.
- Degraded reliability actively restricts AI autonomy.
- Every non-Green decision explains why it occurred.
- An unacknowledged Red action visibly re-escalates.

### Evidence

- Comparative evaluation includes AI only, existing guard, and Decision Firewall.
- It reports dangerous misroutes, catch rate, false escalation, review rate, and safe automation.
- All denominators are visible.
- Scenario-based cascade impact is labelled simulated.
- No old D4 assumption is presented as measured Firewall effectiveness.

### Technical credibility

- Failed substation load is shed only once.
- Hospital and water buffers affect state transitions.
- Tests cover cascade invariants and Firewall policy.
- No runtime LLM or external AI API is required.
- No network call is required at runtime except external map tiles in the interactive UI;
  cached data remains sufficient for all computations.
- A fresh environment can install pinned/compatible dependencies and run the app and offline
  evaluation.

### Presentation

- The first solution screen shows an action, not a monitor.
- One canonical scenario tells the entire story end to end.
- The all-green dashboard is only a brief problem visual.
- The final pitch uses “Decision Firewall,” “AI authority,” “immediate action,” and
  “acknowledgement,” not merely “monitoring degradation.”
- Limitations remain visible and specific.

---

## 22. Hard constraints and honesty rules

- Python 3.10+.
- Core logic must remain pure and testable; plotting/UI stay separate.
- Keep fixed seeds for reproducible experiments.
- No runtime LLM calls.
- No real municipal dispatch, alert, or ticket mutation.
- No new dependency without a demonstrated need.
- Pin compatible dependency versions before final submission.
- Cache OSM source data; do not re-fetch during the demo.
- Treat OSM names and complaint text as untrusted when generating HTML.
- Fail loudly on missing required data; do not silently pick a high-impact asset.
- Every displayed quantity must be labelled as one of:
  - **Observed** — e.g. OSM asset existence/location;
  - **Inferred** — e.g. proximity-based topology;
  - **Assumed** — e.g. capacity, SLA, failure window, policy threshold;
  - **Synthetic** — e.g. complaints and scenario mapping;
  - **Measured** — results of the controlled classifier/Firewall evaluation;
  - **Simulated** — cascade and avoided-exposure outcomes;
  - **Cited** — backed by a named, linked source.
- Do not say the prototype predicts Bengaluru's real grid.
- Do not say it continuously monitors a production classifier.
- Do not say it dispatches a real repair crew.
- Do not say a simulated intervention “saved” a precise number of real people.
- Do not hide results that weaken the pitch; adjust the pitch instead.

---

## 23. What must remain from the previous plans

The following earlier decisions remain binding unless this document explicitly supersedes
them:

- Bengaluru remains the primary city because it matches the Kannada complaint experiment.
- OSM locations are observed; grid/supply topology is inferred.
- Capacities, loads, population served, buffer durations, SLAs, and failure windows are
  assumptions stored in `config.yaml`.
- The deterministic keyword classifier is an honest proxy, not a production LLM.
- The clean/truncated/small-model experiment and its raw results remain available.
- The small-model result that does not match the expected language-gap story must remain
  visible in methodology.
- Bootstrap confidence intervals and dangerous-downgrade metrics remain part of the evidence.
- The cascade engine stays graph-agnostic and does not mutate the caller's graph.
- Cached raw OSM data and provenance values must be preserved.
- Static outputs remain useful for the PPT/video even though the interactive app now exists.
- The project remains a scenario-based stress test, not a validated predictive system.

This document supersedes the original constraints that prohibited Streamlit and limited the
repository to static outputs; the existing Streamlit application is now part of the Round 1
demonstration.

---

## 24. Definition of the final claim

After implementation, the strongest defensible claim should be:

> In this controlled bilingual complaint set and simulated infrastructure scenario, a
> deterministic consequence-aware Decision Firewall intercepts dangerous routes that an
> AI-only workflow would allow, initiates a safer response for high-consequence cases, and
> preserves automatic routing for eligible low-risk cases. The physical-impact result is
> simulated and requires real municipal and utility data for validation.

That is stronger and more defensible than claiming merely that AI degradation can be
monitored, or that an assumed checkpoint prevents a fixed percentage of failures.

---

## 25. When implementation choices are uncertain

Do not guess at:

- new SLA, acknowledgement, or re-escalation targets;
- changes to the city or canonical asset;
- risk-policy thresholds that will appear in the PPT;
- adding or deleting complaint/hazard terms after seeing evaluation results;
- whether a location-to-asset mapping is reported, inferred, or scenario-selected;
- any number presented as real-world effectiveness; or
- any destructive removal of existing outputs.

Ask the team, record the choice in `config.yaml`, and label its provenance. Everything shown
to judges must be reproducible from committed inputs and code.
