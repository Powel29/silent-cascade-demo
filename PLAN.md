# PLAN.md — Silent Cascade Decision Firewall

This document explains the current product direction and Round 1 presentation strategy.
`CLAUDE.md` is the sole authoritative implementation specification.

Historical plans and existing output documents may describe the earlier monitoring-focused
prototype. When they conflict with this file or `CLAUDE.md`, follow `CLAUDE.md`.

---

## Project

- **Name:** Silent Cascade
- **Event:** Manipal Hackathon (M#), Round 1
- **Problem statement:** *Cascading Failure: When One Failure Becomes Many*
- **Domain:** Disaster Resilience and Critical Infrastructure
- **SDG:** UN SDG 11 — Sustainable Cities and Communities
- **Theme:** The Butterfly Effect

## Problem

Municipal grievance systems may use AI to classify complaints, assign departments, and set
urgency. A complaint can be processed successfully while the AI decision itself is unsafe.

A citizen may report a sparking transformer in Kannada. The system can return `200 OK` but
route the complaint to routine maintenance. The resulting delay can leave a dangerous asset
unrepaired and allow one failure to propagate through power, hospital, and water dependencies.

The core safety gap is not simply that an AI model can degrade. It is that a high-consequence
AI decision may be allowed to control operational action without an independent safety check,
an override, or confirmation that someone responded.

## Final solution

# Silent Cascade Decision Firewall

> A deterministic, consequence-aware safety and dispatch layer placed between AI complaint
> classification and municipal operations.

The AI recommends a route. The Decision Firewall determines how much authority the AI may
exercise by asking:

> If this decision is wrong, how dangerous is the consequence?

### Operational pipeline

```text
Citizen complaint + location + structured hazard answers
        ↓
AI department prediction and uncertainty signal
        +
Independent multilingual safety scan of the complete original complaint
        ↓
Affected infrastructure asset and criticality context
        ↓
Consequence-aware Decision Firewall
        ↓
GREEN  → automatic routing
YELLOW → rapid human verification before final routing
RED    → immediate emergency dispatch + human review in parallel
        ↓
Acknowledgement required for critical incidents
        ↓
Automatic re-escalation if nobody accepts the incident
```

## Why this solves the problem

The previous prototype mainly detected or illustrated unsafe AI behaviour. The Decision
Firewall changes the operational outcome:

- it reads danger signals independently of the AI prediction;
- it connects the complaint to the consequence of the affected infrastructure asset;
- it prevents uncertain or incomplete cases from being treated as low risk;
- it overrides unsafe routes;
- it initiates immediate action for critical cases;
- it requires acknowledgement; and
- it shows whether the initiating failure is prevented under the declared scenario.

The system is therefore an active safety controller, not an AI-monitoring dashboard.

## Existing work that remains valuable

- Bengaluru OSM infrastructure locations.
- Inferred graph topology and explicit provenance labels.
- Deterministic English/Kannada classifier.
- Twenty-complaint bilingual controlled experiment.
- Clean, truncated, and small-model conditions.
- Dangerous-downgrade metric and bootstrap intervals.
- Cascade map and criticality-ranking capability.
- Configuration-driven assumptions and seeded runs.
- Static assets for the PPT and video.

The deterministic classifier remains a controlled proxy for an AI routing layer. It is not
being replaced by an LLM.

## What changes from the previous solution

| Previous emphasis | Current direction |
|---|---|
| AI degradation monitoring | AI authority control and corrective action |
| Passive canary alarm | Active safe mode that restricts automatic routing |
| Confidence-only guard | Consequence-aware Green/Yellow/Red policy |
| Same degraded input checked twice | Independent scan of the complete original complaint |
| One verification queue | Tiered response with immediate Red dispatch |
| Routing as completion | Dispatch acknowledgement and re-escalation |
| Complaint and cascade shown separately | One complaint-to-asset-to-action-to-outcome trace |
| Hardware versus checkpoint comparison | AI-only versus Decision Firewall safety evaluation |
| Large analysis dashboards | One focused intervention demonstration |

## Round 1 build priorities

1. Correct the cascade engine's repeated load redistribution and implement buffer timing.
2. Build the independent multilingual safety scan.
3. Connect explicit scenario assets to full criticality context.
4. Implement deterministic Green/Yellow/Red policy and reason codes.
5. Add active safe mode, simulated dispatch, acknowledgement, and re-escalation.
6. Create one canonical Kannada electrical-emergency scenario.
7. Evaluate AI only, the old guard, and the Decision Firewall.
8. Redesign the Streamlit app around Live Intervention.
9. Regenerate valid outputs and refresh submission documentation.

The full data contracts, rules, file changes, tests, and acceptance criteria are defined in
`CLAUDE.md`.

## Required evidence

The submission must report both safety improvement and operational cost:

- dangerous misroutes allowed;
- dangerous misroutes intercepted;
- critical-incident catch rate;
- human-review rate;
- emergency-dispatch rate;
- unnecessary-escalation rate;
- safe-automation rate; and
- simulated impact avoided for explicitly mapped scenarios.

Counts and denominators must accompany percentages. A policy that escalates every complaint
is not a successful solution.

## Canonical demonstration

```text
Kannada complaint reports a sparking transformer
        ↓
Controlled degraded classifier proposes a routine or unparseable route
        ↓
Independent safety scan still detects the original hazard
        ↓
Scenario-selected asset has high simulated criticality
        ↓
Decision Firewall assigns RED
        ↓
Immediate simulated emergency work order
Human review in parallel
        ↓
Acknowledgement or re-escalation
        ↓
AI-only branch: delayed response and simulated cascade
Firewall branch: intervention before the initiating failure
```

The asset mapping, failure window, and physical consequence must be labelled synthetic,
assumed, or simulated as appropriate.

## PPT story

1. Physical consequence of one delayed infrastructure fault.
2. Hidden AI routing error behind a technically successful request.
3. Why uptime/latency monitoring cannot prevent the incident.
4. Decision Firewall architecture.
5. Green/Yellow/Red operational policy.
6. Complete live intervention trace.
7. AI-only versus Firewall physical outcome.
8. Comparative safety and workload metrics.
9. Feasibility and municipal/GIS integration points.
10. Honest limitations and next-step pilot.

The all-green dashboard may be used briefly to explain the blind spot. It must not be
presented as the solution.

## Non-goals

- No production LLM or external AI API.
- No voice-recognition feature for Round 1.
- No real dispatch or municipal-system mutation.
- No claim of confirmed feeder topology from geographic proximity.
- No generic monitoring product.
- No vulnerability scoring without credible data.
- No fabricated SLA, cost, prevention, or impact claims.
- No claim that the prototype predicts Bengaluru's actual grid.

## Honesty rules

Every value shown to judges must be labelled as:

- **Observed**
- **Inferred**
- **Assumed**
- **Synthetic**
- **Measured**
- **Simulated**
- **Cited**

The final claim must remain limited to the controlled complaint set and simulated
infrastructure scenario. Real-world effectiveness requires real municipal dispatch data,
confirmed utility topology, operational policy validation, and a live pilot.

## Documentation authority

Use documents in this order:

1. `CLAUDE.md` — current implementation specification.
2. `PLAN.md` — current product and presentation direction.
3. `LIMITATIONS.md` — claim boundary and provenance of the implemented Decision Firewall.
4. `README.md` — the runnable repository as implemented (Decision Firewall, corrected engine).
5. `docs/STREAMLIT_APP.md` — page-by-page description of the redesigned interface.
6. `silent-cascade-plan.md` — historical original planning and research notes only.
