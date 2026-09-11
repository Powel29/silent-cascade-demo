# SILENT CASCADE
### Manipal Hackathon (M#) — Full Plan, Round 1 → Round 2
**Version 2 — corrected**

**Problem Statement:** Cascading Failure: When One Failure Becomes Many
**Domain:** Disaster Resilience & Critical Infrastructure
**SDG:** 11 — Sustainable Cities and Communities
**Theme:** The Butterfly Effect

---

# ⚠️ SECTION 0 — UNRESOLVED FACTS

**Four things must be confirmed before this plan is usable. Fill these in first.**

| # | Question | Answer | Why it matters |
|---|---|---|---|
| 1 | Round 1 **submission** deadline (NOT registration close) | ________ | Determines which timeline in §A.6 applies |
| 2 | Are you registered? | ________ | If registration closes Sept 15, this is step zero |
| 3 | Team size | ________ | Determines how much of M1–M6 is achievable |
| 4 | Does MPPKVVCL GIS portal load + export? | ________ | Determines real vs synthetic physical layer |

> **Known:** Registration for Round 1 opened Aug 30 and closes Sept 15.
> **Unknown:** whether submission is also Sept 15 or later. These are usually different dates.
> **Today is Sept 11.** If submission is Sept 15, you have 4 days — use Timeline A in §A.6.

**Also verify from the rulebook before investing in Part B:**
- Round 2 statements release Oct 7 in the same Domain + SDG as your Round 1 pick, but as a NEW problem
- When Round 1 results are announced
- Whether team members must appear on camera in the video

---

## 0.1 Strategic frame

If the Round 2 structure above is correct, the design rule that drives everything is:

> Do not build a one-scenario demo. Build a **reusable, config-driven cascade engine**
> with swappable networks, failure types, and impact metrics.

Whatever Round 2 throws at you will be Disaster Resilience + SDG 11 — some network, some
disruption, some propagation, some urban impact. A generic engine means you walk into
Round 2 with a working system while others start from zero.

## 0.2 The one-sentence pitch

> Cities monitor every physical asset. Nothing monitors the AI that decides which asset
> gets fixed first — and that AI degrades silently, worst on the citizens least able to escalate.

## 0.3 The delete test (statement-fit insurance)

*If I delete the AI layer, is there still a valid infrastructure cascade project?*
The answer must always be **yes**. The physical simulator stands alone; the AI layer is an
additional initiating-event class.

---

# SECTION 1 — EVIDENCE BASE

**Citations are tiered by strength. Lead with Tier 1 on slides. Attribute Tier 3 honestly
or omit it.**

## 1.1 TIER 1 — Strong, primary, checkable

| Fact | Source |
|---|---|
| Delhi launched an AI grievance system (IGMS) with IIT Kanpur — department prediction, automatic routing, spam filtering, semantic search, root-cause analysis, OCR | Delhi Govt / IIT Kanpur, Dec 2025 |
| National scale: classification engines assign every complaint topic, urgency and destination; speech-to-text across 22 languages; Bhashini across text, voice, WhatsApp, kiosks | NextGen CPGRAMS |
| Complaints reach field officers who verify and assign teams; escalation supervisor → zonal → Executive Engineer → CGRF; **48-hour SLA** | UPPCL published process |
| Water boards run centralised control rooms coordinating head office with field staff, complaints in any Indian language, docket tracking | KUWSDB CCRRC |
| Gateway fallback handles provider errors and operational failures — **not low-quality answers that still return successfully** | LLM gateway comparison, 2026 |
| Error compounding: 99% per-step accuracy → 36.6% at 100 steps | Six Sigma Agent, arXiv 2026 |
| In a hardened agent runtime with 4,286 automated tests and 827 governance checks, ~70% of silent failures surfaced only when a human looked at the output | Longitudinal study, 2026 |
| Denser topologies spread errors more; chain structures reduce propagation by up to 19% | Multi-agent information propagation, arXiv |
| English consistently outperforms all Indic languages on all metrics; tiers — Moderate (Hindi, Marathi) / Low (Kannada, Telugu, Tamil, Bengali, Gujarati, Punjabi, Assamese) / Extremely Low (Manipuri, Sindhi, Odia, Urdu) | IndicQuest |
| Frontier models hit a strict ceiling below 45% on extremely low-resource Indic languages | IndicParam |
| Native-script tier degrades severely vs English — gaps up to ~0.50 | IndicKLAR |
| Water supply, water quality and drainage are the most reported problems among the urban poor in Ahmedabad slums | J. Social & Economic Development, 2026 |

