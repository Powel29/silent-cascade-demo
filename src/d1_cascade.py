"""D1 step 4 — orchestrator: run both cascade scenarios, render frames, stitch GIFs.

Run order: fetch_data.py -> build_graph.py -> this script.
Produces:
  outputs/d1_frames/{scenario}_frame_{step:02d}.png
  outputs/d1_cascade_scenario_a.gif
  outputs/d1_cascade_scenario_b.gif
  outputs/d1_criticality.csv   (FULL ranking of every substation, with rank + percentile)

Uses the corrected cascade engine (one-time load shedding, hospital/water buffer states) —
see src/cascade.py. Amber markers are substations >90% load OR dependent assets on backup;
red markers are tripped substations OR dependent assets whose buffer has expired.
"""

from __future__ import annotations

import pickle
from pathlib import Path
from typing import Any

import imageio.v2 as imageio
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import networkx as nx
import yaml

from cascade import cascade, criticality_ranking

REPO_ROOT = Path(__file__).resolve().parent.parent
PROCESSED_DIR = REPO_ROOT / "data" / "processed"
OUTPUTS_DIR = REPO_ROOT / "outputs"
FRAMES_DIR = OUTPUTS_DIR / "d1_frames"

COLORS = {"healthy": "#9aa0a6", "overloaded": "#f5a623", "failed": "#d93025", "on_backup": "#f5a623"}
MARKERS = {"substation": "o", "hospital": "+", "pump": "s"}


