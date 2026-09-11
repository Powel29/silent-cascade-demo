"""Silent Cascade — interactive prototype (Streamlit).

A thin UI over the repo's existing pure functions. Every number shown here comes from the
same code that produced outputs/*.csv: cascade.cascade(), d2_language.classify_one(),
d4_intervention.run_condition(). Nothing is reimplemented in the app layer.

Run locally:  pip install -r requirements.txt && streamlit run app.py
"""

from __future__ import annotations

import html
import pickle
import sys
from pathlib import Path
from typing import Any

import folium
import pandas as pd
import streamlit as st
import yaml
from streamlit_autorefresh import st_autorefresh
from streamlit_folium import st_folium

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
    classify_one,
    misroute_examples,
    plot_accuracy,
)
from d4_intervention import draw_random_failures, hardened_graph, plot_comparison, run_condition  # noqa: E402

COLORS = {"healthy": "#9aa0a6", "overloaded": "#f5a623", "failed": "#d93025", "blue": "#4285f4", "green": "#34a853"}
BHOPAL_CENTER = (23.25, 77.42)

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

@st.cache_data
def load_config() -> dict[str, Any]:
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


# ---------------------------------------------------------------- map

def cascade_map(nodes: pd.DataFrame, G, snapshot: dict[str, Any], center: tuple[float, float], zoom: int) -> folium.Map:
    m = folium.Map(location=center, zoom_start=zoom, tiles="OpenStreetMap", control_scale=True)
    failed, over = snapshot["failed"], snapshot["overloaded"]
    state = lambda n: "failed" if n in failed else "overloaded" if n in over else "healthy"

    edges = folium.FeatureGroup(name="grid")
    for u, v, d in G.edges(data=True):
        if d["type"] != "grid" or u > v:
            continue
        su, sv = state(u), state(v)
        col = COLORS["failed"] if su == sv == "failed" else COLORS["overloaded"] if "failed" in (su, sv) else "#6b7280"
        folium.PolyLine([(G.nodes[u]["lat"], G.nodes[u]["lon"]), (G.nodes[v]["lat"], G.nodes[v]["lon"])], color=col, weight=1.4, opacity=0.8).add_to(edges)

    pts = folium.FeatureGroup(name="assets")
    for r in nodes.itertuples():
        s = state(r.id)
        col = COLORS[s]
        label = r.name if isinstance(r.name, str) and r.name else r.id
        tip = f"<b>{html.escape(label)}</b><br>{r.type} · {s.upper()}"
        if r.type == "substation":
            tip += f"<br>serves {int(r.population_served):,}"
            folium.CircleMarker((r.lat, r.lon), radius=7, color="#000", weight=1, fill=True, fill_color=col, fill_opacity=0.95, tooltip=tip).add_to(pts)
        elif r.type == "hospital":
            folium.CircleMarker((r.lat, r.lon), radius=3, color=col, weight=2, fill=True, fill_color=col, fill_opacity=0.9, tooltip=tip).add_to(pts)
        else:
            folium.RegularPolygonMarker((r.lat, r.lon), number_of_sides=4, radius=5, rotation=45, color="#000", weight=1, fill_color=col, fill_opacity=0.95, tooltip=tip).add_to(pts)
    edges.add_to(m)
    pts.add_to(m)
    return m


