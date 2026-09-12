# CLAUDE.md — Build Spec

Read `PLAN.md` for context on why this exists. This file is what to build.

## What we are building

Four **demo assets** for a hackathon slide deck and a 3-minute video.
We are NOT building a product. We are NOT deploying anything.
Every deliverable is a **PNG, GIF, or CSV** written to `outputs/`.

| ID | Asset | Feeds |
|----|-------|-------|
| D1 | Cascade animation on a real city power network | Slides 7, 8, 10 · Video 0:20–0:40, 1:20–2:00 |
| D2 | Language-stratified classification experiment | Slide 11 · Video 2:00–2:20 |
| D3 | Fake "all green" monitoring dashboard screenshot | Slides 4, 10 · Video 0:40–1:00 |
| D4 | Intervention comparison chart | Slide 13 · Video 2:20–2:40 |

**Build order: D1 → D2 → D3 → D4.** D4 is optional; drop it if time runs short.

---

## Hard constraints

- **Python 3.10+.** No Streamlit, no Flask, no database, no web server.
- **One runnable script per asset.** `python src/d1_cascade.py` must work end to end.
- Core logic must be **pure functions** taking a graph and returning data. Plotting is separate.
- **No network calls at run time** except the one-off data fetch in `src/fetch_data.py`.
  Cache raw OSM responses to `data/raw/` and never re-fetch.
- If a library isn't in `requirements.txt`, don't use it.
- **Do not invent numbers.** If a value is assumed, put it in `config.yaml` with a comment
  saying it's an assumption.

## Libraries

```
osmnx
overpy
networkx
geopandas
shapely
matplotlib
imageio
pandas
pyyaml
```

Add nothing else without asking.

---

## File structure

```
.
├── CLAUDE.md
├── PLAN.md
├── config.yaml
├── requirements.txt
├── data/
│   ├── raw/              # cached OSM JSON — never edit, never re-fetch
│   └── processed/        # nodes.csv, edges.csv, graph.gpickle
├── src/
│   ├── fetch_data.py     # D1 step 1
│   ├── build_graph.py    # D1 step 2
│   ├── cascade.py        # D1 step 3 — CORE LOGIC, pure functions
│   ├── d1_cascade.py     # D1 orchestrator → GIF + PNGs
│   ├── d2_language.py    # D2 → CSV + bar chart
│   ├── d3_dashboard.py   # D3 → HTML, screenshot manually
│   └── d4_intervention.py# D4 → comparison chart
└── outputs/              # everything the deck uses
```

---

## D1 — Cascade animation

### Step 1: fetch data (`src/fetch_data.py`)

Target city: **Bengaluru** (fallback: Bhopal, Indore, Nagpur, Jaipur — try in that order if node count < 15).
Bengaluru was chosen so the network geography matches the complaint language: the D2 dataset is
in **Kannada**, the language of Karnataka. (Bhopal, the original target, is in Hindi-speaking
Madhya Pradesh — the mismatch is why we switched.)

Bounding boxes:
- Bengaluru: `12.85, 77.45, 13.10, 77.75`
- Bhopal: `23.15, 77.30, 23.35, 77.55`
- Indore: `22.65, 75.75, 22.80, 75.95`

Overpass queries (use `overpy`, endpoint `https://overpass-api.de/api/interpreter`):

```
[out:json][timeout:90];
(
  node["power"="substation"](BBOX);
  way["power"="substation"](BBOX);
);
out center;
```

```
[out:json][timeout:90];
(
  node["amenity"="hospital"](BBOX);
  way["amenity"="hospital"](BBOX);
);
out center;
```

```
[out:json][timeout:90];
(
  node["man_made"="water_works"](BBOX);
  way["man_made"="water_works"](BBOX);
  node["man_made"="pumping_station"](BBOX);
  node["man_made"="water_tower"](BBOX);
);
out center;
```

**Known issue:** water infrastructure is sparsely mapped in Indian OSM. If fewer than
3 water nodes return, synthesise 5 pumping stations at random points within the bbox and
set `provenance="synthetic"` on them. Print a loud warning. Do not fail silently.

Cache each raw response to `data/raw/{layer}_{city}.json`. If the file exists, load it
instead of re-fetching.

### Step 2: build graph (`src/build_graph.py`)

**Node schema** — write to `data/processed/nodes.csv`:

| field | type | notes |
|---|---|---|
| `id` | str | `sub_001`, `hosp_001`, `pump_001` |
| `type` | str | `substation` \| `hospital` \| `pump` |
| `lat`, `lon` | float | from OSM |
| `name` | str | OSM name, or `""` |
| `capacity` | float | substations only; see config |
| `load` | float | substations only; see config |
| `population_served` | int | substations only |
| `buffer_hours` | float | hospitals (generator fuel), pumps (reservoir) |
| `provenance` | str | `observed` \| `inferred` \| `synthetic` |