def load_config() -> dict[str, Any]:
    with open(REPO_ROOT / "config.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_graph() -> nx.DiGraph:
    with open(PROCESSED_DIR / "graph.gpickle", "rb") as f:
        return pickle.load(f)


def largest_substation_by_population(G: nx.DiGraph) -> str:
    subs = [(n, d["population_served"]) for n, d in G.nodes(data=True) if d["type"] == "substation"]
    return max(subs, key=lambda x: x[1])[0]


def render_frame(G: nx.DiGraph, snapshot: dict[str, Any], out_path: Path, cfg: dict[str, Any]) -> None:
    """One timestep frame: real lat/lon scatter + grid edges + status colouring."""
    width_px = cfg["d1"]["frame_width_px"]
    height_px = cfg["d1"]["frame_height_px"]
    dpi = cfg["d1"]["frame_dpi"]
    fig, ax = plt.subplots(figsize=(width_px / dpi, height_px / dpi), dpi=dpi)

    # grid edges (sub<->sub) as thin grey lines
    for u, v, d in G.edges(data=True):
        if d["type"] != "grid":
            continue
        x = [G.nodes[u]["lon"], G.nodes[v]["lon"]]
        y = [G.nodes[u]["lat"], G.nodes[v]["lat"]]
        ax.plot(x, y, color="#cccccc", linewidth=0.6, zorder=1)

    failed = snapshot["failed"]  # tripped substations + dependent assets whose buffer expired
    overloaded = snapshot["overloaded"] | snapshot["on_backup"]  # amber: overloaded or on backup

    for node_type, marker in MARKERS.items():
        xs, ys, colors = [], [], []
        for n, d in G.nodes(data=True):
            if d["type"] != node_type:
                continue
            if n in failed:
                c = COLORS["failed"]
            elif n in overloaded:
                c = COLORS["overloaded"]
            else:
                c = COLORS["healthy"]
            xs.append(d["lon"])
            ys.append(d["lat"])
            colors.append(c)
        size = 90 if node_type == "substation" else 70
        edge_kwargs = {} if marker == "+" else {"edgecolors": "black", "linewidths": 0.4}
        ax.scatter(xs, ys, c=colors, marker=marker, s=size, zorder=2, **edge_kwargs)

    ax.set_title(f"T+{snapshot['hours']:.1f}h", fontsize=18)
    ax.set_xlabel("Longitude")
    ax.set_ylabel("Latitude")

    textstr = (
        f"Simulated service population exposed: {snapshot['people_affected']:,}\n"
        f"Substations tripped: {len(snapshot['failed_substations'])}\n"
        f"Hospitals on generator: {len(snapshot['hospitals_on_generator'])}\n"
        f"Hospitals without power: {len(snapshot['hospitals_without_power'])}\n"
        f"Wards without water: {len(snapshot['wards_without_water'])}"
    )
    ax.text(
        0.02, 0.02, textstr, transform=ax.transAxes, fontsize=13, va="bottom", ha="left",
        bbox=dict(boxstyle="round", facecolor="white", alpha=0.85),
    )

    fig.tight_layout()
    fig.savefig(out_path, dpi=dpi)
    plt.close(fig)


def render_scenario(
    G: nx.DiGraph,
    timeline: list[dict[str, Any]],
    scenario_name: str,
    cfg: dict[str, Any],
) -> list[Path]:
    FRAMES_DIR.mkdir(parents=True, exist_ok=True)
    frame_paths = []
    for snapshot in timeline:
        out_path = FRAMES_DIR / f"{scenario_name}_frame_{snapshot['step']:02d}.png"
        render_frame(G, snapshot, out_path, cfg)
        frame_paths.append(out_path)
        print(
            f"[d1_cascade] {scenario_name} step={snapshot['step']:02d} "
            f"T+{snapshot['hours']:.1f}h substations_failed={len(snapshot['failed_substations'])} "
            f"on_backup={len(snapshot['on_backup'])} outage={len(snapshot['service_outage'])} "
            f"people_affected={snapshot['people_affected']} unserved_mw={snapshot['unserved_load']:.1f}"
        )
    return frame_paths


def stitch_gif(frame_paths: list[Path], out_path: Path, cfg: dict[str, Any]) -> None:
    fps = cfg["d1"]["gif_fps"]
    hold = cfg["d1"]["final_frame_hold_count"]
    images = [imageio.imread(p) for p in frame_paths]
    images = images + [images[-1]] * hold
    duration = 1.0 / fps
    imageio.mimsave(out_path, images, duration=duration)
    print(f"[d1_cascade] wrote {out_path} ({len(images)} frames incl. hold, {fps} fps)")


def run_scenario_a(G: nx.DiGraph, target: str, cfg: dict[str, Any]) -> list[dict[str, Any]]:
    """Scenario A — the highest-criticality substation fails (equipment failure).

    NOTE: CLAUDE.md's original spec picked "largest substation by population_served", but on
    this network's random seed that node is a peripheral, weakly-connected substation whose
    cascade stays contained to 3 nodes — it doesn't clear the deck's own "visible spread
    across >=4 frames" bar. By user decision, we instead use the #1 node from
    criticality_ranking() (highest total people_affected if it alone fails), captioned
    honestly as "the substation whose failure cascades most broadly" rather than by
    population served.
    """
    print(f"[d1_cascade] scenario_a initial failure: {target} (highest-criticality substation)")
    return cascade(G, [target], max_steps=cfg["d1"]["max_steps"], hours_per_step=cfg["assumptions"]["hours_per_step"])


def run_scenario_b(G: nx.DiGraph, target: str, cfg: dict[str, Any]) -> list[dict[str, Any]]:
    """Scenario B — same cascade, framed as a delayed-repair failure (narrative only).

    CLAUDE.md: "The delay itself is narrative, not simulated — just start the cascade and
    title it differently." We reuse the same initiating node and physics as scenario_a; only
    the frame titles / captioning in the deck should describe the 14-step repair delay.
    """
    print(f"[d1_cascade] scenario_b initial failure: {target} (delayed-repair framing, same physics)")
    return cascade(G, [target], max_steps=cfg["d1"]["max_steps"], hours_per_step=cfg["assumptions"]["hours_per_step"])


def main() -> None:
    cfg = load_config()
    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)

    print("[d1_cascade] loading graph...")
    G = load_graph()
    print(f"[d1_cascade] graph: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges")

    print("\n[d1_cascade] === criticality ranking ===")
    # FULL ranking (all substations) so the Decision Firewall can look up any asset's rank and
    # percentile; the top-10 view is what the deck shows.
    ranking = criticality_ranking(
        G, max_steps=cfg["d1"]["max_steps"], hours_per_step=cfg["assumptions"]["hours_per_step"], top_n=None
    )
    ranking_path = OUTPUTS_DIR / "d1_criticality.csv"
    ranking.to_csv(ranking_path, index=False)
    print(f"[d1_cascade] wrote {ranking_path} ({len(ranking)} substations, full ranking)")
    print(ranking.head(10).to_string(index=False))

    top_node = ranking.iloc[0]["node_id"]
    pop_node = largest_substation_by_population(G)
    if pop_node != top_node:
        print(
            f"[d1_cascade] NOTE: largest-population substation is {pop_node}, but its cascade "
            f"stays small; using highest-criticality node {top_node} for scenario_a/b instead "
            f"(see code comment in run_scenario_a)."
        )

    print("\n[d1_cascade] === scenario_a: equipment failure ===")
    timeline_a = run_scenario_a(G, top_node, cfg)
    frames_a = render_scenario(G, timeline_a, "scenario_a", cfg)
    stitch_gif(frames_a, OUTPUTS_DIR / "d1_cascade_scenario_a.gif", cfg)

    print("\n[d1_cascade] === scenario_b: delayed-repair framing ===")
    timeline_b = run_scenario_b(G, top_node, cfg)
    frames_b = render_scenario(G, timeline_b, "scenario_b", cfg)
    stitch_gif(frames_b, OUTPUTS_DIR / "d1_cascade_scenario_b.gif", cfg)


if __name__ == "__main__":
    main()
