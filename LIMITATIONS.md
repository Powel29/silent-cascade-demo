# Limitations, Assumptions & What This Prototype Actually Proves

This document exists because a fair reviewer should not have to dig through code comments to
find out what is real. Read it before the deck, not after a judge asks. It describes the
**Decision Firewall** implementation and the **corrected** cascade engine; every number below
was regenerated from that engine. No figure from the earlier (uncorrected) prototype is reused.

## The one claim this prototype supports

> In this controlled bilingual complaint set and simulated infrastructure scenario, a
> deterministic consequence-aware Decision Firewall intercepts dangerous routes that an AI-only
> workflow would allow, initiates an emergency-speed response for every critical case, and
> preserves automatic routing for most eligible low-risk cases under clean input. The
> physical-impact result is simulated and requires real municipal and utility data for
> validation.

**This is scenario-based stress testing of a hypothesis, not a validated predictive model of
Bengaluru's grid or grievance system.** No real dispatch data, real feeder topology, or real AI
classifier was available on a hackathon timeline, and this document does not pretend otherwise.

## What is Observed, Inferred, Assumed, Synthetic, Measured, Simulated or Cited

| Item | Status | Detail |
|---|---|---|
| Substation (190), hospital (1,060) and pump (157) locations | **Observed** | OpenStreetMap, cached in `data/raw/`; no runtime fetch |
| Grid topology (which substation feeds which) | **Inferred** | 3-nearest-neighbour by haversine; nearest substation feeds each hospital/pump. Not real feeder topology |
| Capacity, load, population served | **Assumed** | Seeded uniform draws, `config.yaml: assumptions`; population values are independent per substation and are **not unique people** |
| Hospital generator buffer (8 h), water buffer (6 h), 2 h timestep, 12-step horizon | **Assumed** | `config.yaml: assumptions`, `d1.max_steps` |
| Department SLAs, 336 h failure window, 48 h legacy verification window | **Assumed** | `config.yaml: d2.sla_hours`, `d2.time_to_failure_hours`. The 48 h figure was once attributed to UPPCL (Uttar Pradesh); no verified BESCOM/BWSSB figure exists |
| Firewall thresholds, criticality tiers, review/acknowledgement/re-escalation targets | **Assumed** | `config.yaml: firewall`, flagged `confirmed_by_team: false` — placeholders chosen so the prototype runs end to end |
| Complaints (20 × English/Kannada) | **Synthetic** | hand-written, `data/complaints.csv` |
| Complaint-to-asset mappings (7 scenarios) | **Synthetic** | `data/scenarios.csv`, `asset_mapping_method = scenario_selected`. A mapping is not evidence that the complaint occurred at that asset |
| Classifier predictions, hazard-scan hits, Firewall decisions, evaluation counts | **Measured** | on this prototype: `outputs/d2_results.csv`, `outputs/firewall_decisions.csv`, `outputs/firewall_evaluation.csv` |
| Cascade outcomes, criticality ranking, simulated exposure | **Simulated** | `src/cascade.py`, deterministic for the fixed graph and seed 42 |
| AI grievance routing is deployed in Indian cities; native-script languages underperform English | **Cited** | Delhi IGMS + IIT Kanpur, NextGen CPGRAMS; IndicQuest / IndicParam / IndicKLAR — see `silent-cascade-plan.md` §1.1 |

## What changed in the physical model, and what it did to the numbers

The earlier engine re-shed every failed substation's **full** load on **every** timestep and
ignored the configured hospital/water buffers. That amplified cascades artificially. The
corrected engine (`src/cascade.py`, tested in `tests/test_cascade.py`):

- transfers a failed substation's carried load **exactly once**, in the step after it fails;
  if no live neighbour remains the load is recorded as **unserved**, never duplicated;
- conserves load at every snapshot (`live + unserved + pending == initial`);
- moves hospitals and pumps through `healthy → on_backup → service_outage`, with the outage
  only after the configured buffer has elapsed; "hospitals on generator" counts backup state,
  "hospitals without power" counts expired backup, "wards without water" counts expired water
  buffers;
- terminates when nothing changes and nothing is pending, or at the 12-step (24 h) horizon.

Consequences, all regenerated:

- The top-ranked substation is now **ITI (sub_171)**: 110 substations tripped and 2,918,254
  simulated service population exposed within 24 h. The former number one (MUSS NGEF) is now
  rank 145 of 190.
- The large cascade is still **horizon-bounded**: the top-ranked runs are still growing at
  step 12, so "exposure" means "within the simulated 24 h", not the eventual extent.
- The robustness sweep (`outputs/d1_robustness.csv`) is now **more cautious**: under the
  default assumptions (k=3, load 55–75 % of capacity) the worst single substation affects
  62.5 % of nodes, but under 6 of the 9 tested parameter combinations the worst failure stays
  contained to about 3 % of nodes. Impact remains concentrated (top vs. median ratio 11.7×–176×)
  in every combination, which is the only property the relative criticality tiers depend on.
  **Cascade size is highly sensitive to the assumed headroom. Nothing collapses the whole
  network.**
- The legacy D4 hardening-vs-checkpoint table was rerun for provenance only (baseline
  174,195; hardened 173,857; checkpoint 99,268 mean simulated exposure over 100 runs). Its
  checkpoint result still depends on an **assumed 40 % prevention rate** and is not Firewall
  evidence; it is kept in the Evidence appendix and nowhere in the headline story.

## What the Firewall evaluation shows — benefit and cost