**Edge schema** — `data/processed/edges.csv`:

| field | type | notes |
|---|---|---|
| `source`, `target` | str | node ids |
| `type` | str | `grid` (sub↔sub) \| `supply` (sub→hosp/pump) |
| `provenance` | str | always `inferred` — we do not have real feeder topology |

**Topology rules:**
- Connect each substation to its **3 nearest** substations (KNN on haversine distance).
  Make edges undirected and deduplicate.
- Connect each hospital and pump to its **single nearest** substation, directed `sub → asset`.
- Every edge gets `provenance="inferred"`. Say this on the slide. It is not a weakness if labelled.

**Attribute assignment** (all from `config.yaml`, all marked as assumptions):
- `capacity`: random uniform in `[80, 150]` MW, seeded
- `load`: random uniform in `[0.55, 0.75] × capacity` — headroom, but not much
- `population_served`: random uniform `[8000, 45000]`, seeded
- `buffer_hours`: hospitals 8.0, pumps 6.0

**Use a fixed random seed (`config.yaml: seed: 42`) so results are reproducible.**

Save as `data/processed/graph.gpickle`.

### Step 3: cascade logic (`src/cascade.py`) — THIS IS THE CORE

Pure functions only. No plotting, no file I/O.

```python
def cascade(G, initial_failures, max_steps=12):
    """
    Simulate load-redistribution cascade.

    Returns: list[dict] — one entry per timestep:
        {
            "step": int,
            "hours": float,              # step * config.hours_per_step
            "failed": set[str],          # all failed node ids so far
            "newly_failed": set[str],
            "overloaded": set[str],      # >90% capacity, not yet failed
            "people_affected": int,
            "hospitals_on_generator": list[str],
            "wards_without_water": list[str],
        }
    """
```

Algorithm:

```python
failed = set(initial_failures)
timeline = []

for step in range(max_steps):
    newly_failed = set()

    # 1. Redistribute load from failed substations to living neighbours
    for node in failed:
        if G.nodes[node]['type'] != 'substation':
            continue
        live_neighbors = [
            n for n in G.neighbors(node)
            if n not in failed and G.nodes[n]['type'] == 'substation'
        ]
        if not live_neighbors:
            continue
        shed = G.nodes[node]['load'] / len(live_neighbors)
        for n in live_neighbors:
            G.nodes[n]['load'] += shed

    # 2. Trip anything over capacity
    for n in G.nodes:
        if n in failed or G.nodes[n]['type'] != 'substation':
            continue
        if G.nodes[n]['load'] > G.nodes[n]['capacity']:
            newly_failed.add(n)

    # 3. Dependent assets fail when their feeding substation fails
    for n in G.nodes:
        if n in failed or G.nodes[n]['type'] in ('hospital', 'pump'):
            feeders = [p for p in G.predecessors(n)] if G.is_directed() else list(G.neighbors(n))
            if feeders and all(f in failed or f in newly_failed for f in feeders):
                newly_failed.add(n)

    failed |= newly_failed
    timeline.append(build_snapshot(G, failed, newly_failed, step))

    if not newly_failed:
        break

return timeline
```

**Important:** `cascade()` must not mutate the caller's graph. Deep-copy at entry.

Also implement:

```python
def criticality_ranking(G, top_n=10):
    """
    For each substation, run cascade() with it as the sole initial failure.
    Rank by total people_affected at the final timestep — NOT by degree or betweenness.
    Returns: pandas DataFrame [node_id, name, people_affected, cascade_size, hospitals_hit]
    """
```

This ranking is what slide 12 compares AI nodes against. It must exist.

### Step 4: animation (`src/d1_cascade.py`)

For each timestep, plot:
- All nodes at real lat/lon, `matplotlib` scatter
- Grid edges as thin grey lines
- Colours: healthy `#9aa0a6` · overloaded `#f5a623` · failed `#d93025` · hospital marker `+` · pump marker `s`
- Title: `T+{hours}h`
- Text box bottom-left: `People affected: N` / `Hospitals on generator: M`

Write each frame to `outputs/d1_frames/frame_{step:02d}.png` at **1600×1200, dpi=150**.
Stitch to `outputs/d1_cascade.gif` with `imageio`, **fps=1.5**, and hold the final frame for
3 seconds (duplicate it 4–5 times).

Run **two scenarios** and label outputs distinctly:
- `scenario_a` — largest substation by `population_served` fails. This is the "equipment
  failure" baseline for slide 8.
- `scenario_b` — a substation fails **14 timesteps later** due to delayed repair. Same
  visual, different framing for slide 10. (The delay itself is narrative, not simulated —
  just start the cascade and title it differently.)

