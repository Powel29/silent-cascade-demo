# Silent Cascade: When Silent AI Degradation Triggers Physical Infrastructure Collapse

[![SDG 11: Sustainable Cities and Communities](https://img.shields.io/badge/SDG%2011-Sustainable%20Cities-orange.svg)](#)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](#)
[![Theme](https://img.shields.io/badge/Theme-The%20Butterfly%20Effect-red.svg)](#)

> **Manipal Hackathon (M#) — Round 1 Submission**  
> **Problem Statement:** *Cascading Failure: When One Failure Becomes Many*  
> **Domain:** Disaster Resilience & Critical Infrastructure (UN SDG 11)

---

## Executive Summary

Modern smart cities invest heavily in monitoring physical assets—electrical substations, distribution lines, water pumping stations, and emergency hospitals. However, almost **nothing monitors the AI routing layer** that decides which citizen grievances get escalated and repaired first.

In municipal grievance pipelines, AI triage systems can degrade silently:
1. A citizen logs an emergency grievance (e.g., an arcing transformer or fallen live wire) in a regional language (e.g., Kannada script).
2. The AI classifier silently misclassifies the urgency or department due to linguistic degradation, truncation, or low-capacity models.
3. The municipal ops system registers a successful **HTTP 200** with normal latency; all operational health dashboards stay **100% green**.
4. The ticket is assigned a low-priority routine maintenance SLA instead of emergency dispatch.
5. Days later, the physical asset fails under load, triggering a **cascading power grid overload and water supply blackout** across the city.

**Silent Cascade** proves this failure mode using real spatial infrastructure data from Bhopal, experimental linguistic routing benchmarks, a physical cascade simulator, and an intervention analysis illustrating the **Butterfly Effect**: a ₹1.5L human verification checkpoint on AI decisions prevents 5.8× more cascade impact than a ₹85L substation hardware hardening.

---

## The Failure Chain

```mermaid
flowchart LR
    A[Citizen Grievance\nRegional Language] --> B[AI Classification\n& Triage Layer]
    B -->|Silent Degradation\nStatus: 200 OK| C[Low-Priority SLA\nRoutine Queue]
    C --> D[Repair Delay\n14 Days Unattended]
    D --> E[Substation Tripped\nOverload]
    E --> F[Load Shedding to\nNeighbour Substations]
    F --> G[City-wide Blackout\nHospitals & Water Outages]
```

---

## Deliverables & Pipeline Architecture

The project produces four core demonstration deliverables (D1–D4) configured via [config.yaml](file:///d:/Powel/MIT/Projects/silent-cascade-demo/config.yaml):

| ID | Asset | Source Script | Primary Output | Description |
|---|---|---|---|---|
| **D1** | **Cascade Simulation** | [`src/d1_cascade.py`](file:///d:/Powel/MIT/Projects/silent-cascade-demo/src/d1_cascade.py) | [`outputs/d1_cascade_scenario_a.gif`](file:///d:/Powel/MIT/Projects/silent-cascade-demo/outputs/d1_cascade_scenario_a.gif), [`outputs/d1_criticality.csv`](file:///d:/Powel/MIT/Projects/silent-cascade-demo/outputs/d1_criticality.csv) | Physics-based load-redistribution failure cascade across Bhopal's spatial power and water network. |
| **D2** | **Language Experiment** | [`src/d2_language.py`](file:///d:/Powel/MIT/Projects/silent-cascade-demo/src/d2_language.py) | [`outputs/d2_chart.png`](file:///d:/Powel/MIT/Projects/silent-cascade-demo/outputs/d2_chart.png), [`outputs/d2_results.csv`](file:///d:/Powel/MIT/Projects/silent-cascade-demo/outputs/d2_results.csv) | Empirical benchmark of 120 triage decisions measuring accuracy gaps between English and Kannada under clean, truncated, and lightweight model conditions. |
| **D3** | **"All-Green" Ops Monitor** | [`src/d3_dashboard.py`](file:///d:/Powel/MIT/Projects/silent-cascade-demo/src/d3_dashboard.py) | [`outputs/d3_dashboard.html`](file:///d:/Powel/MIT/Projects/silent-cascade-demo/outputs/d3_dashboard.html) | Synthetic municipal telemetry UI demonstrating that service monitoring reports healthy status while fatal decision errors occur. |
| **D4** | **Intervention Analysis** | [`src/d4_intervention.py`](file:///d:/Powel/MIT/Projects/silent-cascade-demo/src/d4_intervention.py) | [`outputs/d4_comparison.png`](file:///d:/Powel/MIT/Projects/silent-cascade-demo/outputs/d4_comparison.png), [`outputs/d4_summary.csv`](file:///d:/Powel/MIT/Projects/silent-cascade-demo/outputs/d4_summary.csv) | Monte Carlo simulation (100 runs) comparing physical hardware hardening vs. an upstream AI verification checkpoint. |

---

## Guide to Main Output HTML Files

The project generates two key HTML files in the `outputs/` directory. Each serves a distinct analytical and presentation purpose:

```
outputs/
├── d3_dashboard.html          # Standalone CivicOps Monitor mockup
└── dashboard/
    ├── index.html             # Master interactive showcase & simulation dashboard
    └── assets/                # Rendered figures and animation assets
```

### 1. `outputs/dashboard/index.html` — Master Interactive Showcase Dashboard
This is the primary presentation application for judges and stakeholders. It is an interactive, dark-mode, single-page web dashboard integrating all project components into an exploratory experience:

* **Hero Section & Dynamic Network Mesh**:
  * Displays an animated, drifting spatial graph rendered on `<canvas>` showing the real geographic topology of Bhopal (27 substations, 295 hospitals, 103 water pumping stations).
* **Section 01 · The Problem Flow**:
  * An animated 7-stage interactive timeline tracking a complaint from regional voice intake to municipal SLA delay, asset trip, and critical buffer depletion.
* **Section 02 · Interactive Cascade Simulator**:
  * An interactive canvas map allowing users to scrub through timesteps ($T+0.0\text{h}$ to $T+18.0\text{h}$).
  * Live Head-Up Display (HUD) tracking **People affected**, **Hospitals on generator**, **Wards without water**, and **Substations tripped**.
  * Controls for Play/Pause, timestep scrubbing, playback speed (slow/normal/fast), zoom, pan, and network auto-fit.
* **Section 03 · "No Alarm Fired" Live Split Test**:
  * **Left Panel**: CivicOps Monitor showing real-time green telemetry (99.98% uptime, 187ms latency, 0.01% error rate).
  * **Right Panel (Degradation Injector)**: Interactive testbench allowing users to test 20 real complaints in English vs. Kannada across Clean, Truncated (40 chars), and Small-Model conditions, showing live HTTP 200 responses alongside misclassification verdicts.
* **Section 04 · "It Isn't Equal" Equity Benchmark**:
  * Visualizes the measured routing accuracy drop (100% clean $\to$ 55% truncated in Kannada vs. 90% in English).
  * Includes the data table and generated chart ([`outputs/dashboard/assets/d2_chart.png`](file:///d:/Powel/MIT/Projects/silent-cascade-demo/outputs/dashboard/assets/d2_chart.png)).
* **Section 05 · The Butterfly Effect (Intervention Comparison)**:
  * Compares **Baseline (366k affected)** vs. **Hardening Substation sub_003 (346k affected, ₹85 Lakhs)** vs. **AI Verification Checkpoint (252k affected, ₹1.5 Lakhs)**.
  * Shows that software-level verification achieves a **31.0% impact reduction at 1/50th of the cost**.
* **Section 06 · Provenance & Transparency Disclosure**:
  * An expandable 9-row disclosure detailing the scientific provenance of every metric, coordinate, and assumption in the pipeline.

---

### 2. `outputs/d3_dashboard.html` — CivicOps Monitor Standalone Mockup
This is a focused, standalone mockup of a municipal operations health monitoring center:

* **What it displays**:
  * **Metric KPI Cards**: Uptime (99.98%), p50 Latency (187ms), Error Rate (0.01%), and Throughput (1,240 req/min) with green sparklines.
  * **Service Health Matrix**: Microservice breakdown showing `operational` status for `intake-api`, `language-normaliser`, `classifier`, `urgency-scorer`, `router`, and `queue-worker`.
* **Analytical Purpose**:
  * Represents the rhetorical paradox at the heart of Silent Cascade: **Standard DevOps/SRE telemetry tracks system availability, not decision correctness.**
  * Demonstrates how an AI system can fail catastrophically in domain logic while maintaining pristine operational health metrics.

---

## Data Provenance & Methodological Honesty

In accordance with strict research integrity standards, every datum in this project is explicitly labeled with its provenance:

| Component | Source / Methodology | Provenance Label |
|---|---|---|
| **Substation Coordinates (27)** | OpenStreetMap query (`power=substation`) over Bhopal bounding box | **Observed** |
| **Hospital & Pump Coordinates (398)** | OpenStreetMap queries (`amenity=hospital`, `man_made=water_works\|pumping_station`) | **Observed** |
| **Power Feeder Topology** | $k$-Nearest Neighbors ($k=3$) on Haversine distance | **Inferred** |
| **Electrical Capacities & Loads** | Uniform bounded sampling from [`config.yaml`](file:///d:/Powel/MIT/Projects/silent-cascade-demo/config.yaml) | **Assumed** |
| **Hospital / Water Buffers** | Standard engineering baselines (8.0h generator fuel, 6.0h reservoir buffer) | **Assumed** |
| **Complaint Texts (20)** | Native Kannada script and English civic grievance dataset | **Synthetic** |
| **Routing Accuracy Metrics** | Deterministic 120-run experimental evaluation | **Measured** |
| **Cascade Dynamics & Criticality** | Physics-based load shedding simulation in [`src/cascade.py`](file:///d:/Powel/MIT/Projects/silent-cascade-demo/src/cascade.py) | **Simulated** |
| **Intervention Cost Estimates** | Order-of-magnitude representative figures for policy comparison | **Assumed** |

---

## Directory Structure

```
silent-cascade-demo/
├── README.md                      # Project documentation and guide
├── CLAUDE.md                      # Technical build specification
├── PLAN.md                        # Context, competition strategy, and core argument
├── config.yaml                    # Single source of truth for numeric assumptions
├── requirements.txt               # Python package dependencies
├── data/
│   ├── raw/                       # Cached Overpass API JSON responses (never re-fetched)
│   └── processed/                 # Generated node/edge CSVs and network graphs
├── src/
│   ├── fetch_data.py              # OpenStreetMap Overpass data extractor
│   ├── build_graph.py             # Spatial network builder & topology generator
│   ├── cascade.py                 # Pure-function cascading failure engine
│   ├── d1_cascade.py              # D1 pipeline: runs cascade & generates GIF/PNG frames
│   ├── d2_language.py             # D2 pipeline: language evaluation & chart generation
│   ├── d3_dashboard.py            # D3 pipeline: generates CivicOps monitor HTML
│   └── d4_intervention.py         # D4 pipeline: Monte Carlo intervention analysis
└── outputs/                       # Final artifacts, charts, CSVs, and dashboards
    ├── d1_cascade_scenario_a.gif  # Animated cascade simulation
    ├── d1_criticality.csv         # Substation vulnerability ranking
    ├── d2_chart.png               # Language accuracy bar chart
    ├── d2_results.csv             # Full 120 classification records
    ├── d3_dashboard.html          # Standalone all-green ops monitor HTML
    ├── d4_comparison.png          # Intervention comparison chart
    ├── d4_summary.csv             # Intervention statistical summary
    └── dashboard/
        ├── index.html             # Master interactive showcase dashboard
        └── assets/                # Supporting images and static media
```

---

## Getting Started

### Prerequisites
* Python 3.10 or higher
* Modern web browser (Chrome, Firefox, Safari, Edge)

### Installation
1. Clone the repository and navigate to the project directory:
   ```bash
   cd silent-cascade-demo
   ```
2. Create and activate a virtual environment:
   ```bash
   python -m venv venv
   # On Windows:
   .\venv\Scripts\activate
   # On macOS/Linux:
   source venv/bin/activate
   ```
3. Install required dependencies:
   ```bash
   pip install -r requirements.txt
   ```

### Running the Pipeline
Run the end-to-end simulation scripts in sequence:

```bash
# 1. Fetch real infrastructure geometry (cached to data/raw/)
python src/fetch_data.py

# 2. Construct topological graph and node attributes
python src/build_graph.py

# 3. Generate D1 cascade animations and criticality rankings
python src/d1_cascade.py

# 4. Run D2 language-stratified triage evaluation
python src/d2_language.py

# 5. Build D3 CivicOps monitoring mockup
python src/d3_dashboard.py

# 6. Execute D4 intervention Monte Carlo simulation
python src/d4_intervention.py
```

### Viewing the Dashboards
Open the HTML files directly in your web browser:
* **Interactive Showcase**: [`outputs/dashboard/index.html`](file:///d:/Powel/MIT/Projects/silent-cascade-demo/outputs/dashboard/index.html)
* **CivicOps Monitor**: [`outputs/d3_dashboard.html`](file:///d:/Powel/MIT/Projects/silent-cascade-demo/outputs/d3_dashboard.html)

---

## License & Attribution
* Built for **Manipal Hackathon (M#)**.
* Map data &copy; [OpenStreetMap](https://www.openstreetmap.org/copyright) contributors.