## 1.2 TIER 3 — Weak sourcing. Attribute or omit.

| Claim | Problem | Handling |
|---|---|---|
| "91% of production LLMs drift within 90 days" | Traces to a vendor (InsightFinder) via a blog post | Say "vendor-reported" or **drop it** — Tier 1 stats are stronger |
| "14–18 day detection lag" | Same chain | Same |
| "23% accuracy drop over 30 days at normal latency" | Practitioner anecdote | Use as illustration, not evidence |

> **Rule:** if a judge could check it and find a blog, don't put a number on a slide.
> You have enough Tier 1 material to carry the argument without these.

## 1.3 CORRECTION carried from earlier drafts

Evidence on **code-mixing** is split — one study found code-mixed scores approach English
(within ~0.05), effectively bypassing the low-resource penalty; another found romanized
code-mixed input IS harder. **Build the equity argument on native-script regional languages
only.** That gap is large and undisputed.

## 1.4 Physical network data

| Source | Contents | Status |
|---|---|---|
| **MPPKVVCL (Madhya Pradesh)** — PRIMARY | Distribution GIS portal: feeders, substations, lines | **VERIFY DAY 0** |
| **KSEB (Kerala)** — BACKUP A | Substation and line registers 2024–25 | Published |
| **WBSETCL (West Bengal)** — BACKUP B | District substation register + single-line diagrams | Published |
| **OSM / Overpass API** — UNIVERSAL FALLBACK | Power lines, transformers, poles, substations | Always available |
| Census / ward boundaries | Population, vulnerability | Always available |

**City recommendation: Indore or Bhopal** — MPPKVVCL is the only listed Indian source with
**distribution-level** granularity, which is what a city cascade needs.

**If MPPKVVCL fails:** fall back to OSM Overpass for any city, synthesise feeder topology,
and label it clearly. A synthetic-but-labelled layer is acceptable. An unlabelled one is not.

## 1.5 Real vs synthetic — prepare this slide

You WILL be asked. Have the answer ready:

| Component | Source | Status |
|---|---|---|
| Substation locations | MPPKVVCL / OSM | Real |
| Feeder topology | MPPKVVCL, else inferred | Real or Inferred |
| Hospital locations | OSM | Real |
| Ward populations | Census | Real |
| Generator fuel / reservoir hours | Typical engineering values | Declared assumption |
| Complaint volumes & text | Synthetic | Synthetic |
| AI routing accuracy by language tier | Measured in our pipeline | Measured |
| Cascade outcomes | Simulated | Simulated |

Label every edge in the graph: **Observed / Declared / Inferred / Unknown.**

---

# SECTION 2 — ARCHITECTURE

## 2.1 Layer 1 — Physical network (BUILD FIRST)

**Nodes:** substations (capacity, load), feeders, water pumping stations (power dependency,
reservoir hours), hospitals (generator fuel hours, catchment), ward polygons (population,
vulnerability index)

**Edges:** electrical feed, water supply, road access (matters for crews and fuel delivery)

**Propagation (time-stepped):**
```
t=0    substation trips
t+Δ    load redistributes to adjacent substations
t+2Δ   any substation over capacity trips
t+3Δ   dependent water pumps lose power
t+Nh   reservoir reserve depletes → ward loses supply
t+Mh   hospital generator fuel depletes → critical care at risk
```

**Key design choice:** buffers are **durations**, not booleans. "Redundancy for 8 hours" is
a different statement from "redundancy exists" — and no existing tool makes it.

## 2.2 Layer 2 — AI control layer

**Pipeline:** intake → language normalisation → classification → urgency scoring → routing → queue

**Silent degradation injection types** (nothing returns an error):

| Type | Real trigger |
|---|---|
| Model version swap | Provider ships update, no changelog |
| Context truncation | Long complaint exceeds window under load |
| Cheap-model routing | Traffic spike triggers cost-based routing |
| Stale retrieval index | Department taxonomy changed; index didn't |
| Non-equivalent fallback | Backup responds but can't do structured tool calls |

## 2.3 The coupling

```
AI routing output
  → department + urgency
    → dispatch queue position
      → repair delay (SLA days)
        → increased physical failure probability
          → PHYSICAL CASCADE
```

