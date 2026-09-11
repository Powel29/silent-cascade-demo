"""Silent Cascade — interactive prototype (Streamlit).

A thin UI over the repo's existing pure functions. Every number shown here comes from the
same code that produced outputs/*.csv: cascade.cascade(), d2_language.classify_one(),
d4_intervention.run_condition(). Nothing is reimplemented in the app layer.

Run locally:  pip install -r requirements.txt && streamlit run app.py
"""

from __future__ import annotations

import html
import json
import pickle
import sys
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
import yaml

REPO_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO_ROOT / "src"))

from cascade import cascade, criticality_ranking  # noqa: E402
from d2_language import (  # noqa: E402
    CONDITIONS,
    DEPARTMENTS,
    FULL_KEYWORDS_EN,
    FULL_KEYWORDS_KN,
    SMALL_KEYWORDS_EN,
    SMALL_KEYWORDS_KN,
    _looks_english,
    accuracy_table,
    canary_report,
    classify_one,
    condition_input,
    misroute_examples,
    route_with_guard,
    plot_accuracy,
)
from d4_intervention import draw_random_failures, hardened_graph, plot_comparison, run_condition  # noqa: E402

COLORS = {"healthy": "#9aa0a6", "overloaded": "#f5a623", "failed": "#d93025", "blue": "#4285f4", "green": "#34a853"}

st.set_page_config(page_title="Silent Cascade", page_icon="⚡", layout="wide")

st.markdown(
    """
    <style>
      .sc-eyebrow { font-family: monospace; font-size: 12px; letter-spacing: .16em; text-transform: uppercase; color: #9aa0a6; }
      .sc-title { font-size: 44px; font-weight: 800; letter-spacing: .04em; line-height: 1; margin: 6px 0 10px; }
      .sc-title span { color: #d93025; }
      .sc-lede { color: #cfd2d6; font-size: 18px; max-width: 70ch; }
      .sc-cap { font-family: monospace; font-size: 13px; color: #cfd2d6; border-left: 2px solid #343b46; padding-left: 12px; }
      .sc-card { background: #171b21; border: 1px solid #262b33; border-radius: 10px; padding: 16px 18px; }
      .sc-bad { border-color: rgba(217,48,37,.6); box-shadow: 0 0 24px rgba(217,48,37,.18); }
      .sc-ok  { border-color: rgba(52,168,83,.5); box-shadow: 0 0 24px rgba(52,168,83,.12); }
      .sc-k { font-family: monospace; font-size: 11px; letter-spacing: .08em; text-transform: uppercase; color: #9aa0a6; }
      .sc-v { font-family: monospace; font-size: 15px; }
      .sc-v.bad { color: #d93025; font-weight: 700; } .sc-v.ok { color: #34a853; } .sc-v.unp { color: #f5a623; font-weight: 700; }
      .sc-text { font-size: 16px; line-height: 1.6; }
      .sc-text mark { background: rgba(66,133,244,.22); color: inherit; border-bottom: 1px solid #4285f4; padding: 0 1px; }
      .sc-text mark.wrong { background: rgba(217,48,37,.22); border-bottom-color: #d93025; }
      .sc-text s { color: #6b7280; text-decoration-color: rgba(217,48,37,.6); }
      .sc-log { font-family: monospace; font-size: 12px; color: #6b7280; } .sc-log b { color: #34a853; font-weight: 500; }
      .sc-hud { display: flex; flex-wrap: wrap; gap: 10px; margin: 6px 0 14px; }
      .sc-hud > div { flex: 1 1 150px; background: #171b21; border: 1px solid #262b33; border-radius: 8px; padding: 10px 14px; }
      .sc-big { font-family: monospace; font-size: 26px; font-weight: 700; line-height: 1.15; margin-top: 4px; font-variant-numeric: tabular-nums; }
      .sc-pill { display: inline-block; font-family: monospace; font-size: 11px; letter-spacing: .06em; text-transform: uppercase; padding: 3px 9px; border-radius: 999px; border: 1px solid #343b46; }
      .sc-pill.real { color: #34a853; border-color: rgba(52,168,83,.5); } .sc-pill.meas { color: #4285f4; border-color: rgba(66,133,244,.5); }
      .sc-pill.inf { color: #f5a623; border-color: rgba(245,166,35,.5); } .sc-pill.syn { color: #9aa0a6; } .sc-pill.sim { color: #cfd2d6; }

      .sc-hero { padding: 28px 0 8px; }
      .sc-hero .sc-eyebrow { display: inline-flex; align-items: center; gap: 10px; }
      .sc-hero .sc-eyebrow i { width: 6px; height: 6px; border-radius: 50%; background: #d93025; box-shadow: 0 0 10px #d93025; display: inline-block; }
      .sc-hero .sc-title { font-size: clamp(40px, 7vw, 72px); margin: 10px 0 14px; }
      .sc-hero .sc-lede { font-size: clamp(17px, 1.6vw, 20px); line-height: 1.5; }
      .sc-meta { display: flex; flex-wrap: wrap; gap: 8px 24px; margin-top: 18px; font-family: monospace; font-size: 12px; color: #6b7280; }
      .sc-meta b { color: #9aa0a6; font-weight: 500; margin-right: 6px; }

      .sc-sec { margin: 44px 0 18px; padding-top: 18px; border-top: 1px solid #262b33; }
      .sc-sec h3 { margin: 0; font-size: 26px; font-weight: 700; letter-spacing: .01em; }
      .sc-sec p { margin: 6px 0 0; color: #9aa0a6; max-width: 70ch; font-size: 15px; }
      .sc-sec em { color: #cfd2d6; font-style: normal; font-weight: 600; }

      .sc-flow { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 14px; }
      .sc-step { background: #171b21; border: 1px solid #262b33; border-radius: 10px; padding: 12px 14px; position: relative; }
      .sc-step .dot { width: 10px; height: 10px; border-radius: 50%; background: #4285f4; box-shadow: 0 0 10px rgba(66,133,244,.6); margin: 8px 0 10px; }
      .sc-step.bad .dot { background: #d93025; box-shadow: 0 0 12px rgba(217,48,37,.7); }
      .sc-step.bad { border-color: rgba(217,48,37,.35); }
      .sc-step .t { font-size: 15px; line-height: 1.3; color: #e8eaed; font-weight: 600; }
      .sc-step .s { font-family: monospace; font-size: 11.5px; color: #9aa0a6; margin-top: 5px; line-height: 1.4; }

      .sc-split { display: grid; grid-template-columns: repeat(auto-fit, minmax(340px, 1fr)); gap: 18px; align-items: stretch; }
      .sc-panel { background: #171b21; border: 1px solid #262b33; border-radius: 12px; padding: 18px 20px; }
      .sc-panel .hdr { display: flex; justify-content: space-between; align-items: baseline; gap: 12px; flex-wrap: wrap; margin-bottom: 14px; }
      .sc-panel .hdr b { font-size: 16px; } .sc-panel .hdr span { font-family: monospace; font-size: 11px; color: #6b7280; letter-spacing: .06em; }
      .sc-mgrid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 10px; }
      .sc-mgrid .m { background: #1d222a; border: 1px solid #262b33; border-radius: 8px; padding: 12px 14px; }
      .sc-mgrid .l { font-size: 12px; color: #9aa0a6; }
      .sc-mgrid .v { font-family: monospace; font-size: 22px; font-weight: 600; display: flex; align-items: center; gap: 8px; margin-top: 2px; }
      .sc-mgrid svg { display: block; width: 100%; height: 26px; margin-top: 8px; }
      .gdot { width: 8px; height: 8px; border-radius: 50%; background: #34a853; box-shadow: 0 0 8px rgba(52,168,83,.8); display: inline-block; }
      .sc-svc { margin-top: 12px; border-top: 1px solid #262b33; }
      .sc-svc div { display: flex; align-items: center; gap: 10px; padding: 8px 2px; border-bottom: 1px solid #262b33; font-family: monospace; font-size: 12.5px; }
      .sc-svc div:last-child { border-bottom: 0; } .sc-svc span { flex: 1; color: #cfd2d6; }
      .sc-svc em { font-style: normal; color: #34a853; font-size: 10.5px; letter-spacing: .08em; text-transform: uppercase; }
      .sc-trace { display: grid; gap: 0; margin-top: 8px; }
      .sc-trace > div { display: grid; grid-template-columns: 90px 1fr; gap: 12px; align-items: baseline; padding: 9px 0; border-top: 1px solid rgba(217,48,37,.2); font-size: 14px; }
      .sc-trace > div:last-child { border-bottom: 1px solid rgba(217,48,37,.2); }

      .sc-prov { border: 1px solid #262b33; border-radius: 12px; background: #171b21; padding: 4px 20px; }
      .sc-prov > div { display: grid; grid-template-columns: 1.3fr 1fr auto; gap: 14px; align-items: center; padding: 12px 0; border-bottom: 1px solid #262b33; }
      .sc-prov > div:last-child { border-bottom: 0; }
      .sc-prov .k { color: #e8eaed; font-size: 14.5px; } .sc-prov .src { font-family: monospace; font-size: 12px; color: #9aa0a6; }
      @media (max-width: 640px) { .sc-prov > div { grid-template-columns: 1fr; gap: 4px; } .sc-mgrid { grid-template-columns: 1fr; } }
    </style>
    """,
    unsafe_allow_html=True,
)


