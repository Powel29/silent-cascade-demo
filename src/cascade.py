"""D1 step 3 — cascade simulation core. Pure functions only: no plotting, no file I/O.

`cascade()` never mutates the caller's graph — it deep-copies at entry.
"""

from __future__ import annotations

import copy
from typing import Any

import networkx as nx
import pandas as pd


def build_snapshot(
    G: nx.DiGraph,
    failed: set[str],
    newly_failed: set[str],
    step: int,
    hours_per_step: float,
) -> dict[str, Any]:
    """Assemble one timeline entry from current graph + failure state."""
    overloaded = {
        n
        for n, d in G.nodes(data=True)
        if n not in failed
        and d["type"] == "substation"
        and d["load"] > 0.9 * d["capacity"]
    }

    people_affected = sum(
        int(G.nodes[n]["population_served"])
        for n in failed
        if G.nodes[n]["type"] == "substation" and G.nodes[n]["population_served"] != ""
    )

    hospitals_on_generator = sorted(n for n in failed if G.nodes[n]["type"] == "hospital")
    wards_without_water = sorted(n for n in failed if G.nodes[n]["type"] == "pump")

    return {
        "step": step,
        "hours": round(step * hours_per_step, 2),
        "failed": set(failed),
        "newly_failed": set(newly_failed),
        "overloaded": overloaded,
        "people_affected": people_affected,
        "hospitals_on_generator": hospitals_on_generator,
        "wards_without_water": wards_without_water,
    }


def cascade(
    G: nx.DiGraph,
    initial_failures: list[str] | set[str],
    max_steps: int = 12,
    hours_per_step: float = 2.0,
) -> list[dict[str, Any]]:
    """Simulate load-redistribution cascade starting from `initial_failures`.

    Returns a list of per-timestep snapshot dicts (see build_snapshot). Deep-copies G so
    the caller's graph is never mutated.
    """
    G = copy.deepcopy(G)
    failed: set[str] = set(initial_failures)
    timeline: list[dict[str, Any]] = []

    # record step 0 as the initial failure state before any redistribution
    timeline.append(build_snapshot(G, failed, set(initial_failures), 0, hours_per_step))

    for step in range(1, max_steps + 1):
        newly_failed: set[str] = set()

        # 1. redistribute load from failed substations to living neighbouring substations
        for node in list(failed):
            if G.nodes[node]["type"] != "substation":
                continue
            live_neighbors = [
                n
                for n in G.neighbors(node)
                if n not in failed and G.nodes[n]["type"] == "substation"
            ]
            if not live_neighbors:
                continue
            shed = G.nodes[node]["load"] / len(live_neighbors)
            for n in live_neighbors:
                G.nodes[n]["load"] += shed

        # 2. trip anything over capacity
        for n in G.nodes:
            if n in failed or G.nodes[n]["type"] != "substation":
                continue
            if G.nodes[n]["load"] > G.nodes[n]["capacity"]:
                newly_failed.add(n)

        # 3. dependent assets fail once every feeding substation has failed
        for n in G.nodes:
            if n in failed or G.nodes[n]["type"] not in ("hospital", "pump"):
                continue
            feeders = list(G.predecessors(n))
            if feeders and all(f in failed or f in newly_failed for f in feeders):
                newly_failed.add(n)

        failed |= newly_failed
        timeline.append(build_snapshot(G, failed, newly_failed, step, hours_per_step))

        if not newly_failed:
            break

    return timeline


def criticality_ranking(G: nx.DiGraph, max_steps: int = 12, hours_per_step: float = 2.0, top_n: int = 10) -> pd.DataFrame:
    """Run cascade() with each substation as the sole initial failure; rank by impact.

    Ranked by total people_affected at the final timestep, NOT by degree or betweenness.
    """
    rows = []
    substations = [n for n, d in G.nodes(data=True) if d["type"] == "substation"]
    for node in substations:
        timeline = cascade(G, [node], max_steps=max_steps, hours_per_step=hours_per_step)
        final = timeline[-1]
        rows.append(
            {
                "node_id": node,
                "name": G.nodes[node].get("name", "") or node,
                "people_affected": final["people_affected"],
                "cascade_size": len(final["failed"]),
                "hospitals_hit": len(final["hospitals_on_generator"]),
            }
        )
    df = pd.DataFrame(rows).sort_values("people_affected", ascending=False).reset_index(drop=True)
    return df.head(top_n) if top_n else df