**Never claim automated crew dispatch.** Your cascade runs on **delay**, which is fully evidenced.

## 2.4 Four properties that make it a cascade, not a chain

1. **Branching** — fan-out at routing into multiple departments and assets
2. **Load redistribution** — misroutes saturate the general-works queue, delaying
   *correctly routed* complaints too. Collateral spread is the defining feature.
3. **Feedback** — unresolved → re-filed → load up → cheap-model routing → more misroutes
4. **Cross-layer** — delayed repair → transformer fails → feeder trips → pump stops →
   households dry → hospital on generator

---

# SECTION 3 — MODULES AND CUT ORDER

| # | Module | Purpose | Round |
|---|---|---|---|
| **M1** | Physical network + cascade engine | Statement-fit insurance. Standalone. | R1 |
| **M2** | Time-aware impact & criticality | People-hours lost, not centrality | R1 |
| **M3** | AI layer + degradation injector | The novelty | R1 |
| **M4** | Cross-layer criticality ranking | **The headline finding (slide 12)** | R1 |
| M5 | Equity lens | Inclusivity pillar | R1 if time |
| M6 | Intervention comparison | Butterfly payoff | R1 if time |
| M7 | Fallback-equivalence tester | Extended novelty | R2 |
| M8 | Topology hardening recommender | Structural fixes | R2 |
| M9 | Multi-hazard scenario library | R2 reusability | R2 |

## ⚠️ CORRECTED CUT ORDER

**Cut in this order:** M5 → M3 extra injection types → M6
**Irreducible core: M1, M2, M3 (one injection), M4**

> *Correction from v1, which wrongly listed M4 as cuttable. M4 produces slide 12 —
> "the most critical asset isn't a substation." Cutting M4 removes the pitch.*

**Never cut M1.** It is what keeps you inside the problem statement.

## 3.1 Scaling by team size

| Team | Realistic scope |
|---|---|
| **2 people** | M1 + M2 only. Deck describes M3–M6 as roadmap. No prototype. |
| **3 people** | M1 + M2 + M3 (one injection). M4 charted in deck, not coded. |
| **4 people** | M1–M4 coded. M5/M6 in deck. |
| **5+** | Full M1–M6. One person owns deck+video from Day 1. |

> One person must own the deck and video **from the start**, not as an afterthought.
> Pillar 5 is pass/fail and pillars 3–4 live entirely in the deck.

---

# PART A — ROUND 1 SUBMISSION

## A.1 Scoring position

| Pillar | Your position |
|---|---|
| 1. Innovation | **Strong** — new initiating-event class |
| 2. Feasibility | **Good** — real data, phased roadmap, inclusivity built in |
| 3. Marketing | **Good** — clear buyers, publishable launch asset |
| 4. Monetisation | **Weakest** — lead with certification, not consulting |
| 5. Format | **Free points — do not lose these** |
| 6. Prototype | Bonus. Never sacrifice the deck for it. |

## A.2 Format compliance — DO TODAY

- [ ] Download the mandatory presentation template
- [ ] Max slide count
- [ ] Video max duration
- [ ] Video resolution / aspect ratio / format
- [ ] **Must team members appear on camera?**
- [ ] File naming convention
- [ ] Submission portal + deadline **with time zone**
- [ ] Must the prototype link be public or access-gated?

## A.3 Deck — slide by slide

**SLIDE 1 — Title.** Silent Cascade. *"The city's most critical asset isn't a substation."*
Team, members, problem statement ID, SDG 11 badge.

**SLIDE 2 — Open on the human.** A citizen reports a sparking transformer. Voice complaint,
regional language, evening. No AI mentioned yet.

**SLIDE 3 — The consequence.** Fourteen days later it failed. Feeder tripped → pumping
station stopped → N households lost water → hospital on generator. *(Mark as simulated.)*

**SLIDE 4 — No alarm fired.** Complaint acknowledged. Ticket created. Status green. SLA
nominally met for the category it was assigned to.

**SLIDE 5 — The blind spot.** Cities monitor every asset. Nothing monitors what decides
**which asset gets fixed first.** Cite Delhi IGMS + IIT Kanpur, 22-language national scale.
*This is deployed today.*

**SLIDE 6 — Why nothing catches it.** Monitoring watches whether the AI *answered*, not
whether it was *right*. Cite gateway fallback limitation (Tier 1). Cite 4,286-test study (Tier 1).

