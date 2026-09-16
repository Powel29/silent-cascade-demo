"""Silent Cascade Decision Firewall — interactive intervention prototype (Streamlit).

A thin UI over the repo's pure functions. Every decision shown here is produced by
src/decision_firewall.py (the same code the offline evaluation scores), every cascade by
src/cascade.py, every classifier result by src/d2_language.py. Nothing is reimplemented in the
app layer and nothing here sends a real message, creates a real ticket or dispatches anyone.

UI principle: structure explains itself. The pipeline ribbon carries the architecture, each
reason code sits in the stage that produced it, and every control shows its own meaning — so a
judge can read the demo cold without a narrator and without paragraphs of explanation.

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

from cascade import cascade, summarize_final  # noqa: E402
from d2_language import CONDITIONS, DEPARTMENTS, canary_report, condition_input, plot_accuracy  # noqa: E402
from decision_firewall import (  # noqa: E402
    advance_acknowledgement,
    build_asset_context,
    reliability_state_from_canary,
    run_firewall,
)
from evaluate_firewall import LABELS, PRIMARY_CONFIGURATIONS  # noqa: E402

st.set_page_config(page_title="Silent Cascade Decision Firewall", page_icon="⚡", layout="wide")

st.markdown(
    """
    <style>
      .sc-eyebrow { font-family: monospace; font-size: 11.5px; letter-spacing: .16em; text-transform: uppercase; color: #9aa0a6; }
      .sc-title { font-size: clamp(26px, 3.2vw, 38px); font-weight: 800; letter-spacing: .03em; line-height: 1.05; margin: 4px 0 4px; }
      .sc-title span { color: #d93025; }
      .sc-q { color: #cfd2d6; font-size: 15px; margin: 0 0 4px; }
      .sc-cap { font-family: monospace; font-size: 12.5px; color: #9aa0a6; line-height: 1.5; margin: 6px 0 0; }
      .sc-card { background: #171b21; border: 1px solid #262b33; border-radius: 10px; padding: 14px 16px; height: 100%; }
      .sc-k { font-family: monospace; font-size: 10.5px; letter-spacing: .08em; text-transform: uppercase; color: #9aa0a6; margin-top: 10px; }
      .sc-k:first-child { margin-top: 0; }
      .sc-v { font-family: monospace; font-size: 14px; color: #e8eaed; }
      .sc-v.bad { color: #d93025; font-weight: 700; } .sc-v.ok { color: #34a853; } .sc-v.unp { color: #f5a623; font-weight: 700; }
      .sc-text { font-size: 15px; line-height: 1.6; margin: 4px 0 0; }
      .sc-text mark { background: rgba(66,133,244,.22); color: inherit; border-bottom: 1px solid #4285f4; padding: 0 1px; }
      .sc-text mark.wrong { background: rgba(217,48,37,.22); border-bottom-color: #d93025; }
      .sc-text mark.haz { background: rgba(217,48,37,.3); border-bottom: 2px solid #d93025; font-weight: 600; }
      .sc-text s { color: #6b7280; text-decoration-color: rgba(217,48,37,.6); }
      .sc-pill { display: inline-block; font-family: monospace; font-size: 10.5px; letter-spacing: .06em; text-transform: uppercase; padding: 2px 8px; border-radius: 999px; border: 1px solid #343b46; color: #9aa0a6; margin: 2px 3px 2px 0; }
      .sc-pill.real { color: #34a853; border-color: rgba(52,168,83,.5); } .sc-pill.meas { color: #4285f4; border-color: rgba(66,133,244,.5); }
      .sc-pill.inf { color: #f5a623; border-color: rgba(245,166,35,.5); } .sc-pill.red { color: #d93025; border-color: rgba(217,48,37,.6); }

      /* --- pipeline ribbon: the architecture, told by structure instead of prose --- */
      /* minmax(0,…) lets a track shrink below its longest token, so one long reason code cannot
         steal width from the decision tile; the decision tile gets the extra weight. */
      .sc-ribbon { display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)) minmax(0, 1.35fr); gap: 9px; margin: 4px 0 14px; }
      .sc-rt { position: relative; background: #171b21; border: 1px solid #262b33; border-top: 3px solid #4a5160; border-radius: 10px; padding: 9px 11px 10px; min-height: 104px; }
      .sc-rt .n { font-family: monospace; font-size: 10px; color: #6b7280; }
      .sc-rt .s { font-family: monospace; font-size: 10px; letter-spacing: .09em; text-transform: uppercase; color: #9aa0a6; margin-top: 1px; }
      .sc-rt .v { font-size: 14.5px; font-weight: 700; line-height: 1.25; margin-top: 5px; color: #e8eaed; overflow-wrap: anywhere; }
      .sc-rt .g { font-family: monospace; font-size: 10.5px; color: #6b7280; margin-top: 4px; line-height: 1.4; overflow-wrap: anywhere; }
      .sc-rt .c { margin-top: 6px; }
      .sc-rt.red { border-top-color: #d93025; background: rgba(217,48,37,.07); } .sc-rt.red .v { color: #ff6b5e; }
      .sc-rt.amber { border-top-color: #f5a623; background: rgba(245,166,35,.06); } .sc-rt.amber .v { color: #f5a623; }
      .sc-rt.green { border-top-color: #34a853; } .sc-rt.green .v { color: #34a853; }
      .sc-rt.last { border-width: 2px; border-top-width: 3px; }
      .sc-rt.last .v { font-size: 26px; letter-spacing: .04em; font-family: monospace; }
      .sc-rt.last.red { border-color: rgba(217,48,37,.7); } .sc-rt.last.yellow { border-color: rgba(245,166,35,.7); }
      .sc-rt.last.green { border-color: rgba(52,168,83,.6); }
      .sc-rt.yellow { border-top-color: #f5a623; background: rgba(245,166,35,.06); } .sc-rt.yellow .v { color: #f5a623; }
      .sc-rt:not(:last-child)::after { content: '▸'; position: absolute; right: -8px; top: 46%; color: #4a5160; font-size: 13px; z-index: 2; }
      .sc-chip { display: inline-block; font-family: monospace; font-size: 9.5px; letter-spacing: .04em; padding: 2px 6px; border-radius: 4px; margin: 2px 3px 0 0;
                 background: rgba(217,48,37,.18); border: 1px solid rgba(217,48,37,.45); color: #ff8a80; overflow-wrap: anywhere; }
      .sc-chip.y { background: rgba(245,166,35,.15); border-color: rgba(245,166,35,.45); color: #f5c26b; }
      .sc-chip.g { background: rgba(52,168,83,.14); border-color: rgba(52,168,83,.45); color: #7bcf95; }
      @media (max-width: 1100px) { .sc-ribbon { grid-template-columns: repeat(3, minmax(0, 1fr)); } .sc-rt::after { display: none; } }
      @media (max-width: 640px) { .sc-ribbon { grid-template-columns: minmax(0, 1fr); } }

      /* --- verdict --- */
      .sc-risk { border-radius: 14px; padding: 20px 24px; margin: 0 0 10px; border: 2px solid; }
      .sc-risk .lvl { font-family: monospace; font-size: clamp(22px, 2.9vw, 34px); font-weight: 800; letter-spacing: .03em; line-height: 1.1; }
      .sc-risk .sub { font-size: 15.5px; margin-top: 7px; line-height: 1.5; color: #e8eaed; }
      .sc-risk .why { font-size: 13.5px; margin-top: 8px; color: #cfd2d6; }
      .sc-risk.red { background: rgba(217,48,37,.14); border-color: #d93025; box-shadow: 0 0 40px rgba(217,48,37,.26); }
      .sc-risk.red .lvl { color: #ff6b5e; }
      .sc-risk.yellow { background: rgba(245,166,35,.12); border-color: #f5a623; box-shadow: 0 0 28px rgba(245,166,35,.16); }
      .sc-risk.yellow .lvl { color: #f5a623; }
      .sc-risk.green { background: rgba(52,168,83,.10); border-color: #34a853; box-shadow: 0 0 28px rgba(52,168,83,.13); }
      .sc-risk.green .lvl { color: #34a853; }

      .sc-delta { font-family: monospace; font-size: 13px; padding: 8px 14px; border-radius: 8px; margin: 0 0 10px;
                  background: rgba(66,133,244,.12); border: 1px solid rgba(66,133,244,.45); color: #9ec1fa; }
      .sc-safe { border-radius: 9px; padding: 9px 14px; font-family: monospace; font-size: 12.5px; border: 1px solid; margin-bottom: 10px; }
      .sc-safe.on { background: rgba(245,166,35,.12); border-color: #f5a623; color: #f5a623; }
      .sc-safe.off { background: rgba(52,168,83,.07); border-color: rgba(52,168,83,.4); color: #34a853; }
      .sc-safe b { letter-spacing: .08em; }
      .sc-safe span { color: #9aa0a6; }

      .sc-split { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 14px; }
      .sc-panel { background: #171b21; border: 1px solid #262b33; border-radius: 12px; padding: 15px 18px; }
      .sc-panel.bad { border-color: rgba(217,48,37,.6); box-shadow: 0 0 22px rgba(217,48,37,.14); }
      .sc-panel.ok { border-color: rgba(52,168,83,.5); box-shadow: 0 0 22px rgba(52,168,83,.1); }
      .sc-panel .hdr { font-family: monospace; font-size: 12px; letter-spacing: .12em; font-weight: 700; margin-bottom: 9px; }
      .sc-panel.bad .hdr { color: #ff6b5e; } .sc-panel.ok .hdr { color: #34a853; }
      .sc-big { font-family: monospace; font-size: 27px; font-weight: 700; line-height: 1.1; margin-top: 6px; font-variant-numeric: tabular-nums; }
      .sc-wo { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 9px; }
      .sc-wo > div { background: #1d222a; border: 1px solid #262b33; border-radius: 8px; padding: 9px 11px; }

      /* --- evidence table --- */
      .sc-tbl { width: 100%; border-collapse: collapse; font-size: 14px; }
      .sc-tbl th, .sc-tbl td { padding: 10px 12px; border-bottom: 1px solid #262b33; text-align: right; }
      .sc-tbl th:first-child, .sc-tbl td:first-child { text-align: left; }
      .sc-tbl thead th { font-family: monospace; font-size: 11px; letter-spacing: .08em; text-transform: uppercase; color: #9aa0a6; border-bottom: 1px solid #343b46; }
      .sc-tbl thead th.win { color: #ff6b5e; }
      .sc-tbl td { font-family: monospace; font-variant-numeric: tabular-nums; }
      .sc-tbl td:first-child { font-family: inherit; color: #e8eaed; }
      .sc-tbl tr.cost td:first-child::after { content: ' (cost)'; color: #6b7280; font-size: 12px; }
      .sc-tbl td.best { color: #34a853; font-weight: 700; } .sc-tbl td.worst { color: #d93025; font-weight: 700; }
      .sc-tbl tbody tr:hover { background: rgba(255,255,255,.02); }

      .sc-prov { border: 1px solid #262b33; border-radius: 12px; background: #171b21; padding: 2px 18px; }
      .sc-prov > div { display: grid; grid-template-columns: 1.3fr 1fr auto; gap: 14px; align-items: center; padding: 10px 0; border-bottom: 1px solid #262b33; font-size: 14px; }
      .sc-prov > div:last-child { border-bottom: 0; }
      .sc-prov .src { font-family: monospace; font-size: 12px; color: #9aa0a6; }
      .sc-mon div { display: flex; justify-content: space-between; padding: 5px 0; border-bottom: 1px solid #262b33; font-family: monospace; font-size: 12.5px; }
      .sc-mon div:last-child { border-bottom: 0; } .sc-mon em { font-style: normal; color: #34a853; }
      @media (max-width: 640px) { .sc-prov > div { grid-template-columns: 1fr; gap: 3px; } }
    </style>
    """,
    unsafe_allow_html=True,
)


# ---------------------------------------------------------------- data loading (fail loudly, never default silently)


def _mtime(rel: str) -> float:
    p = REPO_ROOT / rel
    return p.stat().st_mtime if p.exists() else -1.0


_SIG = (_mtime("data/processed/graph.gpickle"), _mtime("outputs/d1_criticality.csv"), _mtime("config.yaml"))
if st.session_state.get("_sig") != _SIG:
    st.cache_data.clear()
    st.cache_resource.clear()
    st.session_state["_sig"] = _SIG


def require(rel: str, command: str) -> Path:
    p = REPO_ROOT / rel
    if not p.exists():
        st.error(f"Missing required file `{rel}`. Generate it with:\n\n```bash\n{command}\n```")
        st.stop()
    return p


@st.cache_data
def load_config(_sig: tuple) -> dict[str, Any]:
    with open(REPO_ROOT / "config.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)


@st.cache_resource
def load_graph(_sig: tuple):
    with open(require("data/processed/graph.gpickle", "python src/build_graph.py"), "rb") as f:
        return pickle.load(f)


@st.cache_data
def load_nodes() -> pd.DataFrame:
    return pd.read_csv(require("data/processed/nodes.csv", "python src/build_graph.py"))


@st.cache_data
def load_complaints() -> pd.DataFrame:
    return pd.read_csv(require("data/complaints.csv", "git checkout data/complaints.csv"))


@st.cache_data
def load_scenarios() -> pd.DataFrame:
    df = pd.read_csv(require("data/scenarios.csv", "git checkout data/scenarios.csv"), dtype={"structured_hazard": "string"})
    df["structured_hazard"] = df["structured_hazard"].fillna("")
    df["structured_immediate_danger"] = df["structured_immediate_danger"].astype(str).str.lower().isin(["true", "1", "yes"])
    return df


@st.cache_data
def load_ranking(_sig: tuple) -> pd.DataFrame:
    df = pd.read_csv(require("outputs/d1_criticality.csv", "python src/d1_cascade.py"))
    if "rank" not in df.columns or "criticality_percentile" not in df.columns:
        st.error("`outputs/d1_criticality.csv` is a legacy top-10 slice without rank/percentile. Regenerate the full ranking:\n\n```bash\npython src/d1_cascade.py\n```")
        st.stop()
    return df


@st.cache_data
def load_csv(name: str) -> pd.DataFrame | None:
    p = REPO_ROOT / "outputs" / name
    return pd.read_csv(p) if p.exists() else None


@st.cache_data
def canary(_sig: tuple) -> pd.DataFrame:
    return canary_report(load_complaints(), load_config(_SIG)["d2"])


@st.cache_data
def run_cascade(node_id: str, _sig: tuple) -> list[dict[str, Any]]:
    cfg = load_config(_SIG)
    return cascade(load_graph(_SIG), [node_id], max_steps=cfg["d1"]["max_steps"], hours_per_step=cfg["assumptions"]["hours_per_step"])


CFG = load_config(_SIG)
FW = CFG["firewall"]


# ---------------------------------------------------------------- map (client-side Leaflet, no reruns)

MAP_HTML = r"""
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<style>
  html, body { margin: 0; background: #0f1216; font-family: "Source Sans Pro", "Segoe UI", sans-serif; color: #e8eaed; }
  #wrap { position: relative; width: 100%; height: __H__px; border-radius: 10px; overflow: hidden; border: 1px solid #343b46; background: #0b0d10; }
  #map { position: absolute; inset: 0; }
  .leaflet-tile-pane { filter: brightness(.62) saturate(.7); }
  .hud { position: absolute; left: 12px; top: 12px; z-index: 1000; display: grid; gap: 4px; min-width: 230px; pointer-events: none;
         background: rgba(15,18,22,.88); border: 1px solid #343b46; border-radius: 8px; padding: 10px 12px; font-family: monospace; }
  .hud div { display: flex; justify-content: space-between; gap: 16px; align-items: baseline; font-size: 12px; }
  .hud .k { color: #9aa0a6; font-size: 10px; letter-spacing: .08em; text-transform: uppercase; }
  .hud b { font-weight: 700; color: #e8eaed; font-size: 14px; font-variant-numeric: tabular-nums; }
  .hud .t b { font-size: 21px; color: #d93025; } .hud .p b { color: #d93025; }
  .hud .lbl { font-size: 9.5px; color: #6b7280; letter-spacing: .06em; text-transform: uppercase; }
  .ctl { position: absolute; left: 12px; right: 12px; bottom: 12px; z-index: 1000; display: flex; gap: 8px; align-items: center; flex-wrap: wrap;
         background: rgba(15,18,22,.88); border: 1px solid #343b46; border-radius: 8px; padding: 7px 10px; }
  .btn { font-family: monospace; font-size: 12px; color: #0f1216; background: #e8eaed; border: 0; border-radius: 6px; padding: 6px 11px; cursor: pointer; font-weight: 700; white-space: nowrap; }
  .btn.ghost { background: transparent; color: #cfd2d6; border: 1px solid #343b46; font-weight: 500; }
  input[type=range] { flex: 1; min-width: 120px; accent-color: #d93025; }
  .attrib { margin-left: auto; font-family: monospace; font-size: 10px; color: rgba(232,234,237,.55); white-space: nowrap; }
  .attrib a { color: inherit; }
  .leaflet-control-attribution { display: none; }
  .leaflet-tooltip { background: rgba(15,18,22,.95); color: #e8eaed; border: 1px solid #343b46; font-family: monospace; font-size: 11px; }
  .pump { width: 9px; height: 9px; border: 1px solid #000; box-sizing: border-box; }
  .leaflet-marker-icon.pump { background: var(--c, #9aa0a6); }
</style>
<div id="wrap">
  <div id="map"></div>
  <div class="hud">
    <div class="t"><span class="k">Elapsed</span><b id="h-t">T+0.0h</b></div>
    <div class="p"><span class="k">Simulated exposure</span><b id="h-p">0</b></div>
    <div><span class="k">Substations tripped</span><b id="h-s">0</b></div>
    <div><span class="k">Hospitals on generator</span><b id="h-h">0</b></div>
    <div><span class="k">Hospitals without power</span><b id="h-ho">0</b></div>
    <div><span class="k">Wards without water</span><b id="h-w">0</b></div>
    <div class="lbl">simulated · assumed loads · inferred topology</div>
  </div>
  <div class="ctl">
    <button class="btn" id="play">❚❚ Pause</button>
    <button class="btn ghost" id="restart">↺</button>
    <input type="range" id="scrub" min="0" max="__LAST__" step="0.01" value="0">
    <button class="btn ghost" id="fit">⤢ fit</button>
    <span class="attrib">© <a href="https://www.openstreetmap.org/copyright" target="_blank">OpenStreetMap</a> contributors</span>
  </div>
</div>
<script>
const D = __DATA__;
const C = { healthy: '#9aa0a6', over: '#f5a623', backup: '#f5a623', failed: '#d93025' };
const map = L.map('map', { zoomControl: false, attributionControl: false });
L.control.zoom({ position: 'topright' }).addTo(map);
L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', { maxZoom: 18 }).addTo(map);
const bounds = L.latLngBounds(D.nodes.map(n => [n[0], n[1]]));
map.fitBounds(bounds.pad(0.08));
const failAt = new Array(D.nodes.length).fill(Infinity), backupAt = new Array(D.nodes.length).fill(Infinity);
const overAt = D.nodes.map(() => new Set());
D.steps.forEach(s => {
  const n = s.new.length;
  s.new.forEach((i, k) => { failAt[i] = s.step + (n > 1 ? (k / n) * 0.8 : 0); });
  s.backup.forEach(i => { backupAt[i] = Math.min(backupAt[i], s.step); });
  s.over.forEach(i => overAt[i].add(s.step));
});
const stateOf = (i, t) => failAt[i] <= t ? 'failed' : backupAt[i] <= t ? 'backup' : overAt[i].has(Math.floor(t)) ? 'over' : 'healthy';
const edgeLayers = D.edges.map(([a, b]) => L.polyline([[D.nodes[a][0], D.nodes[a][1]], [D.nodes[b][0], D.nodes[b][1]]], { color: '#6b7280', weight: 1.4, opacity: .8, interactive: false }).addTo(map));
const markers = D.nodes.map((n, i) => {
  const [lat, lon, type, id, name, pop] = n;
  const label = `<b>${name || id}</b><br>${['substation','hospital','pump'][type]}${type === 0 ? ` · simulated service population ${pop.toLocaleString('en-US')}` : ''}<br><span id="tt-${i}"></span>`;
  let m;
  if (type === 2) m = L.marker([lat, lon], { icon: L.divIcon({ className: 'pump', iconSize: [9, 9] }), interactive: true });
  else m = L.circleMarker([lat, lon], { radius: type === 0 ? 7 : 3, color: type === 0 ? '#000' : C.healthy, weight: type === 0 ? 1 : 2, fillColor: C.healthy, fillOpacity: .95 });
  m.bindTooltip(label, { direction: 'top', offset: [0, -6] });
  m.addTo(map);
  return m;
});
const TYPE = D.nodes.map(n => n[2]);
const fmt = v => v.toLocaleString('en-US');
let t = 0, playing = true, secPerStep = 2.5, last = 0;
const LAST = D.steps.length - 1;
function paint() {
  const step = Math.floor(t);
  D.nodes.forEach((n, i) => {
    const s = stateOf(i, t), col = C[s];
    const m = markers[i];
    if (TYPE[i] === 2) { const el = m.getElement(); if (el) el.style.background = col; }
    else m.setStyle(TYPE[i] === 0 ? { fillColor: col } : { fillColor: col, color: col });
    const tt = document.getElementById('tt-' + i);
    if (tt) tt.textContent = s === 'failed' ? `${TYPE[i] === 0 ? 'TRIPPED' : 'SERVICE OUTAGE'} at T+${(failAt[i] * D.hps).toFixed(1)}h` : s === 'backup' ? `ON BACKUP since T+${(backupAt[i] * D.hps).toFixed(1)}h` : s.toUpperCase();
  });
  D.edges.forEach(([a, b], k) => {
    const fa = failAt[a] <= t, fb = failAt[b] <= t;
    edgeLayers[k].setStyle({ color: fa && fb ? C.failed : (fa || fb) ? C.over : '#6b7280', opacity: fa || fb ? .9 : .7 });
  });
  const s = D.steps[step];
  document.getElementById('h-t').textContent = `T+${(t * D.hps).toFixed(1)}h`;
  document.getElementById('h-p').textContent = fmt(s.people);
  document.getElementById('h-s').textContent = `${s.subs} / ${D.nsub}`;
  document.getElementById('h-h').textContent = fmt(s.hosp_gen);
  document.getElementById('h-ho').textContent = fmt(s.hosp_out);
  document.getElementById('h-w').textContent = fmt(s.water_out);
  document.getElementById('scrub').value = t;
}
function loop(ts) {
  const dt = last ? (ts - last) / 1000 : 0; last = ts;
  if (playing) { t = Math.min(LAST, t + dt / secPerStep); if (t >= LAST) { playing = false; document.getElementById('play').textContent = '↺ Replay'; } paint(); }
  requestAnimationFrame(loop);
}
const playBtn = document.getElementById('play');
playBtn.onclick = () => { if (playing) { playing = false; playBtn.textContent = t >= LAST ? '↺ Replay' : '▶ Play'; } else { if (t >= LAST) t = 0; playing = true; playBtn.textContent = '❚❚ Pause'; } };
document.getElementById('restart').onclick = () => { t = 0; playing = true; playBtn.textContent = '❚❚ Pause'; paint(); };
document.getElementById('fit').onclick = () => map.fitBounds(bounds.pad(0.08));
document.getElementById('scrub').oninput = e => { t = +e.target.value; playing = false; playBtn.textContent = t >= LAST ? '↺ Replay' : '▶ Play'; paint(); };
paint();
requestAnimationFrame(loop);
</script>
"""


def cascade_component(nodes: pd.DataFrame, G, timeline: list[dict[str, Any]], hours_per_step: float, height: int = 520) -> str:
    """Self-contained Leaflet page: whole timeline embedded, animated client-side. OSM names are
    JSON-encoded (never interpolated into markup) and rendered via textContent/tooltip."""
    idx = {nid: i for i, nid in enumerate(nodes.id)}
    tcode = {"substation": 0, "hospital": 1, "pump": 2}
    node_list = [
        [round(float(r.lat), 5), round(float(r.lon), 5), tcode[r.type], r.id,
         html.escape(r.name) if isinstance(r.name, str) else "", int(r.population_served) if r.type == "substation" else 0]
        for r in nodes.itertuples()
    ]
    edges = [[idx[u], idx[v]] for u, v, d in G.edges(data=True) if d["type"] == "grid" and u < v]
    prev_failed: set[str] = set()
    prev_backup: set[str] = set()
    steps = []
    for s in timeline:
        new = sorted(idx[n] for n in s["failed"] - prev_failed)
        backup = sorted(idx[n] for n in s["on_backup"] - prev_backup)
        prev_failed, prev_backup = set(s["failed"]), set(s["on_backup"])
        steps.append({
            "step": s["step"], "new": new, "backup": backup, "over": sorted(idx[n] for n in s["overloaded"]),
            "people": s["people_affected"], "subs": len(s["failed_substations"]),
            "hosp_gen": len(s["hospitals_on_generator"]), "hosp_out": len(s["hospitals_without_power"]),
            "water_out": len(s["wards_without_water"]),
        })
    data = {"nodes": node_list, "edges": edges, "steps": steps, "hps": hours_per_step, "nsub": int((nodes.type == "substation").sum())}
    return (MAP_HTML.replace("__DATA__", json.dumps(data, ensure_ascii=False).replace("</", "<\\/"))
            .replace("__LAST__", str(len(timeline) - 1)).replace("__H__", str(height)))


# ---------------------------------------------------------------- small helpers

E = html.escape

# Which pipeline stage each reason code belongs to, so a reason is shown inside the stage that
# produced it instead of in a separate list of sentences. Unmapped codes fall through to the
# decision tile, so a new reason code can never silently disappear from the UI.
REASON_STAGE: dict[str, int] = {
    "STRUCTURED_IMMEDIATE_DANGER": 0,
    "UNPARSEABLE_CLASSIFICATION": 1, "LOW_MARGIN": 1, "TRUNCATED_CLASSIFIER_INPUT": 1,
    "DIRECT_HAZARD": 2, "DANGEROUS_DOWNGRADE": 2, "CONFLICTING_SIGNALS": 2,
    "VERY_HIGH_ASSET_CRITICALITY": 3, "HIGH_ASSET_CRITICALITY": 3, "ASSET_CONTEXT_MISSING": 3, "REPAIR_WINDOW_AT_RISK": 3,
    "RELIABILITY_DEGRADED": 4, "RELIABILITY_UNAVAILABLE": 4,
}

# Short plain-language chip for each stable reason code. The code itself is never lost: it is
# the chip's tooltip and it is listed verbatim next to its full sentence in the reasons expander.
SHORT_REASON: dict[str, str] = {
    "STRUCTURED_IMMEDIATE_DANGER": "immediate danger",
    "DIRECT_HAZARD": "direct hazard",
    "DANGEROUS_DOWNGRADE": "dangerous downgrade",
    "UNPARSEABLE_CLASSIFICATION": "unparseable",
    "LOW_MARGIN": "low margin",
    "TRUNCATED_CLASSIFIER_INPUT": "input cut off",
    "VERY_HIGH_ASSET_CRITICALITY": "very high consequence",
    "HIGH_ASSET_CRITICALITY": "high consequence",
    "REPAIR_WINDOW_AT_RISK": "repair too late",
    "RELIABILITY_DEGRADED": "quality degraded",
    "RELIABILITY_UNAVAILABLE": "no quality signal",
    "ASSET_CONTEXT_MISSING": "no asset context",
    "CONFLICTING_SIGNALS": "signals conflict",
    "MISSING_REQUIRED_FIELD": "missing data",
    "SAFE_AUTOMATION_ALLOWED": "safe to automate",
}

COND_LABEL = {"clean": "full text", "truncated": "cut to 40 chars", "small_model": "smaller model"}
REL_LABEL = {"auto": "auto (from quality check)", "normal": "healthy", "degraded": "degraded", "unavailable": "no signal"}
LEVEL_WORD = {"red": "RED", "yellow": "YELLOW", "green": "GREEN"}
CHIP_CLS = {"red": "", "yellow": "y", "green": "g"}


def _pill(text: str, cls: str = "") -> str:
    return f'<span class="sc-pill {cls}">{E(text)}</span>'


def _cap(text: str) -> None:
    st.markdown(f'<p class="sc-cap">{text}</p>', unsafe_allow_html=True)


def _highlight(text: str, keywords: dict[str, list[str]] | None, hazard_terms: list[str], predicted: str) -> str:
    """Escape the complaint text and wrap classifier keyword hits / hazard-scan hits in <mark>."""
    low = text.lower()
    hits: list[tuple[int, int, str]] = []
    for term in hazard_terms:
        k, i = term.lower(), 0
        while k and (i := low.find(k, i)) != -1:
            hits.append((i, i + len(k), "haz"))
            i += len(k)
    for dept in DEPARTMENTS if keywords else []:
        for kw in keywords[dept]:
            k, i = kw.lower(), 0
            while (i := low.find(k, i)) != -1:
                hits.append((i, i + len(kw), "" if dept == predicted else "wrong"))
                i += len(kw)
    hits.sort(key=lambda h: (h[0], 0 if h[2] == "haz" else 1))
    out, pos = [], 0
    for s, e, cls in hits:
        if s < pos:
            continue
        out.append(E(text[pos:s]))
        out.append(f'<mark class="{cls}">{E(text[s:e])}</mark>')
        pos = e
    out.append(E(text[pos:]))
    return "".join(out)


def _hours(h: float | None) -> str:
    if h is None:
        return "—"
    return f"{h:g} h" if h < 48 else f"{h / 24:g} days"


def _num(n: int | None) -> str:
    return f"{n:,}" if isinstance(n, (int, float)) else "—"


# ---------------------------------------------------------------- decision computation


def compute_trace(cid: str, language: str, condition: str, structured: list[str], immediate: bool,
                  asset_id: str | None, mapping_method: str, reliability: str, window: float | None) -> dict[str, Any]:
    complaints = load_complaints().set_index("id")
    text = complaints.loc[cid, "text_native" if language == "native" else "text_en"]
    ctx = build_asset_context(load_graph(_SIG), asset_id, load_ranking(_SIG), CFG, mapping_method)
    trace = run_firewall(cid, text, language, condition, CFG, structured_hazards=structured, immediate_danger=immediate,
                         asset_context=ctx, reliability_state=reliability, scenario_failure_window_hours=window)
    trace["original_text"] = text
    return trace


def resolve_reliability(choice: str, language: str, condition: str) -> str:
    if choice == "auto":
        return reliability_state_from_canary(canary(_SIG), language, condition, CFG)
    return choice


# ---------------------------------------------------------------- page 1: live intervention


CONTROL_KEYS = ("scenario", "complaint", "language", "condition", "asset", "reliability", "structured", "immediate", "use_window", "window")


def _apply_scenario(scen: pd.Series, asset_ids: set[str]) -> None:
    has_window = not pd.isna(scen.scenario_failure_window_hours)
    st.session_state.update({
        "complaint": scen.complaint_id,
        "language": scen.language,
        "condition": scen.condition,
        "asset": scen.asset_id if scen.asset_id in asset_ids else "(no asset context)",
        "reliability": "auto",
        "structured": [h for h in str(scen.structured_hazard).split(";") if h],
        "immediate": bool(scen.structured_immediate_danger),
        "use_window": bool(has_window),
        "window": float(scen.scenario_failure_window_hours) if has_window else float(CFG["d2"]["time_to_failure_hours"]),
    })


def page_live() -> None:
    complaints = load_complaints()
    scenarios = load_scenarios().set_index("scenario_id")
    nodes = load_nodes()
    G = load_graph(_SIG)
    d2 = CFG["d2"]
    asset_ids = set(nodes[nodes.type == "substation"].id)
    scen_ids = list(scenarios.index)
    canonical = FW.get("canonical_scenario_id", scen_ids[0])

    st.markdown(
        '<div class="sc-eyebrow">Manipal Hackathon · Cascading Failure · SDG 11 · Bengaluru</div>'
        '<div class="sc-title">SILENT CASCADE <span>DECISION FIREWALL</span></div>'
        '<p class="sc-q">The AI proposes a route. The Firewall asks: <b>if this decision is wrong, how dangerous is the consequence?</b></p>',
        unsafe_allow_html=True,
    )

    # ---- seed every control before anything reads it (widgets render lower down the page) ----
    if "scenario" not in st.session_state:
        st.session_state["scenario"] = canonical
        _apply_scenario(scenarios.loc[canonical], asset_ids)
        st.session_state["_applied_scenario"] = canonical

    # ---- guided demo: three clicks tell the whole story, no narrator needed ----
    g1, g2, g3, g4 = st.columns([1, 1, 1, 1.5])
    if g1.button("① The dangerous miss", width="stretch", type="primary", key="g_miss"):
        st.session_state["scenario"] = canonical
        _apply_scenario(scenarios.loc[canonical], asset_ids)
        st.session_state["_applied_scenario"] = canonical
        st.session_state.update(ack=False, ack_min=0)
    if g2.button("② A routine complaint", width="stretch", key="g_routine"):
        routine = "SC-05" if "SC-05" in scenarios.index else scen_ids[-1]
        st.session_state["scenario"] = routine
        _apply_scenario(scenarios.loc[routine], asset_ids)
        st.session_state["_applied_scenario"] = routine
        st.session_state.update(ack=False, ack_min=0)
    if g3.button("③ Nobody accepts it", width="stretch", key="g_wait"):
        st.session_state["ack"] = False
        st.session_state["ack_min"] = FW["action_policy"]["red_reescalation_target_minutes"]
    g4.markdown('<p class="sc-cap" style="margin-top:6px">Click ① ② ③ in order. Every panel below updates.</p>', unsafe_allow_html=True)

    # ---- a scenario change resets its dependent controls ----
    scen_choice = st.session_state["scenario"]
    if st.session_state.get("_applied_scenario") != scen_choice:
        st.session_state["_applied_scenario"] = scen_choice
        if scen_choice != "custom":
            _apply_scenario(scenarios.loc[scen_choice], asset_ids)
    scen = scenarios.loc[scen_choice] if scen_choice != "custom" else None

    # ---- compute from session state (controls are rendered after the verdict) ----
    cid = st.session_state["complaint"]
    lang = st.session_state["language"]
    cond = st.session_state["condition"]
    asset_sel = st.session_state["asset"]
    rel_choice = st.session_state["reliability"]
    struct = list(st.session_state["structured"])
    immediate = bool(st.session_state["immediate"])
    window = float(st.session_state["window"]) if st.session_state["use_window"] else None
    asset_id = None if asset_sel == "(no asset context)" else asset_sel
    mapping = scen.asset_mapping_method if (scen is not None and asset_id == scen.asset_id) else ("scenario_selected" if asset_id else "none")

    rel = resolve_reliability(rel_choice, lang, cond)
    trace = compute_trace(cid, lang, cond, struct, immediate, asset_id, mapping, rel, window)
    decision, plan, clf, scan, ctx = trace["decision"], trace["action_plan"], trace["classifier"], trace["safety_scan"], trace["asset_context"]
    level = decision["risk_level"]
    text = trace["original_text"]
    row = complaints.set_index("id").loc[cid]

    # counterfactual: what the same complaint would get with a healthy AI quality check
    ghost_level = None
    if rel != "normal":
        alt = compute_trace(cid, lang, cond, struct, immediate, asset_id, mapping, "normal", window)
        if alt["decision"]["risk_level"] != level:
            ghost_level = alt["decision"]["risk_level"]

    # ---- delta banner: teaches causality in one line whenever the verdict moves ----
    if st.session_state.get("_prev_level") and st.session_state["_prev_level"] != level:
        new_codes = [c for c in decision["reason_codes"] if c not in st.session_state.get("_prev_codes", [])]
        why = f" · new reason: {SHORT_REASON.get(new_codes[0], new_codes[0])}" if new_codes else ""
        st.markdown(f'<div class="sc-delta">CHANGED · {LEVEL_WORD[st.session_state["_prev_level"]]} → {LEVEL_WORD[level]}{E(why)}</div>', unsafe_allow_html=True)
    st.session_state["_prev_level"], st.session_state["_prev_codes"] = level, list(decision["reason_codes"])

    # ---- 1. the pipeline ribbon: the architecture, readable in one glance ----
    chips_by_stage: dict[int, list[str]] = {}
    for code in decision["reason_codes"]:
        chips_by_stage.setdefault(REASON_STAGE.get(code, 5), []).append(code)

    def chips(stage: int) -> str:
        return '<div class="c">' + "".join(
            f'<span class="sc-chip {CHIP_CLS[level]}" title="{E(c)}">{E(SHORT_REASON.get(c, c.lower().replace("_", " ")))}</span>'
            for c in chips_by_stage.get(stage, [])) + "</div>"

    haz_terms = [m["term"] for m in scan["matched_terms"] if m["source"] == "original_text"]
    haz_names = [h.replace("_", " ") for h in scan["hazards"]]
    haz_summary = ", ".join(haz_names[:2]) + (f" +{len(haz_names) - 2} more" if len(haz_names) > 2 else "")
    n_struct = len([m for m in scan["matched_terms"] if m["source"] == "structured_intake"])
    tiles = [
        ("Complaint", "Kannada" if lang == "native" else "English",
         f'{len(text)} chars · intake flags: {n_struct or "none"}', "red" if immediate else ""),
        ("AI prediction", clf["predicted_dept"] or "none — unparseable",
         f'margin {clf["margin"]} · saw {"all " + str(len(text)) if clf["input_complete"] else str(len(clf["seen_text"])) + " of " + str(len(text))} chars',
         "amber" if (not clf["predicted_dept"] or not clf["input_complete"] or clf["margin"] < FW["uncertainty"]["low_margin_threshold"]) else ""),
        ("Independent scan", f'{len(scan["direct_hazards"])} direct hazard' + ("s" if len(scan["direct_hazards"]) != 1 else "") if scan["direct_hazards"] else "no hazard found",
         haz_summary or f"scanned all {len(text)} chars", "red" if scan["direct_hazard"] else "green"),
        ("Asset consequence", (ctx["criticality_tier"].replace("_", " ") if ctx["context_available"] else "unknown"),
         (f'rank {ctx["criticality_rank"]}/{ctx["n_ranked_assets"]} · {_num(ctx["simulated_people_exposed"])} exposed' if ctx["context_available"] else "no asset mapped"),
         "red" if ctx.get("criticality_tier") == "very_high" else ("amber" if ctx.get("criticality_tier") in ("high", "unknown") else "")),
        ("AI quality check", rel,
         (f"if healthy → {LEVEL_WORD[ghost_level]}" if ghost_level else ("automatic routing permitted" if rel == "normal" else "automatic routing restricted")),
         "amber" if rel != "normal" else "green"),
        ("Firewall decision", LEVEL_WORD[level],
         {"red": "dispatch now · review in parallel", "yellow": "person checks before routing", "green": "routed automatically"}[level], level),
    ]
    st.markdown(
        '<div class="sc-ribbon">' + "".join(
            f'<div class="sc-rt {cls}{" last" if i == len(tiles) - 1 else ""}"><div class="n">{i + 1}</div><div class="s">{E(name)}</div>'
            f'<div class="v">{E(str(value))}</div><div class="g">{E(str(ghost))}</div>{chips(i)}</div>'
            for i, (name, value, ghost, cls) in enumerate(tiles)
        ) + "</div>",
        unsafe_allow_html=True,
    )

    # ---- 2. the verdict ----
    if level == "red":
        head, sub = "RED — IMMEDIATE EMERGENCY DISPATCH", (
            f'AI route <b>{"overridden" if decision["ai_route_overridden"] else "confirmed and escalated"}</b> → '
            f'<b>{E(decision["final_department"])}</b>. Work order created now. Human review runs <b>in parallel</b>.')
    elif level == "yellow":
        head, sub = "YELLOW — HUMAN VERIFICATION BEFORE ROUTING", (
            f'AI suggestion <b>{E(decision["recommended_department"] or "none")}</b> is advice only. Not routed until a person checks it.')
    else:
        head, sub = "GREEN — AUTOMATIC ROUTING ALLOWED", (
            f'Routed to <b>{E(decision["final_department"])}</b> automatically. No person needed.')
    st.markdown(f'<div class="sc-risk {level}"><div class="lvl">{head}</div><div class="sub">{sub}</div>'
                f'<div class="why">{E(decision["reason_text"][0])}</div></div>', unsafe_allow_html=True)
    with st.expander(f"All {len(decision['reason_codes'])} reasons in plain language"):
        for code, txt in zip(decision["reason_codes"], decision["reason_text"]):
            st.markdown(f'<div style="padding:5px 0;border-top:1px solid #262b33"><span class="sc-chip {CHIP_CLS[level]}">{E(code)}</span> {E(txt)}</div>', unsafe_allow_html=True)

    # ---- 3. AI-only vs Firewall, always on screen ----
    ai_hours, fw_hours = trace["ai_only"]["response_hours"], trace["response_hours"]
    ai_fails = fw_fails = None
    summ = None
    if ctx["context_available"] and window is not None:
        ai_fails, fw_fails = ai_hours >= window, fw_hours >= window
        summ = summarize_final(run_cascade(ctx["asset_id"], _SIG))

    def outcome_line(fails: bool | None) -> str:
        if fails is None:
            return '<div class="sc-k">Physical outcome</div><div class="sc-v">not evaluated — needs a mapped asset and a failure window</div>'
        if fails:
            return (f'<div class="sc-k">Physical outcome (simulated)</div><div class="sc-v bad">equipment fails → cascade</div>'
                    f'<div class="sc-big" style="color:#d93025">{summ["people_affected"]:,}</div>'
                    f'<div class="sc-k">simulated service population exposed · {summ["substations_failed"]} substations · '
                    f'{summ["hospitals_on_backup"]} hospitals on generator · {summ["pumps_without_water"]} wards without water</div>')
        return ('<div class="sc-k">Physical outcome (simulated)</div><div class="sc-v ok">repair lands before the assumed failure window</div>'
                '<div class="sc-big" style="color:#34a853">0</div><div class="sc-k">no cascade under the stated scenario assumption</div>')

    fw_action = {"red": f'emergency dispatch → {decision["final_department"]}', "yellow": "human verification, then routing",
                 "green": f'automatic → {decision["final_department"]}'}[level]
    st.markdown(
        '<div class="sc-split">'
        f'<div class="sc-panel bad"><div class="hdr">AI ONLY · TODAY</div>'
        f'<div class="sc-k">Route</div><div class="sc-v">{E(trace["ai_only"]["department"])}{" · " + E(trace["ai_only"]["department_note"]) if trace["ai_only"]["department_note"] else ""}</div>'
        f'<div class="sc-k">Response</div><div class="sc-v bad">{_hours(ai_hours)}</div>{outcome_line(ai_fails)}</div>'
        f'<div class="sc-panel {"ok" if level != "green" else ""}"><div class="hdr">WITH DECISION FIREWALL</div>'
        f'<div class="sc-k">Route</div><div class="sc-v">{E(fw_action)}</div>'
        f'<div class="sc-k">Response</div><div class="sc-v ok">{_hours(fw_hours)}</div>{outcome_line(fw_fails)}</div>'
        "</div>",
        unsafe_allow_html=True,
    )

    # ---- 4. work order + acknowledgement ----
    sig = json.dumps([cid, lang, cond, struct, immediate, asset_id, rel, window, level], default=str)
    if st.session_state.get("ack_sig") != sig:
        st.session_state["ack_sig"], st.session_state["ack"], st.session_state["ack_min"] = sig, False, 0
    # the card is rendered into a slot reserved ABOVE the buttons, so a click updates the status
    # in the same rerun instead of one interaction late
    wo_slot = st.container()
    if plan["requires_acknowledgement"]:
        b1, b2, b3, _ = st.columns([1, 1.2, 0.7, 2.1])
        if b1.button("✔ Crew accepts", width="stretch", key="btn_ack"):
            st.session_state["ack"] = True
        if b2.button("⏱ Nobody accepts", width="stretch", key="btn_wait"):
            st.session_state["ack_min"] += FW["action_policy"]["red_reescalation_target_minutes"] if level == "red" else FW["action_policy"]["yellow_review_target_hours"] * 60
        if b3.button("↺", width="stretch", key="btn_reset"):
            st.session_state["ack"], st.session_state["ack_min"] = False, 0
    state = advance_acknowledgement(plan, st.session_state.get("ack", False), st.session_state.get("ack_min", 0), FW)
    status_cls = {"acknowledged": "ok", "not_required": "", "reescalated": "bad"}.get(state["acknowledgement_state"], "unp")
    wo_slot.markdown(
        '<div class="sc-card" style="margin-top:14px"><div class="sc-wo">'
        f'<div><div class="sc-k">Work order</div><div class="sc-v">{E(plan["work_order_type"])}</div></div>'
        f'<div><div class="sc-k">Assigned to</div><div class="sc-v">{E(plan["assigned_department"])}</div></div>'
        f'<div><div class="sc-k">Priority</div><div class="sc-v">{E(plan["priority"])}</div></div>'
        f'<div><div class="sc-k">Human review</div><div class="sc-v">{"in parallel" if plan["human_review_parallel"] else ("before routing" if level == "yellow" else "not required")}</div></div>'
        f'<div><div class="sc-k">Status · T+{state["minutes_elapsed"]:g} min</div><div class="sc-v {status_cls}">{E(state["status"]).replace("_", " ")}</div></div>'
        f'<div><div class="sc-k">If nobody accepts</div><div class="sc-v">{E(plan["next_action_if_unacknowledged"])}</div></div>'
        "</div></div>",
        unsafe_allow_html=True,
    )

    # ---- 5. controls: every feature visible, nothing hidden behind an expander ----
    with st.container(border=True):
        st.markdown('<div class="sc-eyebrow">Change any input · the decision above recomputes</div>', unsafe_allow_html=True)
        c1, c2, c3, c4 = st.columns([1.15, 1.35, 1, 1])
        c1.selectbox("Scenario", scen_ids + ["custom"], key="scenario",
                     format_func=lambda s: f"{s} · {scenarios.loc[s, 'complaint_id']}" if s != "custom" else "custom", help="Rehearsed complaint-to-asset mappings from data/scenarios.csv (synthetic).")
        c2.selectbox("Complaint", list(complaints.id), key="complaint",
                     format_func=lambda i: f"{i} · {complaints.set_index('id').loc[i, 'text_en'][:42]}…")
        c3.radio("Submitted in", ["native", "en"], horizontal=True, key="language",
                 format_func=lambda v: "ಕನ್ನಡ" if v == "native" else "English")
        c4.radio("AI input", CONDITIONS, horizontal=True, key="condition", format_func=COND_LABEL.get,
                 help="How the classifier sees the complaint. The safety scan always reads the complete original.")
        c5, c6, c7 = st.columns([1.5, 1, 1.3])
        c5.selectbox("Affected asset", ["(no asset context)"] + sorted(asset_ids), key="asset",
                     format_func=lambda a: a if a.startswith("(") else f"{a} · {nodes.set_index('id').loc[a, 'name'] if isinstance(nodes.set_index('id').loc[a, 'name'], str) else 'unnamed'}",
                     help="Scenario-selected mapping. Not evidence that the complaint occurred at this asset.")
        c6.selectbox("AI quality check", ["auto", "normal", "degraded", "unavailable"], key="reliability", format_func=REL_LABEL.get,
                     help="Degraded or missing quality signal switches safe mode on and restricts automatic routing.")
        c7.multiselect("Hazard boxes ticked at intake", ["sparking", "fire", "live_wire", "shock", "burst_pipe", "flooding"], key="structured",
                       help="The structured path: works even when free-text classification fails.")
        c8, c9, c10 = st.columns([1.2, 1.1, 1.2])
        c8.checkbox("Caller says immediate danger", key="immediate")
        c9.checkbox("Assume a failure window", key="use_window")
        if st.session_state["use_window"]:
            c10.number_input("Failure window (hours, assumed)", min_value=1.0, step=24.0, key="window")

    # ---- 6. safe mode, stated as behaviour ----
    if rel != "normal":
        st.markdown(f'<div class="sc-safe on" style="margin-top:14px"><b>SAFE MODE ACTIVE</b> · {"Kannada" if lang == "native" else "English"} automatic routing restricted · '
                    f'uncertain complaints become Yellow, direct-danger complaints become Red <span>· quality check: {E(rel)}</span></div>', unsafe_allow_html=True)
    else:
        st.markdown('<div class="sc-safe off" style="margin-top:14px"><b>SAFE MODE OFF</b> · quality check healthy · automatic routing permitted for eligible low-risk complaints</div>', unsafe_allow_html=True)

    # ---- 7. the evidence behind the verdict, two rows ----
    seen, kws = condition_input(text, cond, d2["truncate_chars"])
    a, b = st.columns(2)
    with a:
        st.markdown(f'<div class="sc-card"><div class="sc-k">1 · Complaint as submitted · red marks = hazards the scan found</div>'
                    f'<p class="sc-text">{_highlight(text, None, haz_terms, "")}</p>'
                    f'<div class="sc-k">Translation</div><p class="sc-text" style="color:#9aa0a6;font-size:13.5px">{E(row["text_en"] if lang == "native" else row["text_native"])}</p></div>',
                    unsafe_allow_html=True)
    with b:
        body = _highlight(seen, kws, [], clf["predicted_dept"])
        if not clf["input_complete"]:
            body += f"<s>{E(text[len(seen):])}</s>"
        # translation of what the AI saw, split to mirror the cut so a non-Kannada reader sees
        # the classifier only got a fragment. Split point is proportional and snapped to a word.
        other = row["text_en"] if lang == "native" else row["text_native"]
        if clf["input_complete"] or not text:
            tr_html, tr_label = E(other), "Translation"
        else:
            cut = int(round(len(seen) / len(text) * len(other)))
            snap = other.rfind(" ", 0, cut + 1)
            cut = snap if snap > 0 else cut
            tr_html = f"{E(other[:cut])}<s>{E(other[cut:])}</s>"
            tr_label = "Translation · AI saw only the un-struck part (approx. split)"
        st.markdown(f'<div class="sc-card"><div class="sc-k">2 · What the AI saw · struck-through text was cut off</div><p class="sc-text">{body}</p>'
                    f'<div class="sc-k">{tr_label}</div><p class="sc-text" style="color:#9aa0a6;font-size:13.5px">{tr_html}</p>'
                    f'<div class="sc-k">Verdict</div><div class="sc-v {"unp" if not clf["predicted_dept"] else ""}">{E(clf["predicted_dept"]) or "unparseable — no department"} · margin {clf["margin"]}</div></div>',
                    unsafe_allow_html=True)
    a, b = st.columns(2)
    with a:
        hits = "".join(f'<div class="sc-v">{_pill(m["source"].replace("_", " "), "meas" if m["source"] == "original_text" else "syn")} <b>{E(str(m["term"]))}</b> → {E(m["hazard"])}</div>'
                       for m in scan["matched_terms"]) or '<div class="sc-v ok">no hazard terms in this complaint</div>'
        st.markdown(f'<div class="sc-card"><div class="sc-k">3 · Independent scan · reads all {len(text)} chars, never the AI prediction</div>{hits}</div>', unsafe_allow_html=True)
    with b:
        if ctx["context_available"]:
            st.markdown(f'<div class="sc-card"><div class="sc-k">4 · Affected asset · {E(ctx["mapping_method"].replace("_", " "))}</div>'
                        f'<div class="sc-v">{E(ctx["asset_name"])} · rank {ctx["criticality_rank"]} of {ctx["n_ranked_assets"]} · {E(ctx["criticality_tier"].replace("_", " "))}</div>'
                        f'<div class="sc-k">If it fails (simulated, {CFG["d1"]["max_steps"] * CFG["assumptions"]["hours_per_step"]:g} h horizon)</div>'
                        f'<div class="sc-v">{_num(ctx["simulated_people_exposed"])} exposed · {ctx["simulated_substations_failed"]} substations · '
                        f'{ctx["dependent_hospitals"]} hospitals lose feeder · {ctx["wards_without_water"]} wards without water</div>'
                        f'<div class="sc-k">Labels</div><div>{_pill("location observed", "real")}{_pill("topology inferred", "inf")}{_pill("loads assumed", "syn")}{_pill("outcome simulated", "")}</div></div>',
                        unsafe_allow_html=True)
        else:
            st.markdown(f'<div class="sc-card"><div class="sc-k">4 · Affected asset</div><div class="sc-v unp">none mapped — {E(str(ctx["reason"]))}</div>'
                        '<div class="sc-k">Policy</div><div class="sc-v">unknown consequence is never treated as low consequence, and no asset is picked on the complaint\'s behalf</div></div>',
                        unsafe_allow_html=True)

    # ---- 8. the map, only when a failure actually occurs ----
    if ai_fails:
        st.markdown('<div class="sc-k" style="margin-top:14px">5 · AI-only branch · corrected cascade from the mapped asset</div>', unsafe_allow_html=True)
        components.html(cascade_component(nodes, G, run_cascade(ctx["asset_id"], _SIG), CFG["assumptions"]["hours_per_step"], height=480), height=500)
        st.markdown('<span class="sc-pill">● healthy</span><span class="sc-pill inf">● overloaded / on backup</span><span class="sc-pill red">● tripped / no service</span>'
                    '<span class="sc-pill">● substation · hospital ■ pump · hover for state</span>', unsafe_allow_html=True)

    with st.expander("Why the operations dashboard never noticed (the problem, not the solution)"):
        st.markdown('<div class="sc-mon"><div><span>intake-api</span><em>operational · 200 OK</em></div><div><span>classifier</span><em>operational · p50 187 ms</em></div>'
                    '<div><span>router</span><em>operational · error rate 0.01%</em></div></div>', unsafe_allow_html=True)
        _cap("Health dashboards measure whether the AI answered, not whether the answer was safe to act on. Every request above returned 200 OK.")
    with st.expander("Provenance and caveats for this page"):
        _cap("Complaints and asset mappings are <b>synthetic</b>. Classifier and Firewall results are <b>measured</b> on this prototype. "
             "Cascade outcomes are <b>simulated</b> on assumed loads and inferred topology, and exposure is service population, not unique people. "
             f"Acknowledgement ({FW['action_policy']['red_acknowledgement_target_minutes']} min) and re-escalation "
             f"({FW['action_policy']['red_reescalation_target_minutes']} min) targets are assumed prototype policy, unconfirmed by the team. "
             "Nothing here dispatches a real crew. Full detail: LIMITATIONS.md.")
        if scen is not None:
            _cap(f"<b>Scenario {E(str(scen.name))}</b> · {E(str(scen.notes))}")


# ---------------------------------------------------------------- page 2: evidence


def page_evidence() -> None:
    ev = load_csv("firewall_evaluation.csv")
    by_cond = load_csv("firewall_evaluation_by_condition.csv")
    if ev is None:
        st.error("Missing `outputs/firewall_evaluation.csv`. Generate it with:\n\n```bash\npython src/evaluate_firewall.py\n```")
        st.stop()
    e = ev.set_index("configuration")
    fw, gd = e.loc["decision_firewall"], e.loc["existing_guard"]

    st.markdown('<div class="sc-eyebrow">Evidence</div>'
                '<div class="sc-title" style="font-size:clamp(22px,2.6vw,30px)">Does it catch danger <span>without escalating everything?</span></div>'
                '<p class="sc-q">20 synthetic complaints × 2 languages × 3 AI conditions = 120 decisions. Ground truth is used to score, never to decide.</p>',
                unsafe_allow_html=True)

    rows = [
        ("Dangerous AI routes intercepted", "dangerous_misroutes_intercepted", "n_dangerous_ai_routes", "benefit", True),
        ("Dangerous AI routes allowed through", "dangerous_misroutes_allowed", "n_dangerous_ai_routes", "benefit", False),
        ("Critical cases answered at emergency speed", "critical_emergency_response", "n_critical_cases", "benefit", True),
        ("Correct low-risk routes kept automatic", "safe_automation_count", "n_noncritical_ai_correct", "benefit", True),
        ("Decisions needing a human", "human_review_count", "n_cases", "cost", False),
        ("Unnecessary escalations", "unnecessary_escalations", "n_noncritical_ai_correct", "cost", False),
    ]
    body = ""
    for label, num_col, den_col, kind, higher_better in rows:
        vals = {c: int(e.loc[c, num_col]) for c in PRIMARY_CONFIGURATIONS}
        best = max(vals.values()) if higher_better else min(vals.values())
        worst = min(vals.values()) if higher_better else max(vals.values())
        cells = ""
        for c in PRIMARY_CONFIGURATIONS:
            cls = "best" if vals[c] == best and best != worst else ("worst" if vals[c] == worst and best != worst else "")
            cells += f'<td class="{cls}">{vals[c]} / {int(e.loc[c, den_col])}</td>'
        body += f'<tr class="{kind}"><td>{E(label)}</td>{cells}</tr>'
    head = "".join(f'<th class="{"win" if c == "decision_firewall" else ""}">{E(LABELS[c])}</th>' for c in PRIMARY_CONFIGURATIONS)
    st.markdown(f'<table class="sc-tbl"><thead><tr><th>Every number is count / denominator</th>{head}</tr></thead><tbody>{body}</tbody></table>', unsafe_allow_html=True)

    st.markdown(
        f'<p class="sc-q" style="margin-top:16px">The guard blocks the same {int(gd.dangerous_misroutes_intercepted)} dangerous routes, but leaves '
        f'<b>{int(gd.n_critical_cases - gd.critical_emergency_response)} critical cases sitting in a queue</b>. The Firewall acts on all '
        f'{int(fw.n_critical_cases)}. It costs {int(fw.human_review_count)} of {int(fw.n_cases)} decisions going to a human.</p>',
        unsafe_allow_html=True)

    p = REPO_ROOT / "outputs" / "firewall_comparison.png"
    if p.exists():
        st.image(str(p), width="stretch")

    if by_cond is not None:
        show = by_cond[by_cond.configuration.isin(PRIMARY_CONFIGURATIONS)].copy()
        show["condition"] = show.condition.map(lambda c: COND_LABEL.get(c, c))
        for new, num, den in [("dangerous routes caught", "dangerous_misroutes_intercepted", "n_dangerous_ai_routes"),
                              ("human review", "human_review_count", "n_cases"),
                              ("kept automatic", "safe_automation_count", "n_noncritical_ai_correct")]:
            show[new] = show[num].astype(int).astype(str) + " / " + show[den].astype(int).astype(str)
        st.markdown("##### Where the review workload comes from")
        st.dataframe(show[["label", "condition", "dangerous routes caught", "human review", "kept automatic"]], width="stretch", hide_index=True)
        _cap("With full text the Firewall keeps most correct low-risk routes automatic. When the AI input is cut off or the quality check is degraded, "
             "the policy deliberately withdraws AI autonomy. That is the cost, reported rather than hidden.")

    with st.expander("Mapped scenarios · simulated physical outcome"):
        cols = {"label": "configuration", "simulated_incidents_prevented": "incidents prevented", "n_mapped_critical_scenarios": "mapped scenarios",
                "simulated_exposure_incurred": "simulated exposure incurred", "simulated_exposure_avoided_vs_ai_only": "exposure avoided vs AI-only"}
        st.dataframe(ev[list(cols)].rename(columns=cols), width="stretch", hide_index=True)
        _cap("Under the assumed 336 h failure window the guard's 48 h queue also beats the window, so the Firewall's edge here is the emergency-speed "
             "response for people next to the hazard, not the 14-day window. Exposure is simulated service population, not unique people.")
    with st.expander("How each configuration works, and how response time is modelled"):
        _cap("<b>AI only</b>: the classifier's route is accepted automatically; unparseable goes to the maintenance queue. "
             "<b>Existing guard</b>: the earlier uncertainty and safety-keyword check, which sees the same degraded input the classifier saw. "
             "<b>Decision Firewall</b>: independent scan of the original complaint, asset consequence, fail-safe policy and quality-check state. "
             "Response times are assumed: emergency 4 h; human verification is the review target plus the correct department's SLA. "
             "The Firewall is scored on free text only, so structured intake answers never inflate the result. "
             "n = 20 complaints per cell, so treat every rate as directional.")
    with st.expander("Appendix · all five configurations, including an escalate-everything reference"):
        st.dataframe(ev, width="stretch", hide_index=True)
        _cap(f"Escalate everything scores {int(e.loc['escalate_everything', 'safe_automation_count'])} / "
             f"{int(e.loc['escalate_everything', 'n_noncritical_ai_correct'])} on safe automation. It is what the Firewall must not become.")
    with st.expander("Appendix · classifier accuracy by language and condition (legacy D2 experiment)"):
        acc, dd = load_csv("d2_accuracy.csv"), load_csv("d2_dangerous_downgrade.csv")
        if acc is not None:
            a, b = st.columns([1.3, 1])
            with a:
                st.pyplot(plot_accuracy(acc, None), width="stretch")
            with b:
                st.dataframe(acc, width="stretch", hide_index=True)
                if dd is not None:
                    st.dataframe(dd, width="stretch", hide_index=True)
            _cap("Truncation shows a real language gap; the smaller-model condition did not. Both are reported. The dangerous-downgrade rate reaches "
                 "100% for critical Kannada complaints under truncation, which is the case the Firewall exists for.")
        else:
            st.info("Run `python src/d2_language.py` to produce outputs/d2_accuracy.csv.")
    with st.expander("Appendix · cascade robustness, and the legacy D4 comparison"):
        rob, d4 = load_csv("d1_robustness.csv"), load_csv("d4_summary.csv")
        if rob is not None:
            st.dataframe(rob, width="stretch", hide_index=True)
            _cap("With one-time load shedding the large cascade appears only under the default headroom assumption; under 6 of 9 combinations the worst "
                 "failure stays near 3% of nodes. Consequence is highly sensitive to assumed headroom, and nothing collapses the whole network.")
        if d4 is not None:
            st.dataframe(d4, width="stretch", hide_index=True)
            _cap("Legacy hardening-vs-checkpoint table, kept for provenance. It depends on an assumed 40% prevention rate and is not Firewall evidence.")


# ---------------------------------------------------------------- page 3: scenario explorer


def page_explorer() -> None:
    nodes = load_nodes()
    G = load_graph(_SIG)
    rank = load_ranking(_SIG)
    scenarios = load_scenarios().set_index("scenario_id")
    st.markdown('<div class="sc-eyebrow">Scenario explorer</div>'
                '<div class="sc-title" style="font-size:clamp(22px,2.6vw,30px)">Consequence depends on <span>which asset is hit</span></div>'
                '<p class="sc-q">Pick a substation to fail. This is the consequence model the Firewall reads when it scores an asset.</p>',
                unsafe_allow_html=True)
    subs = nodes[nodes.type == "substation"]
    labels = {r.id: f"{r.id} · {r.name if isinstance(r.name, str) and r.name else '(unnamed)'}" for r in subs.itertuples()}
    opts = list(subs.id)
    canonical = scenarios.loc[FW.get("canonical_scenario_id", scenarios.index[0]), "asset_id"]
    node = st.selectbox("Substation that fails", opts, index=opts.index(canonical) if canonical in opts else 0, key="explorer_asset", format_func=labels.get)
    ctx = build_asset_context(G, node, rank, CFG, "explorer_selected")
    tl = run_cascade(node, _SIG)
    s = summarize_final(tl)
    st.markdown(f'<div class="sc-card"><div class="sc-k">{E(labels[node])}</div>'
                f'<div class="sc-v">rank {ctx["criticality_rank"]} of {ctx["n_ranked_assets"]} · percentile {ctx["criticality_percentile"]:g} · '
                f'{E(ctx["criticality_tier"].replace("_", " "))} tier</div>'
                f'<div class="sc-k">Simulated outcome within {tl[-1]["hours"]:g} h</div>'
                f'<div class="sc-v">{s["people_affected"]:,} exposed · {s["substations_failed"]} substations tripped · {s["hospitals_on_backup"]} hospitals on generator · '
                f'{s["hospitals_without_power"]} without power · {s["pumps_without_water"]} wards without water · {s["unserved_load_mw"]:,} MW unserved</div></div>',
                unsafe_allow_html=True)
    components.html(cascade_component(nodes, G, tl, CFG["assumptions"]["hours_per_step"], height=560), height=580)
    st.markdown('<span class="sc-pill">● healthy</span><span class="sc-pill inf">● overloaded / on backup</span><span class="sc-pill red">● tripped / no service</span>'
                '<span class="sc-pill">● substation · hospital ■ pump · hover for state</span>', unsafe_allow_html=True)
    with st.expander("Criticality ranking · top 10 of 190"):
        top = rank.head(10).copy()
        top["tier"] = top.criticality_percentile.apply(lambda p: "very high" if p >= FW["criticality_percentiles"]["very_high"] else ("high" if p >= FW["criticality_percentiles"]["high"] else "normal"))
        st.dataframe(top[["rank", "node_id", "name", "tier", "people_affected", "substations_failed", "hospitals_feeder_lost", "hospitals_without_power", "pumps_without_water"]],
                     width="stretch", hide_index=True)
        _cap("Ranked by simulated service population of tripped substations. Very high = top 10%, high = next 15%, both assumed policy boundaries in config.yaml. "
             "Population values are independent per-substation draws, not unique people.")


# ---------------------------------------------------------------- page 4: methodology & limitations


def page_method() -> None:
    st.markdown('<div class="sc-eyebrow">Methodology &amp; limitations</div>'
                '<div class="sc-title" style="font-size:clamp(22px,2.6vw,30px)">What is real, <span>what is assumed</span></div>'
                '<p class="sc-q">Every quantity in this prototype carries one of these labels.</p>', unsafe_allow_html=True)
    rows = [
        ("Substation, hospital and pump locations (190 / 1,060 / 157)", "OpenStreetMap, cached in data/raw/", "Observed", "real"),
        ("Grid topology (which substation feeds what)", "3 nearest neighbours by distance", "Inferred", "inf"),
        ("Capacity, load, population served, buffers, SLAs, failure window", "config.yaml · seeded draws and declared values", "Assumed", ""),
        ("Firewall thresholds, tiers, review and acknowledgement targets", "config.yaml · firewall (confirmed_by_team=false)", "Assumed", ""),
        ("Complaints (20 × 2 languages) and complaint-to-asset mappings", "hand-written · data/scenarios.csv", "Synthetic", ""),
        ("Classifier predictions, hazard hits, Firewall decisions, evaluation counts", "src/d2_language.py, decision_firewall.py, evaluate_firewall.py", "Measured", "meas"),
        ("Cascade outcomes, criticality ranking, exposure avoided", "src/cascade.py · deterministic, seed 42", "Simulated", ""),
        ("AI grievance routing is deployed in Indian cities; low-resource-language gap", "references in LIMITATIONS.md", "Cited", "real"),
    ]
    st.markdown('<div class="sc-prov">' + "".join(f'<div><span>{E(k)}</span><span class="src">{E(src)}</span>{_pill(status, cls)}</div>' for k, src, status, cls in rows) + "</div>",
                unsafe_allow_html=True)

    with st.expander("What the evidence does and does not support"):
        _cap("<b>Supported:</b> in this controlled bilingual set and simulated scenario, a deterministic consequence-aware Firewall intercepts the dangerous "
             "routes an AI-only workflow allows, answers every critical case at emergency speed, and keeps automatic routing for most correct low-risk cases "
             "under clean input.<br><br><b>Not supported:</b> any estimate of real Bengaluru routing accuracy, real feeder connectivity, real repair times, or "
             "real people protected.")
    with st.expander("What changed in the physical model"):
        _cap("The earlier engine re-shed every failed substation's full load on every timestep and ignored the configured buffers, which amplified cascades "
             "artificially. The corrected engine sheds each failed substation's load once, records it as unserved when no live neighbour remains, conserves "
             "load at every snapshot, and moves hospitals and pumps through healthy → on backup → service outage. Every D1, robustness and D4 output was "
             "regenerated; no earlier headline figure is reused.")
    with st.expander("Known limitations of this prototype"):
        _cap("• The quality check uses the <b>same 20 complaints</b> as the evaluation, which is circular; a real deployment needs a separate golden set.<br>"
             "• The hazard vocabulary is small and keyword-based. Kannada active flooding is reachable only through the structured intake path, and Kannada "
             "ಒಡೆದ (broken/burst) also matches a broken footpath, producing one Yellow conflict flag that is left visible rather than tuned away.<br>"
             "• The classifier is a deterministic keyword proxy, not a production model. Its score margin is an uncertainty signal, not calibrated confidence.<br>"
             "• Response, review and acknowledgement timings are assumed prototype policy.<br>"
             "• Nothing dispatches, messages or changes any real municipal system.")
    with st.expander("Reproduce every number"):
        st.code("python src/build_graph.py\npython src/d1_cascade.py\npython src/d1_robustness.py\npython src/d2_language.py\n"
                "python src/evaluate_firewall.py\npython -m pytest tests/ -q\nstreamlit run app.py", language="bash")
        _cap("Full detail: LIMITATIONS.md, README.md and docs/STREAMLIT_APP.md.")


# ---------------------------------------------------------------- router

PAGES = {
    "Live intervention": page_live,
    "Evidence": page_evidence,
    "Scenario explorer": page_explorer,
    "Methodology & limitations": page_method,
}
PAGE_HINT = {
    "Live intervention": "Watch one complaint become an action",
    "Evidence": "Catches danger without escalating everything?",
    "Scenario explorer": "Why the asset matters",
    "Methodology & limitations": "What is real, what is assumed",
}

with st.sidebar:
    st.markdown('<div class="sc-eyebrow">Silent Cascade · Decision Firewall</div>', unsafe_allow_html=True)
    choice = st.radio("Section", list(PAGES), label_visibility="collapsed", key="page",
                      format_func=lambda p: p, captions=[PAGE_HINT[p] for p in PAGES])
    st.markdown("---")
    st.markdown('<p class="sc-cap">AI handles routine cases. When danger, uncertainty, missing data or infrastructure consequence is high, the Firewall '
                'restricts AI authority, overrides the route, starts the emergency action and requires acknowledgement.<br><br>'
                'Scenario-based prototype. Nothing here dispatches a real crew.</p>', unsafe_allow_html=True)

PAGES[choice]()