# ---------------------------------------------------------------- pages

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
    monitor = (
        '<div class="sc-panel sc-ok">'
        '<div class="hdr"><b>CivicOps Monitor</b><span>grievance pipeline · all systems · just now</span></div>'
        '<div class="sc-mgrid">'
        f'<div class="m"><div class="l">Uptime</div><div class="v">99.98% <i class="gdot"></i></div>{_spark("0,14 12,13 24,15 36,13 48,14 60,12 72,14 84,13 96,15 108,13 120,14 132,12 144,13 160,14")}</div>'
        f'<div class="m"><div class="l">p50 Latency</div><div class="v">187ms <i class="gdot"></i></div>{_spark("0,15 12,14 24,16 36,15 48,13 60,15 72,16 84,14 96,13 108,15 120,16 132,14 144,15 160,13")}</div>'
        f'<div class="m"><div class="l">Error rate</div><div class="v">0.01% <i class="gdot"></i></div>{_spark("0,16 12,16 24,15 36,16 48,17 60,16 72,15 84,16 96,16 108,17 120,16 132,15 144,16 160,16")}</div>'
        f'<div class="m"><div class="l">Requests / min</div><div class="v">1,240 <i class="gdot"></i></div>{_spark("0,13 12,15 24,12 36,14 48,16 60,13 72,12 84,15 96,14 108,12 120,15 132,13 144,14 160,12")}</div>'
        "</div>"
        '<div class="sc-svc">' + "".join(
            f'<div><i class="gdot"></i><span>{s}</span><em>operational</em></div>'
            for s in ["intake-api", "language-normaliser", "classifier", "urgency-scorer", "router", "queue-worker"]
        ) + "</div></div>"
    )
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
    st.markdown(f'<div class="sc-split">{monitor}{classifier}</div>', unsafe_allow_html=True)
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

    _section("Cascade simulator", "Real Bhopal substations, hospitals and pumps at real coordinates. Load-redistribution cascade, "
             f"{cfg['assumptions']['hours_per_step']:g} h per step. Grid edges are <em>inferred</em> (3 nearest neighbours) — no feeder topology is published.")

    subs = nodes[nodes.type == "substation"].copy()
    subs["label"] = subs.apply(lambda r: f"{r.id} · {r['name'] if isinstance(r['name'], str) and r['name'] else '(unnamed)'} · serves {int(r.population_served):,}", axis=1)
    default = rank.iloc[0]["node_id"]
    options = list(subs.id)
    top = st.columns([2, 1, 1])
    with top[0]:
        node = st.selectbox("Initiating failure", options, index=options.index(default), format_func=lambda i: subs.set_index("id").loc[i, "label"])
    timeline = run_cascade(node)
    last = len(timeline) - 1

    if "step" not in st.session_state or st.session_state.step > last:
        st.session_state.step = 0
    if st.session_state.pop("restart", False):
        st.session_state.step = 0
        st.session_state.autoplay = True
    elif st.session_state.get("autoplay"):
        if st.session_state.step >= last:
            st.session_state.autoplay = False
        else:
            st.session_state.step += 1
    with top[1]:
        st.write("")
        autoplay = st.checkbox("Autoplay (slow)", key="autoplay")
    with top[2]:
        st.write("")
        if st.button("↺ Restart"):
            st.session_state.restart = True
            st.rerun()
    if autoplay:
        st_autorefresh(interval=1500, key="tick")

    step = st.slider("Timestep", 0, last, key="step", format="step %d")
    snap = timeline[step]
    subs_tripped = sum(1 for n in snap["failed"] if G.nodes[n]["type"] == "substation")

    stats = [
        ("Elapsed", f"T+{snap['hours']:.1f}h", "#d93025"),
        ("People affected", f"{snap['people_affected']:,}", "#d93025"),
        ("Hospitals on generator", str(len(snap["hospitals_on_generator"])), "#e8eaed"),
        ("Wards without water", str(len(snap["wards_without_water"])), "#e8eaed"),
        ("Substations tripped", f"{subs_tripped} / {len(subs)}", "#e8eaed"),
    ]
    st.markdown(
        '<div class="sc-hud">' + "".join(
            f'<div><div class="sc-k">{k}</div><div class="sc-big" style="color:{c}">{v}</div></div>' for k, v, c in stats
        ) + "</div>",
        unsafe_allow_html=True,
    )

    view = st.session_state.get("map_view", {"center": BHOPAL_CENTER, "zoom": 12})
    out = st_folium(
        cascade_map(nodes, G, snap, view["center"], view["zoom"]),
        key="cascade_map", returned_objects=["center", "zoom"], height=560, use_container_width=True,
    )
    if out and out.get("center") and out.get("zoom"):
        st.session_state.map_view = {"center": (out["center"]["lat"], out["center"]["lng"]), "zoom": out["zoom"]}
    st.markdown(
        '<span class="sc-pill" style="color:#9aa0a6">● healthy</span> &nbsp;'
        '<span class="sc-pill" style="color:#f5a623">● overloaded &gt;90%</span> &nbsp;'
        '<span class="sc-pill" style="color:#d93025">● failed</span> &nbsp;'
        '<span class="sc-pill">● substation &nbsp; • hospital &nbsp; ◆ pump</span>',
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


def page_language() -> None:
    cfg = load_config()
    complaints = load_complaints()
    truncate = cfg["d2"]["truncate_chars"]

    _section("Language routing — the AI injection, traced end to end",
             "This runs the exact <code>classify_one()</code> from src/d2_language.py that produced outputs/d2_results.csv — a "
             "deterministic keyword-baseline classifier, <em>not a production LLM</em>. Same code, same numbers.")

    c = st.columns([2, 1, 1])
    with c[0]:
        cid = st.selectbox("Complaint", list(complaints.id), format_func=lambda i: f"{i} · {complaints.set_index('id').loc[i, 'text_en'][:60]}…")
    with c[1]:
        lang = st.radio("Language", ["English", "ಕನ್ನಡ (native)"], horizontal=True)
    with c[2]:
        cond = st.radio("Condition", CONDITIONS, horizontal=True)

    row = complaints.set_index("id").loc[cid]
    full = row["text_en"] if lang == "English" else row["text_native"]
    text = full[:truncate] if cond == "truncated" else full
    is_en = _looks_english(full)
    kws = (SMALL_KEYWORDS_EN if is_en else SMALL_KEYWORDS_KN) if cond == "small_model" else (FULL_KEYWORDS_EN if is_en else FULL_KEYWORDS_KN)
    pred = classify_one(full, cond, truncate)
    wrong = pred != row["true_dept"]

    st.session_state.reqn = st.session_state.get("reqn", 4127) + 1
    ms = 150 + (st.session_state.reqn * 37) % 90

    left, right = st.columns([1.3, 1])
    with left:
        body = _highlight(text, kws, row["true_dept"])
        if cond == "truncated":
            body += f"<s>{html.escape(full[truncate:])}</s>"
        st.markdown(f'<div class="sc-card"><div class="sc-k">Input · {cond}</div><p class="sc-text">{body}</p></div>', unsafe_allow_html=True)
        st.markdown(f'<p class="sc-log" style="margin-top:8px">POST /classify {cid} {"en" if is_en else "kn"} {cond} <b>200 OK</b> {ms} ms</p>', unsafe_allow_html=True)
    with right:
        verdict = "correct · right queue" if not wrong else ("MISROUTED · wrong queue, wrong SLA" if pred else "DROPPED · unparseable, counted as incorrect")
        vcls = "ok" if not wrong else ("bad" if pred else "unp")
        st.markdown(
            f'<div class="sc-card {"sc-bad" if wrong else "sc-ok"}">'
            f'<div class="sc-k">True dept</div><div class="sc-v ok">{row["true_dept"]}</div><br>'
            f'<div class="sc-k">Routed to</div><div class="sc-v {vcls}">{pred or "(unparseable)"}</div><br>'
            f'<div class="sc-k">Verdict</div><div class="sc-v {vcls}">{verdict}</div>'
            "</div>",
            unsafe_allow_html=True,
        )
        st.markdown('<p class="sc-cap" style="margin-top:12px">Every request returns 200. The monitor never notices.</p>', unsafe_allow_html=True)

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