**SLIDE 7 — The network we modelled.** The REAL graph. Name data sources. Show the
real-vs-synthetic table from §1.5. *This slide proves it's an infrastructure project.*

**SLIDE 8 — Cascade demo A: equipment failure.** Substation trips. Time-stepped spread.
*Establishes the simulator is real before the twist.*

**SLIDE 9 — A new class of initiating event.** Physical · Environmental · Operational ·
**AI degradation.** The five silent injection types. Nothing crashes. Every response is a valid 200.

**SLIDE 10 — Cascade demo B: same cascade, nothing broke.** No equipment failed. One silent
quality drop. Same endpoint. **Show the monitoring dashboard: all green.** Full slide.

**SLIDE 11 — It isn't equal.** Stratified by language tier and ward vulnerability. Cite
IndicQuest tiers + Ahmedabad slum study. *The citizens failed first cannot escalate.*

**SLIDE 12 — The headline finding.** Cross-layer criticality, one scale.
*"The highest-criticality asset here is a classification node — it sits upstream of every
dispatch decision, and unlike a substation, nothing monitors whether it's working correctly."*

**SLIDE 13 — Intervention comparison.** Harden a substation: ₹₹₹, Z% reduction. One
verification checkpoint: ₹, Z'% reduction. Let the data say "butterfly effect" — don't say it.

**SLIDE 14 — SDG 11 mapping.**

| Target | Link |
|---|---|
| 11.1 Access to basic services | Misrouted complaints = undocumented denial of service |
| 11.3 Inclusive participatory urbanisation | A channel that drops regional-language complaints isn't participatory |
| 11.5 Reduce people affected by disasters | Degraded classification during flooding = wrong zone prioritised |
| 11.b Integrated disaster risk management | Pre-deployment stress testing of AI in city emergency systems |

**SLIDE 15 — Why not existing tools.**

| Category | What they do | Difference |
|---|---|---|
| Gremlin, AWS FIS, Azure Chaos Studio | Inject outages | We inject *wrongness* |
| Datadog, Dynatrace, CloudWatch | Monitor infrastructure | They watch the request, not the answer |
| Braintrust, Galileo, Traceloop | Monitor LLM quality in production | **They monitor AFTER. We simulate BEFORE.** |
| Academic cascade simulators | Model equipment failure | We add an initiating class the field treats as out of scope |

> The tense is the differentiator: smoke detector vs fire drill.

**SLIDE 16 — Roadmap, market, revenue, limits, team.**

*Roadmap:* open-data simulator → municipal sandbox pilot → continuous pre-deployment gate.

*Market:* municipal IT, Smart Cities Mission offices, state DISCOMs, state disaster
management authorities, govtech vendors bidding on tenders.

*Revenue (all figures ₹):*
1. **Certification badge** — vendors cite "Silent Cascade tested" in tenders *(lead with this)*
2. Per-city audit engagement *(fits procurement cycles)*
3. Subscription pre-deployment gate
4. Open core + paid civic scenario packs

*Honest limits:* scenario-based stress testing, not prediction. Relative comparison of
interventions. Every assumption labelled. Synthetic data marked.

## A.4 Video script (assume 3 min — CONFIRM ACTUAL LIMIT)

| Time | Content | Visual |
|---|---|---|
| 0:00–0:20 | A citizen reports a sparking transformer. No tech. | Person, phone, evening |
| 0:20–0:40 | Fourteen days later it failed. Households dry. Hospital on generator. | Cascade animation, physical only |
| 0:40–1:00 | No alarm fired. Every dashboard green. | Green dashboard, held |
| 1:00–1:20 | Nothing monitors what decides which asset gets fixed. Delhi IGMS is live. | Citation on screen |
| 1:20–2:00 | **Demo.** Run A: substation trips. Run B: nothing breaks, one silent drop, same outcome. | Screen recording, split |
| 2:00–2:20 | It isn't equal. Language-stratified routing accuracy. | Bar chart, stark |
| 2:20–2:40 | Most critical asset is a classification node. One checkpoint beats hardening a substation. | Ranking + comparison |
| 2:40–3:00 | *"You cannot defend infrastructure you monitor perfectly if the thing deciding what to repair is invisible."* | Title card, SDG 11 |

**Production notes**
- Pre-record demo runs at high resolution; don't screen-record live during narration
- Subtitle everything — judges may watch muted
- One voice throughout
- Hold the green-dashboard shot 3 full seconds in silence
- Export, watch on a phone, re-check text legibility
- **If team members must appear on camera, budget an extra 90 minutes**