Also write `outputs/d1_criticality.csv` from `criticality_ranking()`.

---

## D2 — Language experiment

**This produces the only genuinely measured numbers in the submission. Do not skip it.**

### Inputs

Create `data/complaints.csv` with **20 civic complaints**, hand-written:

| field | notes |
|---|---|
| `id` | c01–c20 |
| `text_en` | English complaint, 1–2 sentences, realistic |
| `text_native` | Same complaint in **Kannada native script** (Karnataka's language, matching the Bengaluru network) |
| `true_dept` | ground truth label |

Six departments: `electrical_emergency`, `electrical_maintenance`, `water_supply`,
`drainage`, `roads`, `sanitation`.

Include at least 4 that are genuinely urgent and easily downgraded — a sparking transformer
that could be read as streetlight maintenance, a burst main that could be read as drainage.
**These are the ones the demo hinges on.**

### Conditions

Run all 20 complaints × 2 languages × 3 model conditions = 120 classifications:

| condition | implementation |
|---|---|
| `clean` | full prompt, full model |
| `truncated` | truncate complaint text to first 40 characters before classifying |
| `small_model` | same prompt, a deliberately weaker/smaller model |

Classifier prompt: give the six department names, ask for exactly one, no explanation.
Parse the response strictly; count unparseable as incorrect.

### Outputs

`outputs/d2_results.csv` — one row per classification:
`id, language, condition, predicted_dept, true_dept, correct`

`outputs/d2_accuracy.csv` — accuracy by `language × condition`

`outputs/d2_chart.png` — grouped bar chart, 1600×1000, dpi=150.
X axis: condition. Two bars per group: English, Native script. Y axis: accuracy %.
**If the native-script bars are lower, that is the finding. If they are not, report that
honestly — do not tune the experiment until it agrees with the pitch.**

Also print to console: the specific complaints that were correctly routed in English and
misrouted in native script. **Those are the examples that go in the video.**

---

## D3 — Dashboard mock

`src/d3_dashboard.py` writes `outputs/d3_dashboard.html`.

Plain HTML + inline CSS. Dark background. Four metric cards:

```
Uptime         99.98%   ✓ green
p50 Latency     187ms   ✓ green
Error rate      0.01%   ✓ green
Requests/min    1,240   ✓ green
```

Plus a "Services" list with 6 rows, all showing green status dots:
`intake-api`, `language-normaliser`, `classifier`, `urgency-scorer`, `router`, `queue-worker`

Add a small sparkline per card (a flat-ish random walk is fine — it's a mock).

Make it look like a real monitoring tool. This screenshot sits beside a wrong
classification output, and the contrast is the whole point.

Open in a browser and screenshot manually at 1600px wide → `outputs/d3_dashboard.png`.

---

## D4 — Intervention comparison (optional)

`src/d4_intervention.py`

Three runs of the same cascade:
1. **Baseline** — no intervention
2. **Harden substation** — take the top-ranked node from `d1_criticality.csv`, set
   `capacity *= 1.5`
3. **Verification checkpoint** — reduce misroute rate, modelled as delaying the
   initiating failure by N steps or removing it entirely in X% of runs

Run each 100 times with different random initial failures. Report mean people affected.

`outputs/d4_comparison.png` — horizontal bar chart, three bars, annotated with
approximate ₹ cost (from `config.yaml`, marked as assumption).

---

## Acceptance criteria

Do not consider a module done until:

**D1** ✅ `python src/d1_cascade.py` runs clean from a fresh clone (after `fetch_data.py`)
✅ `outputs/d1_cascade.gif` exists, shows visible spread across ≥4 frames, city shape recognisable
✅ `outputs/d1_criticality.csv` has ≥10 rows ranked by `people_affected`
✅ Every node and edge has a `provenance` value

**D2** ✅ `outputs/d2_results.csv` has 120 rows
✅ `outputs/d2_chart.png` is legible at slide size
✅ Console prints ≥2 named misrouting examples

**D3** ✅ `outputs/d3_dashboard.png` exists and reads as a real monitoring tool at a glance

**D4** ✅ `outputs/d4_comparison.png` exists with three annotated bars

---

## Style

- Type hints on all function signatures
- Docstrings on public functions; skip them on trivial helpers
- No classes unless there's genuine state to hold
- Print progress — these are long-running scripts and silence is indistinguishable from a hang
- Fail loudly on missing data. Never silently substitute defaults.

## When you are unsure

Ask. Do not guess at:
- Which city, if Bengaluru returns too little data
- Whether to synthesise a layer
- Any number that would appear on a slide

Everything in `outputs/` ends up in front of judges. Treat it accordingly.