# ---------------------------------------------------------------- data loading

def load_config() -> dict[str, Any]:
    path = REPO_ROOT / "config.yaml"
    return _load_config(path.stat().st_mtime)


@st.cache_data
def _load_config(mtime: float) -> dict[str, Any]:
    with open(REPO_ROOT / "config.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)


@st.cache_resource
def load_graph():
    with open(REPO_ROOT / "data" / "processed" / "graph.gpickle", "rb") as f:
        return pickle.load(f)


@st.cache_data
def load_nodes() -> pd.DataFrame:
    return pd.read_csv(REPO_ROOT / "data" / "processed" / "nodes.csv")


@st.cache_data
def load_complaints() -> pd.DataFrame:
    return pd.read_csv(REPO_ROOT / "data" / "complaints.csv")


@st.cache_data
def load_csv(name: str) -> pd.DataFrame | None:
    p = REPO_ROOT / "outputs" / name
    return pd.read_csv(p) if p.exists() else None


@st.cache_data
def run_cascade(node_id: str) -> list[dict[str, Any]]:
    cfg = load_config()
    return cascade(load_graph(), [node_id], max_steps=cfg["d1"]["max_steps"], hours_per_step=cfg["assumptions"]["hours_per_step"])


@st.cache_data
def ranking() -> pd.DataFrame:
    cfg = load_config()
    return criticality_ranking(load_graph(), max_steps=cfg["d1"]["max_steps"], hours_per_step=cfg["assumptions"]["hours_per_step"], top_n=10)


@st.cache_data
def run_interventions(n_runs: int) -> tuple[list[tuple[str, list[int], float]], str]:
    cfg = load_config()
    G = load_graph()
    top_node = ranking().iloc[0]["node_id"]
    seed = cfg["seed"]
    failures = draw_random_failures(G, n_runs, seed)
    baseline = run_condition(G, failures, cfg)
    hardened = run_condition(hardened_graph(G, top_node, 1.5), failures, cfg)
    checkpoint = run_condition(G, failures, cfg, prevention_rate=cfg["d4"]["verification_checkpoint_prevention_rate"], prevention_seed=seed + 1)
    costs = cfg["assumptions"]["cost_inr"]
    return (
        [
            ("Baseline\n(no intervention)", baseline, 0),
            ("Harden substation", hardened, costs["harden_substation"]),
            ("Verification checkpoint", checkpoint, costs["verification_checkpoint"]),
        ],
        top_node,
    )


# ---------------------------------------------------------------- map (client-side Leaflet, no reruns)

MAP_HTML = r"""
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<style>
  html, body { margin: 0; background: #0f1216; font-family: "Source Sans Pro", "Segoe UI", sans-serif; color: #e8eaed; }
  #wrap { position: relative; width: 100%; height: __H__px; border-radius: 10px; overflow: hidden; border: 1px solid #343b46; background: #0b0d10; }
  #map { position: absolute; inset: 0; }
  .leaflet-tile-pane { filter: brightness(.62) saturate(.7); }
  .hud { position: absolute; left: 12px; top: 12px; z-index: 1000; display: grid; gap: 5px; min-width: 200px; pointer-events: none;
         background: rgba(15,18,22,.86); border: 1px solid #343b46; border-radius: 8px; padding: 10px 12px; font-family: monospace; }
  .hud div { display: flex; justify-content: space-between; gap: 16px; align-items: baseline; font-size: 12px; }
  .hud .k { color: #9aa0a6; font-size: 10px; letter-spacing: .08em; text-transform: uppercase; }
  .hud b { font-weight: 700; color: #e8eaed; font-size: 14px; font-variant-numeric: tabular-nums; }
  .hud .t b { font-size: 21px; color: #d93025; } .hud .p b { color: #d93025; }
  .ctl { position: absolute; left: 12px; right: 12px; bottom: 12px; z-index: 1000; display: flex; gap: 8px; align-items: center; flex-wrap: wrap;
         background: rgba(15,18,22,.88); border: 1px solid #343b46; border-radius: 8px; padding: 7px 10px; }
  .btn { font-family: monospace; font-size: 12px; color: #0f1216; background: #e8eaed; border: 0; border-radius: 6px; padding: 6px 11px; cursor: pointer; font-weight: 700; white-space: nowrap; }
  .btn.ghost { background: transparent; color: #cfd2d6; border: 1px solid #343b46; font-weight: 500; }
  input[type=range] { flex: 1; min-width: 120px; accent-color: #d93025; }
  .seg { display: inline-flex; border: 1px solid #343b46; border-radius: 6px; overflow: hidden; }
  .seg button { font-family: monospace; font-size: 11px; color: #9aa0a6; background: transparent; border: 0; border-right: 1px solid #343b46; padding: 6px 9px; cursor: pointer; }
  .seg button:last-child { border-right: 0; } .seg button.on { color: #e8eaed; background: #343b46; }
  .attrib { margin-left: auto; font-family: monospace; font-size: 10px; color: rgba(232,234,237,.55); white-space: nowrap; }
  .attrib a { color: inherit; }
  .leaflet-control-attribution { display: none; }
  .leaflet-tooltip { background: rgba(15,18,22,.95); color: #e8eaed; border: 1px solid #343b46; font-family: monospace; font-size: 11px; }
  .leaflet-tooltip-top:before { border-top-color: #343b46; }
  .pump { width: 9px; height: 9px; border: 1px solid #000; box-sizing: border-box; }
  .leaflet-marker-icon.pump { background: var(--c, #9aa0a6); }
</style>
<div id="wrap">
  <div id="map"></div>
  <div class="hud">
    <div class="t"><span class="k">Elapsed</span><b id="h-t">T+0.0h</b></div>
    <div class="p"><span class="k">People affected</span><b id="h-p">0</b></div>
    <div><span class="k">Hospitals on generator</span><b id="h-h">0</b></div>
    <div><span class="k">Wards without water</span><b id="h-w">0</b></div>
    <div><span class="k">Substations tripped</span><b id="h-s">0</b></div>
  </div>
  <div class="ctl">
    <button class="btn" id="play">❚❚ Pause</button>
    <button class="btn ghost" id="restart">↺</button>
    <input type="range" id="scrub" min="0" max="__LAST__" step="0.01" value="0">
    <div class="seg"><button data-s="4" class="on">slow</button><button data-s="2">normal</button><button data-s="0.8">fast</button></div>
    <button class="btn ghost" id="fit">⤢ fit</button>
    <span class="attrib">© <a href="https://www.openstreetmap.org/copyright" target="_blank">OpenStreetMap</a> contributors</span>
  </div>
</div>
<script>
const D = __DATA__;
const C = { healthy: '#9aa0a6', over: '#f5a623', failed: '#d93025' };
const map = L.map('map', { zoomControl: false, attributionControl: false });
L.control.zoom({ position: 'topright' }).addTo(map);
L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', { maxZoom: 18 }).addTo(map);
const bounds = L.latLngBounds(D.nodes.map(n => [n[0], n[1]]));
map.fitBounds(bounds.pad(0.08));

// per-node schedule: failAt (fractional step, staggered within a step), overloaded steps
const failAt = new Array(D.nodes.length).fill(Infinity);
const overAt = D.nodes.map(() => new Set());
D.steps.forEach(s => {
  const n = s.new.length;
  s.new.forEach((i, k) => { failAt[i] = s.step + (n > 1 ? (k / n) * 0.8 : 0); });
  s.over.forEach(i => overAt[i].add(s.step));
});
const stateOf = (i, t) => failAt[i] <= t ? 'failed' : overAt[i].has(Math.floor(t)) ? 'over' : 'healthy';

// edges
const edgeLayers = D.edges.map(([a, b]) => L.polyline([[D.nodes[a][0], D.nodes[a][1]], [D.nodes[b][0], D.nodes[b][1]]], { color: '#6b7280', weight: 1.4, opacity: .8, interactive: false }).addTo(map));
// nodes: substations big circles, hospitals small circles, pumps squares (divIcon)
const markers = D.nodes.map((n, i) => {
  const [lat, lon, type, id, name, pop] = n;
  const label = `<b>${name || id}</b><br>${['substation','hospital','pump'][type]}${type === 0 ? ` · serves ${pop.toLocaleString('en-US')}` : ''}<br><span id="tt-${i}"></span>`;
  let m;
  if (type === 2) {
    m = L.marker([lat, lon], { icon: L.divIcon({ className: 'pump', iconSize: [9, 9] }), interactive: true });
  } else {
    m = L.circleMarker([lat, lon], { radius: type === 0 ? 7 : 3, color: type === 0 ? '#000' : C.healthy, weight: type === 0 ? 1 : 2, fillColor: C.healthy, fillOpacity: .95 });
  }
  m.bindTooltip(label, { direction: 'top', offset: [0, -6] });
  m.addTo(map);
  return m;
});
const TYPE = D.nodes.map(n => n[2]);
const fmt = v => v.toLocaleString('en-US');

let t = 0, playing = true, secPerStep = 4, last = 0;
const LAST = D.steps.length - 1;
function paint() {
  const step = Math.floor(t);
  let subs = 0;
  D.nodes.forEach((n, i) => {
    const s = stateOf(i, t), col = C[s];
    if (s === 'failed' && TYPE[i] === 0) subs++;
    const m = markers[i];
    if (TYPE[i] === 2) { const el = m.getElement(); if (el) el.style.background = col; }
    else m.setStyle(TYPE[i] === 0 ? { fillColor: col } : { fillColor: col, color: col });
    const tt = document.getElementById('tt-' + i); if (tt) tt.textContent = s === 'failed' ? `FAILED at T+${(failAt[i] * D.hps).toFixed(1)}h` : s.toUpperCase();
  });
  D.edges.forEach(([a, b], k) => {
    const fa = failAt[a] <= t, fb = failAt[b] <= t;
    edgeLayers[k].setStyle({ color: fa && fb ? C.failed : (fa || fb) ? C.over : '#6b7280', opacity: fa || fb ? .9 : .7 });
  });
  const s = D.steps[step];
  document.getElementById('h-t').textContent = `T+${(t * D.hps).toFixed(1)}h`;
  document.getElementById('h-p').textContent = fmt(s.people);
  document.getElementById('h-h').textContent = fmt(s.hosp);
  document.getElementById('h-w').textContent = fmt(s.pumps);
  document.getElementById('h-s').textContent = `${subs} / ${D.nsub}`;
  document.getElementById('scrub').value = t;
}
function loop(ts) {
  const dt = last ? (ts - last) / 1000 : 0; last = ts;
  if (playing) {
    t = Math.min(LAST, t + dt / secPerStep);
    if (t >= LAST) { playing = false; document.getElementById('play').textContent = '↺ Replay'; }
    paint();
  }
  requestAnimationFrame(loop);
}
const playBtn = document.getElementById('play');
playBtn.onclick = () => { if (playing) { playing = false; playBtn.textContent = t >= LAST ? '↺ Replay' : '▶ Play'; } else { if (t >= LAST) t = 0; playing = true; playBtn.textContent = '❚❚ Pause'; } };
document.getElementById('restart').onclick = () => { t = 0; playing = true; playBtn.textContent = '❚❚ Pause'; paint(); };
document.getElementById('fit').onclick = () => map.fitBounds(bounds.pad(0.08));
document.getElementById('scrub').oninput = e => { t = +e.target.value; playing = false; playBtn.textContent = t >= LAST ? '↺ Replay' : '▶ Play'; paint(); };
document.querySelectorAll('.seg button').forEach(b => b.onclick = () => { secPerStep = +b.dataset.s; document.querySelectorAll('.seg button').forEach(x => x.classList.toggle('on', x === b)); });
paint();
requestAnimationFrame(loop);
</script>
"""


def cascade_component(nodes: pd.DataFrame, G, timeline: list[dict[str, Any]], hours_per_step: float, height: int = 620) -> str:
    """Self-contained Leaflet page: whole timeline embedded, animated client-side (no Streamlit reruns)."""
    idx = {nid: i for i, nid in enumerate(nodes.id)}
    tcode = {"substation": 0, "hospital": 1, "pump": 2}
    node_list = [
        [round(float(r.lat), 5), round(float(r.lon), 5), tcode[r.type], r.id,
         r.name if isinstance(r.name, str) else "", int(r.population_served) if r.type == "substation" else 0]
        for r in nodes.itertuples()
    ]
    edges = [[idx[u], idx[v]] for u, v, d in G.edges(data=True) if d["type"] == "grid" and u < v]
    prev: set[str] = set()
    steps = []
    for s in timeline:
        new = sorted(idx[n] for n in s["failed"] - prev) if s["step"] else sorted(idx[n] for n in s["failed"])
        prev = set(s["failed"])
        steps.append({
            "step": s["step"], "new": new, "over": sorted(idx[n] for n in s["overloaded"]),
            "people": s["people_affected"], "hosp": len(s["hospitals_on_generator"]), "pumps": len(s["wards_without_water"]),
        })
    data = {"nodes": node_list, "edges": edges, "steps": steps, "hps": hours_per_step, "nsub": int((nodes.type == "substation").sum())}
    return (MAP_HTML.replace("__DATA__", json.dumps(data, ensure_ascii=False))
            .replace("__LAST__", str(len(timeline) - 1)).replace("__H__", str(height)))


# ---------------------------------------------------------------- pages

# Live "all green" monitor. Runs entirely in the browser (no Streamlit reruns): metrics drift,
# sparklines scroll, the clock ticks, and a request log fills with 200 OKs. It is a MOCK — the
# point is that a healthy-looking monitor is exactly what a silently wrong classifier produces.
MONITOR_HTML = r"""
<style>
  html, body { margin: 0; background: transparent; font-family: "Source Sans Pro", "Segoe UI", sans-serif; color: #e8eaed; }
  .p { background: #171b21; border: 1px solid rgba(52,168,83,.5); box-shadow: 0 0 24px rgba(52,168,83,.12); border-radius: 12px; padding: 18px 20px; }
  .hdr { display: flex; justify-content: space-between; align-items: baseline; gap: 12px; flex-wrap: wrap; margin-bottom: 14px; }
  .hdr b { font-size: 16px; } .hdr span { font-family: monospace; font-size: 11px; color: #6b7280; letter-spacing: .06em; }
  .g { display: grid; grid-template-columns: repeat(2, 1fr); gap: 10px; }
  .m { background: #1d222a; border: 1px solid #262b33; border-radius: 8px; padding: 12px 14px; }
  .l { font-size: 12px; color: #9aa0a6; }
  .v { font-family: monospace; font-size: 22px; font-weight: 600; display: flex; align-items: center; gap: 8px; margin-top: 2px; font-variant-numeric: tabular-nums; }
  svg { display: block; width: 100%; height: 26px; margin-top: 8px; }
  .d { width: 8px; height: 8px; border-radius: 50%; background: #34a853; box-shadow: 0 0 8px rgba(52,168,83,.8); display: inline-block; }
  .svc { margin-top: 12px; border-top: 1px solid #262b33; }
  .svc div { display: flex; align-items: center; gap: 10px; padding: 7px 2px; border-bottom: 1px solid #262b33; font-family: monospace; font-size: 12.5px; }
  .svc div:last-child { border-bottom: 0; } .svc span { flex: 1; color: #cfd2d6; }
  .svc em { font-style: normal; color: #34a853; font-size: 10.5px; letter-spacing: .08em; text-transform: uppercase; }
  .log { margin-top: 12px; border-top: 1px solid #262b33; padding-top: 8px; font-family: monospace; font-size: 11px; color: #6b7280; line-height: 1.7; height: 5.1em; overflow: hidden; }
  .log b { color: #34a853; font-weight: 500; }
  @media (max-width: 300px) { .g { grid-template-columns: 1fr; } }
</style>
<div class="p">
  <div class="hdr"><b>CivicOps Monitor</b><span>grievance pipeline · all systems · <span id="clk">updated just now</span></span></div>
  <div class="g">
    <div class="m"><div class="l">Uptime</div><div class="v"><span id="up">99.98%</span> <i class="d"></i></div><svg viewBox="0 0 160 26" preserveAspectRatio="none"><polyline id="s-up" fill="none" stroke="#34a853" stroke-width="1.6" points="0,14 12,13 24,15 36,13 48,14 60,12 72,14 84,13 96,15 108,13 120,14 132,12 144,13 160,14"/></svg></div>
    <div class="m"><div class="l">p50 Latency</div><div class="v"><span id="lat">187ms</span> <i class="d"></i></div><svg viewBox="0 0 160 26" preserveAspectRatio="none"><polyline id="s-lat" fill="none" stroke="#34a853" stroke-width="1.6" points="0,15 12,14 24,16 36,15 48,13 60,15 72,16 84,14 96,13 108,15 120,16 132,14 144,15 160,13"/></svg></div>
    <div class="m"><div class="l">Error rate</div><div class="v"><span id="err">0.01%</span> <i class="d"></i></div><svg viewBox="0 0 160 26" preserveAspectRatio="none"><polyline id="s-err" fill="none" stroke="#34a853" stroke-width="1.6" points="0,16 12,16 24,15 36,16 48,17 60,16 72,15 84,16 96,16 108,17 120,16 132,15 144,16 160,16"/></svg></div>
    <div class="m"><div class="l">Requests / min</div><div class="v"><span id="rpm">1,240</span> <i class="d"></i></div><svg viewBox="0 0 160 26" preserveAspectRatio="none"><polyline id="s-rpm" fill="none" stroke="#34a853" stroke-width="1.6" points="0,13 12,15 24,12 36,14 48,16 60,13 72,12 84,15 96,14 108,12 120,15 132,13 144,14 160,12"/></svg></div>
  </div>
  <div class="svc">
    <div><i class="d"></i><span>intake-api</span><em>operational</em></div>
    <div><i class="d"></i><span>language-normaliser</span><em>operational</em></div>
    <div><i class="d"></i><span>classifier</span><em>operational</em></div>
    <div><i class="d"></i><span>urgency-scorer</span><em>operational</em></div>
    <div><i class="d"></i><span>router</span><em>operational</em></div>
    <div><i class="d"></i><span>queue-worker</span><em>operational</em></div>
  </div>
  <div class="log" id="log"></div>
</div>
<script>
const $ = id => document.getElementById(id);
let seed = 7; const rnd = () => { seed = (seed * 1103515245 + 12345) & 0x7fffffff; return seed / 0x7fffffff; };
const S = {}; for (const k of ['up','lat','err','rpm']) S[k] = $('s-' + k).getAttribute('points').trim().split(/\s+/).map(p => +p.split(',')[1]);
function push(k, y) { const s = S[k]; s.push(Math.max(4, Math.min(22, y))); s.shift(); $('s-' + k).setAttribute('points', s.map((v, i) => `${(i / (s.length - 1) * 160).toFixed(1)},${v.toFixed(1)}`).join(' ')); }
let rpm = 1240, lat = 187, last = 0, n = 4127;
const IDS = ['c01','c03','c05','c07','c08','c10','c12','c13','c15','c17','c19','c20'], LANG = ['en','kn','kn','en','kn'], COND = ['clean','clean','truncated','clean','small_model'];
function tick() {
  rpm = Math.round(Math.max(1180, Math.min(1310, rpm + (rnd() - .5) * 26)));
  lat = Math.round(Math.max(160, Math.min(215, lat + (rnd() - .5) * 14)));
  $('rpm').textContent = rpm.toLocaleString('en-US'); $('lat').textContent = lat + 'ms';
  push('rpm', 13 + (1245 - rpm) / 12); push('lat', 13 + (lat - 187) / 6); push('up', 13.5 + (rnd() - .5) * 2); push('err', 16 + (rnd() - .5) * 1.2);
  last = 0; $('clk').textContent = 'updated just now';
}
function logLine() {
  const id = IDS[Math.floor(rnd() * IDS.length)], lg = LANG[Math.floor(rnd() * LANG.length)], cd = COND[Math.floor(rnd() * COND.length)];
  const ms = 150 + ((n++ * 37) % 90);
  const log = $('log');
  log.insertAdjacentHTML('afterbegin', `<div>POST /classify  ${id}  ${lg}  ${cd.padEnd(11, ' ')}  <b>200 OK</b>  ${ms} ms</div>`);
  while (log.children.length > 4) log.lastChild.remove();
}
for (let i = 0; i < 3; i++) logLine();
setInterval(tick, 2400);
setInterval(logLine, 1300);
setInterval(() => { last += 1; $('clk').textContent = last < 2 ? 'updated just now' : `updated ${last}s ago`; }, 1000);
</script>
"""


def _spark(points: str) -> str:
    return (f'<svg viewBox="0 0 160 26" preserveAspectRatio="none"><polyline fill="none" stroke="#34a853" '
            f'stroke-width="1.6" points="{points}"/></svg>')


def _section(title: str, lede: str = "") -> None:
    st.markdown(f'<div class="sc-sec"><h3>{title}</h3>{f"<p>{lede}</p>" if lede else ""}</div>', unsafe_allow_html=True)


def page_overview() -> None:
    st.markdown(
        '<div class="sc-hero">'
        '<div class="sc-eyebrow"><i></i>Manipal Hackathon · Cascading Failure · SDG 11</div>'
        '<div class="sc-title">SILENT <span>CASCADE</span></div>'
        '<p class="sc-lede">Cities monitor every physical asset. Nothing monitors the AI that decides which asset '
        'gets fixed first — and it degrades silently, worst on the citizens least able to escalate.</p>'
        '<div class="sc-meta"><span><b>Network</b> Bhopal, MP · OpenStreetMap</span>'
        '<span><b>Domain</b> Disaster Resilience &amp; Critical Infrastructure</span>'
        '<span><b>Theme</b> The Butterfly Effect</span></div>'
        "</div>",
        unsafe_allow_html=True,
    )

    _section("The chain we model", "We model <em>delay</em>, not automated dispatch — the only link the published evidence supports.")
    steps = [
        ("Intake", "Citizen complaint", "Kannada · voice → text", ""),
        ("AI layer", "Classification &amp; routing", "department + urgency", ""),
        ("Ops", "Dispatch queue", "position set by category", ""),
        ("Delay", "Repair delay", "wrong SLA, wrong crew", ""),
        ("T+14d", "Equipment fails", "transformer trips", "bad"),
        ("Cascade", "Power &amp; water", "load shed → neighbours trip", "bad"),
        ("Impact", "Households dry, hospital on generator", "buffers are hours, not booleans", "bad"),
    ]
    st.markdown(
        '<div class="sc-flow">' + "".join(
            f'<div class="sc-step {cls}"><span class="sc-k">{k}</span><div class="dot"></div><div class="t">{t}</div><div class="s">{s}</div></div>'
            for k, t, s, cls in steps
        ) + "</div>",
        unsafe_allow_html=True,
    )

    _section("No alarm fired", "Complaint acknowledged. Ticket created. Status green. SLA nominally met — for the category it was assigned to.")
    classifier = (
        '<div class="sc-panel sc-bad">'
        '<div class="hdr"><b style="color:#d93025">What the classifier actually did</b><span>ticket c01 · HTTP 200</span></div>'
        '<p class="sc-text">ನಮ್ಮ ಬೀದಿಯಲ್ಲಿರುವ ಟ್ರಾನ್ಸ್‌ಫಾರ್ಮರ್ ಬಾಕ್ಸ್‌ನಿಂದ ಕಿಡಿಗಳು ಹಾರುತ್ತಿವೆ ಮತ್ತು ಸುಟ್ಟ ವಾಸನೆ ಬರುತ್ತಿದೆ…</p>'
        '<div class="sc-trace">'
        '<div><span class="sc-k">Meaning</span><span>Sparks from the transformer box, smell of burning, children nearby.</span></div>'
        '<div><span class="sc-k">True dept</span><span class="sc-v ok">electrical_emergency</span></div>'
        '<div><span class="sc-k">Routed to</span><span class="sc-v unp">(unparseable) → general queue</span></div>'
        '<div><span class="sc-k">SLA</span><span>14-day maintenance window</span></div>'
        '<div><span class="sc-k">Outcome</span><span class="sc-v bad">equipment failure → cascade</span></div>'
        "</div></div>"
    )
    left, right = st.columns([1.15, 1])
    with left:
        components.html(MONITOR_HTML, height=640)
    with right:
        st.markdown(classifier, unsafe_allow_html=True)
    st.markdown('<p class="sc-cap" style="margin-top:18px">Every dashboard says everything is fine. <b>The thing that failed was a decision, not a server.</b> '
                "Monitoring watches whether the AI answered — not whether it was right.</p>", unsafe_allow_html=True)

    _section("What's real, what's simulated", "Every number in this prototype is one of three things: observed from a named source, measured, or simulated on declared assumptions.")
    rows = [
        ("Substation locations (27)", "OpenStreetMap · power=substation", "Observed", "real"),
        ("Hospital &amp; pump locations (398)", "OpenStreetMap · amenity / man_made", "Observed", "real"),
        ("Feeder topology (grid edges)", "3-nearest-neighbour by haversine", "Inferred", "inf"),
        ("Capacity, load, population served", "config.yaml · seeded uniform draws", "Assumed", "sim"),
        ("Generator / reservoir buffer hours", "8 h · 6 h typical engineering values", "Assumed", "sim"),
        ("Complaint text (20 × 2 languages)", "hand-written, Kannada script", "Synthetic", "syn"),
        ("Routing accuracy by language", "120 classifications, keyword baseline", "Measured", "meas"),
        ("Cascade outcomes, criticality ranking", "cascade.py · deterministic, seed 42", "Simulated", "sim"),
        ("Intervention costs (₹)", "order-of-magnitude placeholders", "Assumed", "sim"),
    ]
    st.markdown(
        '<div class="sc-prov">' + "".join(
            f'<div><span class="k">{k}</span><span class="src">{src}</span><span class="sc-pill {cls}">{status}</span></div>'
            for k, src, status, cls in rows
        ) + "</div>",
        unsafe_allow_html=True,
    )


def page_cascade() -> None:
    cfg = load_config()
    G = load_graph()
    nodes = load_nodes()
    rank = ranking()
    hps = cfg["assumptions"]["hours_per_step"]

    _section("Cascade simulator", "Real Bhopal substations, hospitals and pumps at real coordinates. Load-redistribution cascade, "
             f"{hps:g} h per step. Grid edges are <em>inferred</em> (3 nearest neighbours) — no feeder topology is published.")

    subs = nodes[nodes.type == "substation"].copy()
    labels = {r.id: f"{r.id} · {r.name if isinstance(r.name, str) and r.name else '(unnamed)'} · serves {int(r.population_served):,}" for r in subs.itertuples()}
    default = rank.iloc[0]["node_id"]
    options = list(subs.id)
    node = st.selectbox("Initiating failure", options, index=options.index(default), format_func=labels.get)
    timeline = run_cascade(node)
    final = timeline[-1]
    st.caption(f"Cascade from **{labels[node]}** runs {len(timeline) - 1} steps (T+{final['hours']:.0f}h) and ends with "
               f"**{final['people_affected']:,}** people affected, **{len(final['hospitals_on_generator'])}** hospitals on generator. "
               "Playback is in-browser — the page does not reload while it plays.")

    components.html(cascade_component(nodes, G, timeline, hps, height=620), height=640)
    st.markdown(
        '<span class="sc-pill" style="color:#9aa0a6">● healthy</span> &nbsp;'
        '<span class="sc-pill" style="color:#f5a623">● overloaded &gt;90%</span> &nbsp;'
        '<span class="sc-pill" style="color:#d93025">● failed</span> &nbsp;'
        '<span class="sc-pill">● substation &nbsp; • hospital &nbsp; ■ pump</span> &nbsp; '
        '<span class="sc-pill">hover a node for its state and failure time</span>',
        unsafe_allow_html=True,
    )

    st.write("")
    st.markdown("#### Criticality ranking — by people affected, not by degree")
    st.caption("Each substation failed alone; ranked by total people affected at the final step. This is the ranking a classification node has to beat.")
    st.dataframe(rank, width="stretch", hide_index=True)


def _highlight(text: str, keywords: dict[str, list[str]], true_dept: str) -> str:
    low = text.lower()
    hits: list[tuple[int, int, str]] = []
    for dept in DEPARTMENTS:
        for kw in keywords[dept]:
            k = kw.lower()
            i = 0
            while (i := low.find(k, i)) != -1:
                hits.append((i, i + len(kw), dept))
                i += len(kw)
    hits.sort()
    out, pos = [], 0
    for s, e, dept in hits:
        if s < pos:
            continue
        out.append(html.escape(text[pos:s]))
        cls = "" if dept == true_dept else ' class="wrong"'
        out.append(f"<mark{cls} title='{dept}'>{html.escape(text[s:e])}</mark>")
        pos = e
    out.append(html.escape(text[pos:]))
    return "".join(out)


CASCADE_DEPTS = {"electrical_emergency"}  # complaints whose neglect we link to a substation failure


@st.cache_data
def canary() -> pd.DataFrame:
    return canary_report(load_complaints(), load_config()["d2"])


def _route_card(title: str, r: dict[str, Any], flags: list[str], safety: list[str], cls: str) -> str:
    q = r["queue"]
    sla = r["sla_hours"]
    sla_txt = f"{sla:g} h" if sla < 48 else f"{sla / 24:g} days"
    flag_html = "".join(f'<span class="sc-pill {"inf" if f != "urgency_floor" else "real"}">{f.replace("_", " ")}</span> ' for f in flags)
    flags_block = f'<div style="margin-top:8px">{flag_html}</div>' if flags else ""
    safety_html = f'<div class="sc-k" style="margin-top:8px">Safety terms seen</div><div class="sc-v">{", ".join(safety)}</div>' if safety else ""
    q_cls = "unp" if q == "verification" else ("ok" if cls == "sc-ok" else "bad")
    return (
        f'<div class="sc-panel {cls}"><div class="hdr"><b>{title}</b></div>'
        f'<div class="sc-k">Queue</div><div class="sc-v {q_cls}">{q}</div>'
        f'<div class="sc-k" style="margin-top:8px">Time to repair (SLA)</div><div class="sc-big" style="font-size:22px">{sla_txt}</div>'
        f"{flags_block}{safety_html}</div>"
    )


def page_language() -> None:
    cfg = load_config()
    d2 = cfg["d2"]
    complaints = load_complaints()
    truncate = d2["truncate_chars"]
    ttf = d2["time_to_failure_hours"]

    _section("Language routing — the AI injection, traced end to end",
             "One complaint, one degraded condition, followed from the classifier's decision to the substation. "
             "The classifier is the exact <code>classify_one()</code> that produced outputs/d2_results.csv — a keyword baseline, "
             "<em>not a production LLM</em>. The guard and the monitor are the fix.")

    c = st.columns([2, 1, 1])
    with c[0]:
        cid = st.selectbox("Complaint", list(complaints.id), format_func=lambda i: f"{i} · {complaints.set_index('id').loc[i, 'text_en'][:60]}…")
    with c[1]:
        lang = st.radio("Language", ["English", "ಕನ್ನಡ (native)"], horizontal=True)
    with c[2]:
        cond = st.radio("Condition", CONDITIONS, horizontal=True)

    row = complaints.set_index("id").loc[cid]
    full = row["text_en"] if lang == "English" else row["text_native"]
    is_en = _looks_english(full)
    g = route_with_guard(full, cond, d2)
    pred, wrong = g["predicted"], g["predicted"] != row["true_dept"]
    seen, kws = condition_input(full, cond, truncate)

    st.session_state.reqn = st.session_state.get("reqn", 4127) + 1
    ms = 150 + (st.session_state.reqn * 37) % 90

    # ---- 1. what the classifier saw and decided
    st.markdown("#### 1 · The decision")
    left, right = st.columns([1.3, 1])
    with left:
        body = _highlight(seen, kws, row["true_dept"])
        if cond == "truncated":
            body += f"<s>{html.escape(full[truncate:])}</s>"
        st.markdown(f'<div class="sc-card"><div class="sc-k">Input · {cond}</div><p class="sc-text">{body}</p></div>', unsafe_allow_html=True)
        st.markdown(f'<p class="sc-log" style="margin-top:8px">POST /classify {cid} {"en" if is_en else "kn"} {cond} <b>200 OK</b> {ms} ms</p>', unsafe_allow_html=True)
    with right:
        verdict = "correct · right queue" if not wrong else ("MISROUTED · wrong queue, wrong SLA" if pred else "DROPPED · unparseable")
        vcls = "ok" if not wrong else ("bad" if pred else "unp")
        st.markdown(
            f'<div class="sc-card {"sc-bad" if wrong else "sc-ok"}">'
            f'<div class="sc-k">True dept</div><div class="sc-v ok">{row["true_dept"]}</div><br>'
            f'<div class="sc-k">Classifier said</div><div class="sc-v {vcls}">{pred or "(unparseable)"}</div><br>'
            f'<div class="sc-k">Verdict</div><div class="sc-v {vcls}">{verdict}</div><br>'
            f'<div class="sc-k">Score margin (top − 2nd)</div><div class="sc-v">{g["margin"]}</div>'
            "</div>",
            unsafe_allow_html=True,
        )

    # ---- 2. the guard: today vs with a verification checkpoint
    st.markdown("#### 2 · The routing guard — a verification checkpoint on the decision")
    st.caption("The guard sees exactly what the classifier saw. Unparseable or low-confidence decisions go to a 48 h verification queue "
               "(the cited UPPCL window) instead of a general queue; safety terms cap the SLA at the emergency SLA. Other SLAs are labelled assumptions in config.yaml.")
    naive_late = g["naive"]["sla_hours"] >= ttf
    guard_late = g["guarded"]["sla_hours"] >= ttf
    st.markdown(
        '<div class="sc-split">'
        + _route_card("Today · no guard", g["naive"], [], [], "sc-bad" if naive_late else "sc-ok")
        + _route_card("With guard", g["guarded"], g["flags"], g["safety_hits"], "sc-bad" if guard_late else "sc-ok")
        + "</div>",
        unsafe_allow_html=True,
    )

    # ---- 3. close the loop into the physical network
    st.markdown("#### 3 · What that delay does to the network")
    if row["true_dept"] in CASCADE_DEPTS:
        nodes = load_nodes()
        rank = ranking()
        subs = nodes[nodes.type == "substation"]
        labels = {r.id: f"{r.id} · {r.name if isinstance(r.name, str) and r.name else '(unnamed)'}" for r in subs.itertuples()}
        opts = list(subs.id)
        linked = st.selectbox("Substation this complaint sits on", opts, index=opts.index(rank.iloc[0]["node_id"]), format_func=labels.get)
        final = run_cascade(linked)[-1]
        people, hosp = final["people_affected"], len(final["hospitals_on_generator"])

        def outcome(late: bool, sla: float, title: str) -> str:
            if late:
                return (f'<div class="sc-panel sc-bad"><div class="hdr"><b>{title}</b></div>'
                        f'<div class="sc-k">Repair scheduled</div><div class="sc-v bad">T+{sla:g} h — not before the asset fails at T+{ttf:g} h</div>'
                        f'<div class="sc-k" style="margin-top:10px">Cascade from {linked}</div>'
                        f'<div class="sc-big" style="color:#d93025">{people:,}</div><div class="sc-k">people affected · {hosp} hospitals on generator</div></div>')
            return (f'<div class="sc-panel sc-ok"><div class="hdr"><b>{title}</b></div>'
                    f'<div class="sc-k">Repair scheduled</div><div class="sc-v ok">T+{sla:g} h — before the asset fails at T+{ttf:g} h</div>'
                    f'<div class="sc-k" style="margin-top:10px">Cascade</div>'
                    f'<div class="sc-big" style="color:#34a853">0</div><div class="sc-k">people affected · failure prevented</div></div>')

        st.markdown('<div class="sc-split">' + outcome(naive_late, g["naive"]["sla_hours"], "Today · no guard")
                    + outcome(guard_late, g["guarded"]["sla_hours"], "With guard") + "</div>", unsafe_allow_html=True)
        delta = (people if naive_late else 0) - (people if guard_late else 0)
        if delta > 0:
            st.markdown(f'<p class="sc-cap" style="margin-top:14px">One checkpoint on one decision: <b>{delta:,} fewer people affected</b>. '
                        "Same substation, same physics — the only thing that changed is when the repair crew was told.</p>", unsafe_allow_html=True)
        elif naive_late and guard_late:
            st.markdown('<p class="sc-cap" style="margin-top:14px">The guard could not rescue this one — the degraded input hid every signal it looks for. '
                        "That is the honest limit of a check that sees only what the classifier saw.</p>", unsafe_allow_html=True)
        else:
            st.markdown('<p class="sc-cap" style="margin-top:14px">Routed in time either way — no cascade for this complaint.</p>', unsafe_allow_html=True)
    else:
        st.markdown(f'<p class="sc-cap">This complaint is <b>{row["true_dept"]}</b>; the physical cascade model covers electrical faults only, '
                    "so no substation is linked. The routing guard above still applies.</p>", unsafe_allow_html=True)

    # ---- 4. the monitor that should have existed
    st.markdown("#### 4 · Decision monitor — the canary CivicOps never had")
    st.caption("Every request above returned 200. This monitor ignores that and re-runs a golden set of 20 complaints in both languages "
               f"under the live condition, watching accuracy and the unparseable rate per language. It alarms when native-script accuracy "
               f"falls more than {d2['canary_language_gap_alarm_pct']:g} points below English.")
    rep = canary()
    cur = rep[rep.condition == cond].set_index("language")
    base = rep[rep.condition == "clean"].set_index("language")
    gap = base.loc["native", "accuracy_pct"] - cur.loc["native", "accuracy_pct"]
    lang_gap = cur.loc["en", "accuracy_pct"] - cur.loc["native", "accuracy_pct"]
    alarm = lang_gap > d2["canary_language_gap_alarm_pct"]

    def tile(label: str, value: str, ok: bool, sub: str) -> str:
        col = "#34a853" if ok else "#d93025"
        return (f'<div><div class="l">{label}</div><div class="v" style="color:{col}">{value} <i class="gdot" style="background:{col};box-shadow:0 0 8px {col}"></i></div>'
                f'<div class="l" style="margin-top:4px">{sub}</div></div>')

    en_ok = cur.loc["en", "accuracy_pct"] >= base.loc["en", "accuracy_pct"] - d2["canary_language_gap_alarm_pct"]
    kn_ok = not alarm and cur.loc["native", "accuracy_pct"] >= base.loc["native", "accuracy_pct"] - d2["canary_language_gap_alarm_pct"]
    st.markdown(
        f'<div class="sc-panel {"sc-bad" if alarm else "sc-ok"}">'
        f'<div class="hdr"><b>Routing-quality canary · condition: {cond}</b><span>golden set · 20 × 2 languages · re-run now</span></div>'
        '<div class="sc-mgrid">'
        + tile("English accuracy", f"{cur.loc['en', 'accuracy_pct']:.0f}%", en_ok, f"unparseable {cur.loc['en', 'unparseable_pct']:.0f}%")
        + tile("Kannada accuracy", f"{cur.loc['native', 'accuracy_pct']:.0f}%", kn_ok, f"unparseable {cur.loc['native', 'unparseable_pct']:.0f}%")
        + tile("Language gap", f"{lang_gap:+.0f} pts", not alarm, f"alarm above {d2['canary_language_gap_alarm_pct']:g} pts")
        + tile("Drift vs clean (Kannada)", f"{-gap:+.0f} pts", gap <= d2["canary_language_gap_alarm_pct"], "same golden set, clean condition")
        + "</div>"
        + (f'<div class="sc-v bad" style="margin-top:12px">▲ ALARM · native-script routing degraded {lang_gap:.0f} pts below English while every request returned 200</div>' if alarm
           else '<div class="sc-v ok" style="margin-top:12px">● no language divergence on the golden set</div>')
        + "</div>",
        unsafe_allow_html=True,
    )

    st.write("")
    st.markdown("#### Accuracy by language × condition (120 classifications, measured)")
    results = load_csv("d2_results.csv")
    acc = load_csv("d2_accuracy.csv")
    if acc is None or results is None:
        st.info("Run `python src/d2_language.py` to produce outputs/d2_results.csv and d2_accuracy.csv.")
        return
    a, b = st.columns([1.3, 1])
    with a:
        st.pyplot(plot_accuracy(acc, None), width="stretch")
    with b:
        piv = acc.pivot(index="condition", columns="language", values="accuracy_pct").reindex(CONDITIONS)
        piv.columns = ["English" if c == "en" else "Kannada" for c in piv.columns]
        st.dataframe(piv, width="stretch")
        st.markdown('<p class="sc-cap">Truncation shows a real language gap. The small-model condition did not. We report both — we don\'t tune experiments to fit the pitch.</p>', unsafe_allow_html=True)

    ex = misroute_examples(results, complaints)
    st.markdown(f"#### Routed correctly in English, misrouted in Kannada — {len(ex)} cases")
    st.dataframe(ex[["condition", "id", "true_dept", "predicted_en", "predicted_native", "text_en"]], width="stretch", hide_index=True)


def page_intervention() -> None:
    cfg = load_config()
    _section("Intervention comparison — the smallest intervention",
             "Same cascade engine, N random initiating failures shared across all three conditions (paired). "
             "Costs are <em>order-of-magnitude assumptions</em> from config.yaml, not quotes.")
    n_runs = st.slider("Runs per condition", 20, 200, cfg["d4"]["n_runs"], 10)
    if st.button("Run comparison", type="primary") or "d4" in st.session_state:
        with st.spinner(f"Running {n_runs} × 3 cascades…"):
            conditions, top_node = run_interventions(n_runs)
        st.session_state.d4 = True
        means = [sum(v) / n_runs for _, v, _ in conditions]
        base = means[0]
        cols = st.columns(3)
        for col, (label, vals, cost), mean in zip(cols, conditions, means):
            delta = None if mean == base else f"{(mean - base) / base * 100:+.1f}%"
            col.metric(f"{label.replace(chr(10), ' ')} · people affected", f"{mean:,.0f}", delta, delta_color="inverse")
            col.caption(f"cost ~₹{cost:,.0f}" if cost else "cost ₹0")
        st.pyplot(plot_comparison(conditions, n_runs, None), width="stretch")
        st.markdown(f'<p class="sc-cap">Hardened node: <b>{top_node}</b> (capacity × 1.5). Checkpoint modelled as preventing the initiating failure in '
                    f'{cfg["d4"]["verification_checkpoint_prevention_rate"]:.0%} of runs — an assumption, labelled as such.</p>', unsafe_allow_html=True)
    else:
        summary = load_csv("d4_summary.csv")
        if summary is not None:
            st.caption("Precomputed result from outputs/d4_summary.csv — press Run to recompute live.")
            st.dataframe(summary, width="stretch", hide_index=True)


# ---------------------------------------------------------------- router

PAGES = {
    "Overview": page_overview,
    "Cascade simulator": page_cascade,
    "Language routing": page_language,
    "Intervention comparison": page_intervention,
}

with st.sidebar:
    st.markdown('<div class="sc-eyebrow">Silent Cascade</div>', unsafe_allow_html=True)
    choice = st.radio("Section", list(PAGES), label_visibility="collapsed")
    st.markdown("---")
    st.caption("Prototype · scenario-based stress testing, not prediction. Every edge carries a provenance label; every assumption lives in config.yaml.")

PAGES[choice]()