## A.5 Prototype (bonus)

**Minimum for bonus:** M1 + M2 + visible interactive cascade.
**Differentiator:** M3 with ONE injection, end-to-end traced.

**Stack:** Python + NetworkX (graph/propagation) · GeoPandas + OSMnx/Overpass (spatial) ·
Streamlit or simple React (UI). Single deployable — judges won't install dependencies.

**Hosting:** Streamlit Community Cloud or Hugging Face Spaces. **Test the link from a phone
on mobile data before submitting.**

## A.6 TIMELINES — pick the one matching your actual deadline

### ⏱ TIMELINE A — Submission Sept 15 (4 days from Sept 11)

**Prototype is OFF the table. Deck + video only.**

| Day | Task |
|---|---|
| **Sept 11** | Confirm deadline. Download template. Test MPPKVVCL. Assign: 1 person deck, 1 video, rest data. |
| **Sept 12** | Pull OSM Overpass for chosen city. Build a SIMPLE M1 — 20–30 nodes, hand-checked. Slides 1–8. |
| **Sept 13** | Run one cascade. Screenshot everything. Slides 9–16. M3 conceptual only — describe, don't build. |
| **Sept 14** | Record + edit video. Full deck review against all 6 pillars. |
| **Sept 15** | Format check. Submit with hours to spare, not minutes. |

**What you sacrifice:** measured numbers (mark all as projected), M4–M6 (chart them),
prototype bonus. **What you keep:** the full argument, all Tier 1 evidence, the demo
narrative via mockup rather than live tool.

### ⏱ TIMELINE B — Submission ~Sept 22 (≈10 days)

Use the day-by-day in v1: Day 0 verify → M1 → M2 → M3 → M6 → deck → video → buffer.
Prototype achievable with 4+ people.

### ⏱ TIMELINE C — Submission Oct or later

Full M1–M6 plus early Part B refactoring. Test the engine on a second city to prove
portability before Round 1 even closes.

> **Whichever applies: reserve the final full day as buffer. Do not plan to submit on the last working day.**

---

# PART B — ROUND 2 *(CONDITIONAL — verify §0 first)*

## B.1 The premise to verify

If Round 2 releases Oct 7 with the same Domain + SDG but a **new specific problem**, then
you are not extending Round 1 — you are applying your capability to a new problem.

**Re-read the rulebook yourself before investing the Sept 16 – Oct 6 window.** Also confirm
when Round 1 results are announced; refactoring before you know you've advanced is
speculative work.

## B.2 Build for generality

| Component | Must be swappable via |
|---|---|
| Network topology | Config file / data import, not code |
| Node types & attributes | Schema definition |
| Propagation rules | Pluggable rule modules |
| Initiating events | Event-type registry |
| Impact metrics | Metric plugin |
| Hazard footprints | Geospatial layer import |

**Target:** stand up a working simulation on a new problem in under 24 hours by supplying
new *data*, not new *code*.

## B.3 Likely Round 2 shapes — pre-build hedges

Given Disaster Resilience + SDG 11, expect one of:

1. **Hazard event** (flood, cyclone, earthquake) hitting urban infrastructure
2. **Recovery / restoration sequencing** after disruption
3. **Early warning** and alert propagation
4. **Resource allocation** under constraint
5. **Equity of service restoration** across communities

Hedges: flood-footprint overlay · repair-crew restoration sequencer · alert routing by ward
and language · multi-hazard comparison on one network. Each is a thin layer on M1–M2 if
you refactored properly.

## B.4 New modules

**M7 — Fallback-equivalence tester.** A backup that responds is not a backup. Test whether
it supports the same tool calls, context length, schema fidelity, safety behaviour, latency
budget, data-residency rules. This is false redundancy — and unlike the telecom version
(SRLG, solved since ~2000), the AI version is genuinely unclaimed.

**M8 — Topology hardening recommender.** Denser topologies spread errors more; chains cut
propagation ~19%. Turn into recommendations: sparser delegation, verification checkpoints
at high-fan-out nodes, consensus at critical joins.

**M9 — Multi-hazard scenario library.** See B.3.

## B.5 What Round 2 demands that Round 1 didn't

- A **working system**, not a concept. Prototype moves from bonus to expectation.
- Evidence you tested it — run it on more than one network.
- Deployment realism: who operates this, what onboarding looks like, what the city provides.
- **Every illustrative figure from Round 1 must now be measured.**

