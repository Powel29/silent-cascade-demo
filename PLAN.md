# PLAN.md — Context

Why this repo exists. `CLAUDE.md` has the build spec; this explains what each asset is for.

## The project

**Silent Cascade** — Manipal Hackathon (M#), Round 1.
Problem statement: *Cascading Failure: When One Failure Becomes Many*.
Domain: Disaster Resilience & Critical Infrastructure. SDG 11. Theme: The Butterfly Effect.

## The argument we are making

Cities monitor every physical asset — substations, pumps, hospitals. Nothing monitors the
**AI layer that decides which asset gets fixed first**. That layer is deployed today in
Indian cities, it degrades silently with no error signal, and it degrades worst on the
citizens least able to escalate.

The chain we demonstrate:

```
citizen complaint (regional language, voice)
  → AI classification + routing
    → department assignment + urgency
      → dispatch queue position
        → repair delay
          → physical asset fails
            → CASCADE through power and water
              → households without water, hospital on generator
```

## Two rules that govern everything

**1. Open on physical consequence, never on AI.**
Judges must register this as an infrastructure project. The deck shows the real network and
a real equipment-failure cascade (slides 7–8) *before* AI is mentioned (slide 9).

**2. The delete test.**
If you removed the AI layer entirely, would there still be a valid infrastructure cascade
project? The answer must stay **yes**. That is why D1 is built first and built properly —
it is the submission's backbone, not a supporting visual.

## What each asset has to prove

### D1 — Cascade animation
**Proves:** we built a real infrastructure simulator on real geography.

This is the credibility anchor. If it looks like an abstract graph toy, the whole submission
reads as an AI project wearing an infrastructure costume. Real lat/lon, recognisable city
shape, visible time-stepped spread.

The `criticality_ranking()` output matters as much as the animation. Slide 12 claims that a
classification node outranks every substation in criticality — that claim is meaningless
unless we can show the actual substation ranking it beats.

### D2 — Language experiment
**Proves:** the equity claim, with measured numbers rather than assertions.

This is the most defensible thing in the submission because it is a real experiment we ran,
not a statistic borrowed from a paper. Four numbers — English clean, English degraded,
native-script clean, native-script degraded.

**Native script only.** Published evidence on code-mixed/romanized input is split; the
native-script gap is large and undisputed. Do not use Hinglish.

**If the result contradicts the pitch, report it honestly.** A team that says "we expected
a gap and found a smaller one" is more credible than one with suspiciously clean numbers.
Adjust the pitch, not the experiment.

### D3 — Dashboard mock
**Proves:** nothing technical. It is pure rhetoric, and it is the most memorable image in
the deck.

All-green monitoring beside a catastrophically wrong classification. Thirty minutes of work
for the shot the judges remember. It is a mock and we will say so if asked.

### D4 — Intervention comparison
**Proves:** the Butterfly Effect — smallest intervention, largest effect.

One verification checkpoint outperforming a hardened substation at a fraction of the cost.
Optional because the argument survives without it, but it is what turns an analysis into a
recommendation.

## Where the outputs go

| Asset | Deck | Video |
|---|---|---|
| D1 network plot | Slide 7 | — |
| D1 scenario_a GIF | Slide 8 | 1:20–1:40 |
| D1 scenario_b GIF | Slide 10 | 1:40–2:00 |
| D1 criticality CSV | Slide 12 | 2:20–2:30 |
| D2 chart | Slide 11 | 2:00–2:20 |
| D2 named examples | Slide 11 | 2:00–2:20 |
| D3 screenshot | Slides 4, 10 | 0:40–1:00 |
| D4 chart | Slide 13 | 2:30–2:40 |

## Honesty rules — non-negotiable

Every number that reaches a slide must be one of:
- **Measured** — we ran it (D2 accuracies, D1 cascade sizes)
- **Simulated** — output of our model on assumed inputs, labelled as such
- **Cited** — from a named source we can link

Nothing else. No illustrative figures presented as results.

Every graph edge carries a `provenance` label: `observed` / `inferred` / `synthetic`.
We do not have real feeder topology — our grid edges are inferred from proximity, and we
say so on the slide. Declaring a limitation costs nothing; being caught hiding one is fatal.

## What we are NOT claiming

- We do not predict hallucinations
- We do not prevent AI failure
- We do not replace observability tooling
- We do not claim AI automatically dispatches repair crews — we model **delay**, which is
  what the published evidence supports

## Scope boundary for Round 1

This repo produces **demo assets for a deck and video**. It is not a product, not deployed,
not interactive, and has no users.

If Round 2 follows (new problem, same domain and SDG), the cascade engine gets refactored
to be config-driven and reusable. **Write `cascade.py` with that future in mind** — pure
functions, graph-agnostic, no hardcoded city assumptions — but do not build for it now.
