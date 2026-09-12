"""D1 robustness sweep — is the criticality ranking (a small number of substations dominate
cascade impact, which D4's "harden the top-ranked node" and the pitch's "a classification node
outranks every substation" both depend on) a structural property of this network, or an
artifact of one chosen KNN k / one chosen load-headroom range?

NOTE: on this network (190 Bengaluru substations), no single substation's failure collapses the
*entire* network the way an earlier Bhopal-seed run showed — the worst single substation affects
at most ~65% of nodes, not 100%. So the metric worth stress-testing isn't "does everyone collapse"
(false on its face) but "is impact genuinely concentrated in a few substations, or is it roughly
uniform across all of them" — the latter would undermine the whole idea of a criticality ranking.

Rebuilds the graph under a 3x3 grid of alternate topology (KNN k) and capacity-headroom
assumptions, reruns criticality_ranking() under each, and reports the concentration of impact
(top vs. median substation) plus the top-substation's raw people-affected. Uses the SAME cached
raw OSM layers and the SAME seed — only the two swept assumptions change. Does not touch
data/processed/graph.gpickle (the headline D1 outputs are untouched); writes
outputs/d1_robustness.csv only.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path
from typing import Any

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

from build_graph import _knn_substation_edges, _nearest_substation_edges, build_nodes, to_networkx  # noqa: E402
from cascade import criticality_ranking  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent
OUTPUTS_DIR = REPO_ROOT / "outputs"

K_VALUES = [2, 3, 4]
HEADROOM_RANGES = [(0.55, 0.75), (0.45, 0.65), (0.35, 0.55)]  # current default is the first


def load_config() -> dict[str, Any]:
    import yaml

    with open(REPO_ROOT / "config.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)


def build_with_params(city: str, cfg: dict[str, Any], k: int, headroom: tuple[float, float]):
    """Like build_graph.build(), but with an overridden KNN k and load-headroom range.
    Does not write to data/processed/ — this is a what-if graph, not the headline one."""
    cfg = {**cfg, "assumptions": {**cfg["assumptions"], "load_fraction_of_capacity_range": list(headroom)}}
    nodes = build_nodes(city, cfg)
    edges_rows = []
    for src, tgt in _knn_substation_edges(nodes, k=k):
        edges_rows.append({"source": src, "target": tgt, "type": "grid", "provenance": "inferred"})
    for src, tgt in _nearest_substation_edges(nodes, "hospital"):
        edges_rows.append({"source": src, "target": tgt, "type": "supply", "provenance": "inferred"})
    for src, tgt in _nearest_substation_edges(nodes, "pump"):
        edges_rows.append({"source": src, "target": tgt, "type": "supply", "provenance": "inferred"})
    edges = pd.DataFrame(edges_rows)
    G = to_networkx(nodes, edges)
    return G


def accepted_city(cfg: dict[str, Any]) -> str:
    import json

    raw_dir = REPO_ROOT / "data" / "raw"
    for city in cfg["cities"]["order"]:
        if city not in cfg["cities"]:
            continue
        path = raw_dir / f"substation_{city}.json"
        if path.exists():
            with open(path, encoding="utf-8") as f:
                n = len(json.load(f)["elements"])
            if n >= cfg["overpass"]["min_nodes_to_accept_city"]:
                return city
    raise RuntimeError("No cached city found — run build_graph.py first.")


def main() -> None:
    cfg = load_config()
    city = accepted_city(cfg)
    n_total = None
    rows = []
    print(f"[d1_robustness] city={city}, sweeping k={K_VALUES} x headroom={HEADROOM_RANGES}")

    for k in K_VALUES:
        for headroom in HEADROOM_RANGES:
            t0 = time.time()
            G = build_with_params(city, cfg, k, headroom)
            n_total = G.number_of_nodes()
            ranking = criticality_ranking(
                G, max_steps=cfg["d1"]["max_steps"], hours_per_step=cfg["assumptions"]["hours_per_step"], top_n=None
            )
            pct = ranking["cascade_size"] / n_total * 100
            top_pct, median_pct = pct.max(), pct.median()
            concentration = top_pct / median_pct if median_pct > 0 else float("inf")
            top_people = int(ranking.iloc[0]["people_affected"])
            elapsed = time.time() - t0
            print(
                f"[d1_robustness] k={k} headroom={headroom}: top substation affects {top_pct:.0f}% "
                f"of nodes ({top_people:,} people) vs. {median_pct:.0f}% for the median substation "
                f"({concentration:.1f}x concentration) ({elapsed:.1f}s)"
            )
            rows.append(
                {
                    "knn_k": k,
                    "headroom_low": headroom[0],
                    "headroom_high": headroom[1],
                    "n_substations": len(ranking),
                    "top_pct_nodes_affected": round(top_pct, 1),
                    "median_pct_nodes_affected": round(median_pct, 1),
                    "concentration_ratio": round(concentration, 1),
                    "top_people_affected": top_people,
                }
            )

    df = pd.DataFrame(rows)
    out_path = OUTPUTS_DIR / "d1_robustness.csv"
    df.to_csv(out_path, index=False)
    print(f"\n[d1_robustness] wrote {out_path}")
    print(df.to_string(index=False))

    min_c, max_c = df.concentration_ratio.min(), df.concentration_ratio.max()
    if min_c >= 2:
        print(
            f"\n[d1_robustness] FINDING HOLDS: across all {len(rows)} parameter combinations, "
            f"the top-ranked substation affects {min_c:.1f}x-{max_c:.1f}x as many nodes as the "
            "median substation. Impact is genuinely concentrated in a small set of substations "
            "regardless of the exact topology/headroom assumption — the premise the criticality "
            "ranking (and D4's 'harden the top-ranked node') depends on is not an artifact of one "
            "chosen parameter set. It is NOT the case that any substation collapses the whole "
            "network — the worst single substation affects at most "
            f"{df.top_pct_nodes_affected.max():.0f}% of nodes, not 100%; report it that way."
        )
    else:
        print(
            "\n[d1_robustness] FINDING DOES NOT HOLD: at least one parameter combination shows "
            "impact nearly uniform across substations (concentration ratio near 1) — report this "
            "honestly, it would undermine the criticality-ranking argument. See LIMITATIONS.md."
        )


if __name__ == "__main__":
    main()