## B.6 Round 2 timeline *(if premise confirmed)*

| Window | Focus |
|---|---|
| Sept 16–22 | Refactor M1–M6 for genericity. Config-driven everything. |
| Sept 23–30 | Build M7 + M8 |
| Oct 1–6 | M9 library. Test engine on a SECOND city to prove portability. |
| **Oct 7** | **New statement releases. Read carefully.** |
| Oct 8–9 | Map new problem onto engine. Identify the delta. |
| Oct 10+ | Build the delta. Measure. Document. Submit. |

---

# SECTION 4 — DISCIPLINE RULES

## Always
- Open on **physical consequence**, never on AI
- Label every edge: **Observed / Declared / Inferred / Unknown**
- Build equity on **native-script** regional languages
- Say "scenario-based stress testing," "relative comparison of interventions"
- Mark simulated numbers as simulated
- Use ₹, not $ or £

## Never
- "We predict hallucinations"
- "We prevent AI failure"
- "We replace observability"
- Let an LLM invent a dependency and present it as fact
- Present illustrative numbers as measured results
- Put a Tier 3 statistic on a slide

## Rehearsed answers

**"Isn't this just LLM evals?"**
> "Evals score a model in isolation. We propagate a degraded model's decision through a
> physical infrastructure network and measure households without water — stratified by who
> those households are. No eval does that."

**"Isn't this just another cascade simulator?"**
> "Every cascade simulator models equipment failure. We found a failure class that leaves no
> trace in any monitoring system and sits upstream of every repair decision in the city."

**"Do Indian cities actually use AI for this?"**
> "Delhi launched an AI grievance system with IIT Kanpur in December 2025 with automatic
> department routing. Nationally, classification engines assign topic, urgency and destination
> across 22 languages. Deployed, not hypothetical."

**"Isn't your cascade speculative?"**
> "The link from misrouting to repair delay is documented — field officers assign teams, and
> SLAs like UPPCL's 48-hour window are published. We model delay, not automated dispatch.
> We're explicit about that boundary."

**"How much of your data is real?"**
> *(Show the §1.5 table.)* "Substations, hospitals and ward populations are real. Feeder
> topology is inferred where the utility portal doesn't publish it. Complaint data is
> synthetic. Every edge in our graph carries a provenance label."

---

# SECTION 5 — RISK REGISTER

| # | Risk | Severity | Mitigation |
|---|---|---|---|
| 1 | **Deadline is Sept 15, not later** | **Critical** | §0 verify TODAY. Switch to Timeline A. |
| 2 | Not registered before Sept 15 close | **Critical** | Register today |
| 3 | MPPKVVCL portal dead or gated | High | Verify Day 0. Backups: KSEB, WBSETCL, OSM+synthetic labelled |
| 4 | Scope overrun | High | Cut order M5 → M3 extras → M6. Never M1. Scale by team size (§3.1) |
| 5 | Read as an AI project, not infra | High | Delete test. Slides 7–8 before any AI mention |
| 6 | Team too small for scope | High | §3.1 scaling table. Decide now, not Day 6 |
| 7 | Tier 3 stat challenged by judge | Medium | Use Tier 1 only on slides |
| 8 | Monetisation scores low | Medium | Lead with certification badge |
| 9 | Format violation | Medium | §A.2 checklist, re-check on final day |
| 10 | Part B premise wrong | Medium | Verify rulebook before Sept 16 investment |
| 11 | Illustrative numbers challenged | Medium | Measure or mark clearly |

---

# SECTION 6 — DO THIS IN THE NEXT HOUR

1. ☐ **Confirm the Round 1 submission deadline** (not registration close)
2. ☐ **Confirm you are registered** — registration closes Sept 15
3. ☐ **Count your team** → apply §3.1 scaling
4. ☐ **Open the MPPKVVCL GIS portal** — does it load? export?
5. ☐ **Download the mandatory template**
6. ☐ Assign owners: M1 · deck · video

**Then pick your timeline from §A.6 and start.**

---

*Version 2. Corrections from v1: cut order fixed (M4 is core, not cuttable) · currency
corrected to ₹ · citations tiered by strength · backup data sources added · real-vs-synthetic
table added · team-size scaling added · timeline made conditional on verified deadline ·
Part B marked conditional.*

*Re-verify all citation links before submission.*