`python src/evaluate_firewall.py` scores 120 cases (20 complaints × 2 languages × 3 classifier
conditions). Ground truth (`true_dept`) is read **only** in `src/evaluate_firewall.py`;
`src/decision_firewall.py` raises if it is passed. Counts with denominators, from
`outputs/firewall_evaluation.csv`:

| metric | AI only | Existing guard | Decision Firewall |
|---|---|---|---|
| Dangerous AI routes intercepted | 0 / 9 | 9 / 9 | **9 / 9** |
| Dangerous AI routes allowed through | 9 / 9 | 0 / 9 | **0 / 9** |
| Critical cases with an emergency-speed response (≤ 24 h) | 15 / 24 | 18 / 24 | **24 / 24** |
| Correct low-risk routes kept automatic (safe automation) | 83 / 83 | 73 / 83 | 27 / 83 |
| Decisions needing human review (workload) | 0 / 120 | 25 / 120 | 93 / 120 |
| Unnecessary escalations (correct low-risk route, still escalated) | 0 / 83 | 10 / 83 | 56 / 83 |
| Mapped critical scenarios: initiating failure prevented | 3 / 4 | 4 / 4 | 4 / 4 |

Reference rows in the CSV: *Firewall, safe mode off* (75 / 120 review, 45 / 83 safe
automation) and *Escalate everything* (120 / 120 review, 0 / 83 safe automation).

Read this honestly:

- **The existing guard already blocks the 9 dangerous misroutes.** What it does not do is act:
  6 critical cases sit in a 48 h verification queue. The Firewall's distinctive benefit is the
  **immediate emergency action with parallel review** for every critical case, driven by the
  independent scan of the *original* complaint — the truncated Kannada sparking-transformer
  complaint is unparseable to the classifier and still Red to the Firewall.
- **The workload cost is real and mostly by design.** Under the *truncated* condition every
  case is at least Yellow because the classifier provably saw an incomplete complaint; under
  *small_model* the controlled quality check reports degraded reliability and safe mode
  withdraws automatic routing. Under *clean* input the Firewall keeps 27 of 32 correct low-risk
  routes automatic (`outputs/firewall_evaluation_by_condition.csv`). Whether that trade-off is
  acceptable is a municipal policy decision, and the thresholds that set it are configurable.
- **Under the assumed 336 h failure window the guard's 48 h queue also prevents the initiating
  failure.** The Firewall's advantage on the simulated-cascade metric is therefore *not* the
  14-day window; it is the emergency-speed response for people standing next to a sparking
  transformer. We report both rather than picking the flattering one.
- **The reliability signal is circular in this prototype.** The golden-set canary that sets
  `normal / degraded / unavailable` uses the same 20 complaints as the evaluation. In a real
  deployment the golden set must be separate; the Firewall reacts to a *supplied* state and
  does not continuously monitor a production classifier.
- **The hazard vocabulary is small and keyword-based.** Every term is either from the earlier
  safety vocabulary or appears verbatim in the controlled complaints; nothing was added after
  seeing results. Known artefacts kept visible: Kannada "ಒಡೆದ" (broken/burst) also matches a
  broken footpath (c17) and produces one Yellow conflict flag; Kannada active flooding is
  reachable only through the structured intake path.
- **Structured intake answers are not used in the evaluation** (free text only), so the
  measured result reflects the text scan alone. The structured path is an additional safeguard
  demonstrated in Live Intervention and in `outputs/decision_trace.json`.
- **Response times are assumed, and the two code paths model Yellow differently on purpose.**
  Red is the 4 h emergency response in both. For Yellow, `evaluate_firewall.py` uses the review
  target (24 h, assumed) plus the *correct* department's SLA, which is legitimate in evaluation
  code and assumes the verifier always corrects the route. The runtime path in
  `decision_firewall.py` cannot see ground truth, so it uses the review target plus the SLA of
  the route a verifier would most plausibly confirm, inferred from runtime evidence only: a
  detected service hazard's department, else the AI's suggested department, else the configured
  fallback queue. It deliberately does **not** assume every Yellow is upgraded to the emergency
  queue; doing so would understate the response time and overstate how often the Firewall beats
  the failure window for complaints that carry no hazard.
- With n = 20 complaints per cell, every rate is directional. `outputs/d2_accuracy.csv`
  still carries 95 % bootstrap intervals for the classifier itself, and the small-model
  condition still shows no Kannada gap (75 % vs 70 %) — reported, not tuned away.

## Answering the hardest questions directly

**"What proves the AI error causes the physical failure?"** Nothing observed — that link is
assumed (`time_to_failure_hours`) and labelled so everywhere. What is defensible: each link has
real precedent (misrouting is measurable on this classifier; delayed repair → equipment failure
is how overloaded electrical plant fails), and the simulation shows what follows *if* the
assumed link holds.

**"Isn't the Firewall just escalating everything?"** No — but it escalates a lot under injected
degradation, and the numbers above say so. Compare the *Escalate everything* reference row: the
Firewall keeps automatic routing where the policy allows it and, unlike the guard, it never
leaves a critical case in a queue.

**"How real is the network?"** Locations are real; everything else is inferred or assumed, and
the corrected robustness sweep shows cascade *size* depends heavily on those assumptions.

**"Does the prototype dispatch anything?"** No. Work orders, acknowledgements and
re-escalations are a simulated state machine with assumed timings; nothing is sent anywhere.

## What would make this a validated system instead of a stress test

A real feeder topology and loads from the utility; real dispatch and repair-time data; a
separate golden set for the reliability check; team-confirmed policy thresholds and review /
acknowledgement targets; a production classifier in place of the keyword proxy; and a live
pilot measuring actual routing decisions against outcomes over months rather than a synthetic
20-complaint set.
