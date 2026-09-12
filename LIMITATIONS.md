# Limitations, Assumptions & What This Prototype Actually Proves

This document exists because a fair reviewer should not have to dig through code comments to
find out what's real. Read this before the deck, not after a judge asks.

## The one claim this prototype supports

> A routing-layer decision failure that returns HTTP 200 can, if uncorrected, coincide with a
> physical asset's failure window — and a cheap decision-layer checkpoint is, under the stated
> assumptions, a more cost-effective place to intervene than hardening one piece of hardware.

Everything else in the submission — the map, the animation, the dashboard mock — is context
for that one claim. It is not four co-equal, independently-proven findings. If you remove any
one of D1/D2/D3/D4, this claim still stands or falls on D2 (measured) + D4 (simulated,
sensitivity-tested); D1 and D3 illustrate consequence and rhetoric, respectively.

**This is scenario-based stress testing of a hypothesis, not a validated predictive model of
Bengaluru's actual grid or its actual grievance system.** No real municipal dispatch data,
real feeder topology, or real AI classifier was available for a hackathon timeline, and this
document does not pretend otherwise.

## What's Cited, Assumed, Simulated, or Measured

| Link in the causal chain | Status | Detail |
|---|---|---|
| Municipal AI grievance routing is deployed in Indian cities today | **Cited** | Delhi IGMS + IIT Kanpur (Dec 2025); NextGen CPGRAMS (22-language classification/routing nationally) — PLAN.md §1.1 |
| Misrouted complaints reach field officers on a published SLA | **Cited, but not for this city** | UPPCL (Uttar Pradesh) publishes a 48h verification SLA; we do not have a verified BESCOM/BWSSB (Karnataka) equivalent, so `verification` in `config.yaml`'s `sla_hours` is now treated as an **assumption**, not a citation |
| Other departments' repair SLAs (14-day maintenance window, etc.) | **Assumed** | Illustrative municipal SLA values, `config.yaml: d2.sla_hours` |
| Native-script languages underperform English in AI systems generally | **Cited** | IndicQuest tiers, IndicParam, IndicKLAR — PLAN.md §1.1 (Kannada is "Low" tier, not "Extremely Low") |
| *This* keyword-baseline classifier underperforms on Kannada under truncation | **Measured** | 120 real classifications, `outputs/d2_results.csv`; 95% bootstrap CI reported alongside every accuracy figure because n=20 per cell is small — see below |
| Repair delay → equipment physically fails at a specific hour | **Assumed** | `time_to_failure_hours` in `config.yaml`, the "fourteen days later" narrative compressed into one number. No observed failure-rate curve exists for this. |
| Substation capacity, load, population served | **Assumed** | Seeded uniform draws, `config.yaml: assumptions` — no feeder-level utility data was available |
| Feeder topology (grid edges) | **Inferred** | 3-nearest-neighbour by haversine distance — not real feeder topology, which utilities do not publish at this granularity |
| Cascade propagation given the above | **Simulated** | `src/cascade.py`, deterministic given the graph and seed — see robustness section below for whether this is sensitive to the inferred/assumed inputs |
| Verification-checkpoint prevention rate (40%) | **Assumed** | `config.yaml: d4.verification_checkpoint_prevention_rate` — see sensitivity sweep below for how much this matters |
| Intervention costs (₹85L hardening, ₹1.5L checkpoint) | **Assumed** | Order-of-magnitude, not vendor quotes |

## Answering the five hardest questions directly

**1. "What evidence proves the AI error causes the physical failure?"**
None — that specific causal link is *assumed*, not observed, and this document says so above.
What's defensible instead: (a) the individual links each have real-world precedent (misrouting
happens, measurably, on this classifier; delayed repair→failure is physically how overloaded
electrical equipment fails); (b) the simulation shows what follows *if* the assumed link holds,
which is a legitimate way to stress-test a hypothesis before it's validated, not a substitute
for validation.

**2/4. "How real is this network, and how much do the D4/D1 numbers depend on one assumption?"**
Two robustness checks exist specifically to answer this rather than asserting one number:
- **`src/d1_robustness.py`** rebuilds the graph across 9 combinations of topology (KNN k=2,3,4)
  and load-headroom assumptions, and checks whether "impact is concentrated in a small number
  of substations" — the property the whole criticality ranking (and D4's "harden the top-
  ranked node") depends on — holds regardless of the exact parameters. Result:
  `outputs/d1_robustness.csv` — the top-ranked substation affects **2.1x to 240x** as many
  nodes as the median substation across all 9 combinations tested. The finding that criticality
  is concentrated, not uniform, is robust. What is **not** claimed: that any single substation's
  failure collapses the entire network — the worst case tested affects at most ~97% of nodes
  under an aggressive parameter choice, not literally all of them, and under the *actual*
  parameters used elsewhere in this repo (k=3, headroom 0.55–0.75) it's 67%.
- **`src/d4_intervention.py`'s `sensitivity_sweep()`** re-runs the checkpoint-vs-hardening
  comparison at prevention rates from 10% to 60%, not just the headline 40%. Result:
  `outputs/d4_sensitivity.csv` — the checkpoint beats hardening down to a **10% prevention
  rate**, the lowest tested. The 31%-reduction headline number is specific to 40%, but the
  *qualitative* conclusion (cheap decision-layer fix beats expensive hardware fix) does not
  depend on that specific value.

**3/5. "Why generalize from 20 synthetic complaints, and don't errors have different severities?"**
We don't generalize the point estimate. `outputs/d2_accuracy.csv` and the app's Language
Routing page report a **95% bootstrap confidence interval** next to every accuracy figure
(`bootstrap_ci()` in `src/d2_language.py`) — with n=20 per cell those intervals are wide, and
the page says so explicitly. Treat the finding as directional, not a population estimate of
real Kannada-routing accuracy. Separately, `dangerous_downgrade_rate()` answers the "not all
errors are equal" critique directly: instead of plain accuracy, it measures what fraction of
genuinely time-critical complaints (`electrical_emergency`, the only department with a
config.yaml SLA ≤24h) get downgraded to a non-critical queue. On the current data, that rate is
**0% in clean conditions and reaches 100% for critical Kannada complaints under truncation** —
a sharper and more honest number than aggregate accuracy.

## What would make this a validated system instead of a stress test

Real municipal dispatch/repair-time data; a real feeder topology from the utility; a production
LLM classifier instead of a keyword baseline; and a live pilot measuring actual routing
decisions against actual outcomes over months, not a synthetic 20-complaint set. None of that
is achievable on a hackathon timeline, which is why this document exists instead of a bigger
claim.
