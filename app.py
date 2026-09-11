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
import streamlit.components.v1 as components
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

def page_overview() -> None:
    st.markdown('<div class="sc-eyebrow">Manipal Hackathon · Cascading Failure · SDG 11</div>', unsafe_allow_html=True)
    st.markdown('<div class="sc-title">SILENT <span>CASCADE</span></div>', unsafe_allow_html=True)
    st.markdown(
        '<p class="sc-lede">Cities monitor every physical asset. Nothing monitors the AI that decides which asset '
        'gets fixed first — and it degrades silently, worst on the citizens least able to escalate.</p>',
        unsafe_allow_html=True,
    )
    st.write("")
    st.markdown("#### The chain we model")
    st.markdown(
        "citizen complaint (regional language) → **AI classification & routing** → dispatch queue → repair delay → "
        "equipment fails → **cascade through power and water** → households without water, hospital on generator"
    )
    st.caption("We model *delay*, not automated dispatch — the only link the published evidence supports.")

    st.write("")
    c1, c2 = st.columns([1.2, 1])
    with c1:
        st.markdown("#### Every dashboard says everything is fine")
        mock = REPO_ROOT / "outputs" / "d3_dashboard.html"
        if mock.exists():
            components.html(mock.read_text(encoding="utf-8"), height=520, scrolling=True)
        else:
            st.info("outputs/d3_dashboard.html not found — run `python src/d3_dashboard.py`.")
    with c2:
        st.markdown("#### What the classifier actually did")
        st.markdown(
            '<div class="sc-card sc-bad">'
            '<div class="sc-k">Ticket c01 · HTTP 200</div>'
            '<p class="sc-text">ನಮ್ಮ ಬೀದಿಯಲ್ಲಿರುವ ಟ್ರಾನ್ಸ್‌ಫಾರ್ಮರ್ ಬಾಕ್ಸ್‌ನಿಂದ ಕಿಡಿಗಳು ಹಾರುತ್ತಿವೆ…</p>'
            '<div class="sc-k">True dept</div><div class="sc-v ok">electrical_emergency</div><br>'
            '<div class="sc-k">Routed to (truncated input)</div><div class="sc-v unp">(unparseable) → general queue</div><br>'
            '<div class="sc-k">Outcome</div><div class="sc-v bad">14-day window → equipment failure → cascade</div>'
            "</div>",
            unsafe_allow_html=True,
        )
        st.markdown('<p class="sc-cap" style="margin-top:14px">The thing that failed was a decision, not a server. '
                    "Monitoring watches whether the AI answered — not whether it was right.</p>", unsafe_allow_html=True)

    st.write("")
    st.markdown("#### What's real, what's simulated")
    st.table(pd.DataFrame(
        [
            ("Substation locations (27)", "OpenStreetMap · power=substation", "Observed"),
            ("Hospital & pump locations (398)", "OpenStreetMap · amenity / man_made", "Observed"),
            ("Feeder topology (grid edges)", "3-nearest-neighbour by haversine", "Inferred"),
            ("Capacity, load, population served", "config.yaml · seeded uniform draws", "Assumed"),
            ("Generator / reservoir buffer hours", "8 h · 6 h typical engineering values", "Assumed"),
            ("Complaint text (20 × 2 languages)", "hand-written, Kannada script", "Synthetic"),
            ("Routing accuracy by language", "120 classifications, keyword baseline", "Measured"),
            ("Cascade outcomes, criticality ranking", "cascade.py · deterministic, seed 42", "Simulated"),
            ("Intervention costs (₹)", "order-of-magnitude placeholders", "Assumed"),
        ],
        columns=["Component", "Source", "Status"],
    ))


def page_cascade() -> None:
    cfg = load_config()
    G = load_graph()
    nodes = load_nodes()
    rank = ranking()

    st.markdown("### Cascade simulator")
    st.caption("Real Bhopal substations, hospitals and pumps at real coordinates. Load-redistribution cascade, "
               f"{cfg['assumptions']['hours_per_step']:g} h per step. Grid edges are inferred (3 nearest neighbours) — no feeder topology is published.")

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

    st.markdown("### Language routing — the AI injection, traced end to end")
    st.caption("This runs the exact `classify_one()` from src/d2_language.py that produced outputs/d2_results.csv — a "
               "deterministic keyword-baseline classifier, not a production LLM. Same code, same numbers.")

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
    st.markdown("### Intervention comparison — the smallest intervention")
    st.caption("Same cascade engine, N random initiating failures shared across all three conditions (paired). "
               "Costs are order-of-magnitude assumptions from config.yaml, not quotes.")
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
