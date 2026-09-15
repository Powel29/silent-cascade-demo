"""Cascade simulation core (corrected physical consequence model). Pure functions only:
no plotting, no file I/O.

Model rules (see CLAUDE.md §13):

* **One-time load shedding.** A substation's carried load is transferred at most once, in the
  propagation step *after* it fails. Newly failed nodes shed their *current* load (their own
  plus anything they received). If no live neighbouring substation exists, the load is
  recorded as ``unserved`` rather than duplicated or silently dropped.
* **Load conservation.** At every snapshot
  ``total_initial_load == live_load + unserved_load + pending_shed_load``.
* **Buffered dependent assets.** Hospitals and pumps do not fail the instant their feeder
  trips. They move ``healthy -> on_backup -> service_outage``; the outage happens only once
  the node's configured ``buffer_hours`` has elapsed.
* **Termination.** The cascade stops when a step produces no state change (no shed load, no
  new trips, no new backup transitions, no new outages) or when ``max_steps`` is reached.

``cascade()`` never mutates the caller's graph — it deep-copies at entry.
"""

from __future__ import annotations

import copy
from typing import Any

import networkx as nx
import pandas as pd

DEPENDENT_TYPES = ("hospital", "pump")


def _population(G: nx.DiGraph, n: str) -> int:
    v = G.nodes[n].get("population_served", "")
    return int(v) if v not in ("", None) else 0


def _buffer_hours(G: nx.DiGraph, n: str) -> float:
    v = G.nodes[n].get("buffer_hours", "")
    return float(v) if v not in ("", None) else 0.0


def build_snapshot(
    G: nx.DiGraph,
    step: int,
    hours_per_step: float,
    failed_substations: set[str],
    newly_failed: set[str],
    asset_state: dict[str, str],
    unserved_load: float,
    load_shed_this_step: float,
    pending_shed: set[str],
    total_initial_load: float,
) -> dict[str, Any]:
    """Assemble one timeline entry from the current graph + failure state."""
    overloaded = {
        n
        for n, d in G.nodes(data=True)
        if n not in failed_substations and d["type"] == "substation" and d["load"] > 0.9 * d["capacity"]
    }
    on_backup = {n for n, s in asset_state.items() if s == "on_backup"}
    service_outage = {n for n, s in asset_state.items() if s == "service_outage"}
    live_load = sum(d["load"] for n, d in G.nodes(data=True) if d["type"] == "substation" and n not in failed_substations)
    pending_shed_load = sum(G.nodes[n]["load"] for n in pending_shed)

    hosp = lambda s: sorted(n for n in s if G.nodes[n]["type"] == "hospital")  # noqa: E731
    pump = lambda s: sorted(n for n in s if G.nodes[n]["type"] == "pump")  # noqa: E731

    return {
        "step": step,
        "hours": round(step * hours_per_step, 2),
        # "failed" = out of service: tripped substations + dependent assets whose buffer expired
        "failed": set(failed_substations) | service_outage,
        "newly_failed": set(newly_failed),
        "failed_substations": set(failed_substations),
        "overloaded": overloaded,
        "on_backup": on_backup,
        "service_outage": service_outage,
        "affected": set(failed_substations) | on_backup | service_outage,
        # simulated service population of tripped substations (NOT unique real people)
        "people_affected": sum(_population(G, n) for n in failed_substations),
        "hospitals_on_generator": hosp(on_backup),
        "hospitals_without_power": hosp(service_outage),
        "pumps_on_buffer": pump(on_backup),
        "wards_without_water": pump(service_outage),
        "live_load": round(live_load, 6),
        "unserved_load": round(unserved_load, 6),
        "load_shed_this_step": round(load_shed_this_step, 6),
        "pending_shed_load": round(pending_shed_load, 6),
        "total_initial_load": round(total_initial_load, 6),
    }


def cascade(
    G: nx.DiGraph,
    initial_failures: list[str] | set[str],
    max_steps: int = 12,
    hours_per_step: float = 2.0,
) -> list[dict[str, Any]]:
    """Simulate a load-redistribution cascade starting from ``initial_failures``.

    Returns a list of per-timestep snapshot dicts (see ``build_snapshot``). Deep-copies ``G``
    so the caller's graph is never mutated.
    """
    G = copy.deepcopy(G)
    for n in initial_failures:
        if n not in G:
            raise KeyError(f"initial failure {n!r} is not a node of the graph")

    substations = [n for n, d in G.nodes(data=True) if d["type"] == "substation"]
    dependents = [n for n, d in G.nodes(data=True) if d["type"] in DEPENDENT_TYPES]
    total_initial_load = sum(float(G.nodes[n]["load"]) for n in substations)

    failed_substations: set[str] = {n for n in initial_failures if G.nodes[n]["type"] == "substation"}
    shed_done: set[str] = set()
    asset_state: dict[str, str] = {n: "healthy" for n in dependents}
    feeder_lost_step: dict[str, int] = {}
    # a dependent asset named directly as an initial failure is an immediate service outage
    for n in initial_failures:
        if G.nodes[n]["type"] in DEPENDENT_TYPES:
            asset_state[n] = "service_outage"
            feeder_lost_step[n] = 0
    unserved_load = 0.0
    timeline: list[dict[str, Any]] = []

    def update_dependents(step: int) -> tuple[set[str], set[str]]:
        """Move assets healthy->on_backup when every feeder is down; on_backup->outage when the
        buffer has elapsed. Returns (newly_on_backup, newly_outage)."""
        new_backup: set[str] = set()
        new_outage: set[str] = set()
        for n in dependents:
            if asset_state[n] == "healthy":
                feeders = list(G.predecessors(n))
                if feeders and all(f in failed_substations for f in feeders):
                    asset_state[n] = "on_backup"
                    feeder_lost_step[n] = step
                    new_backup.add(n)
            if asset_state[n] == "on_backup":
                elapsed = (step - feeder_lost_step[n]) * hours_per_step
                if elapsed >= _buffer_hours(G, n):
                    asset_state[n] = "service_outage"
                    new_outage.add(n)
        return new_backup, new_outage

    # step 0: the initiating failure(s); dependents lose their feeder immediately, nothing shed yet
    _, outage0 = update_dependents(0)
    timeline.append(
        build_snapshot(G, 0, hours_per_step, failed_substations, set(initial_failures) | outage0, asset_state,
                       unserved_load, 0.0, failed_substations - shed_done, total_initial_load)
    )

    for step in range(1, max_steps + 1):
        # 1. one-time shedding: every failed substation that has not yet transferred its load
        load_shed_this_step = 0.0
        for node in sorted(failed_substations - shed_done):
            load = float(G.nodes[node]["load"])
            live_neighbors = sorted(
                n for n in G.neighbors(node) if n not in failed_substations and G.nodes[n]["type"] == "substation"
            )
            if live_neighbors:
                share = load / len(live_neighbors)
                for n in live_neighbors:
                    G.nodes[n]["load"] = float(G.nodes[n]["load"]) + share
            else:
                unserved_load += load
            G.nodes[node]["load"] = 0.0
            shed_done.add(node)
            load_shed_this_step += load

        # 2. trip anything over capacity (these shed in the *next* step)
        newly_failed = {
            n for n in substations if n not in failed_substations and float(G.nodes[n]["load"]) > float(G.nodes[n]["capacity"])
        }
        failed_substations |= newly_failed

        # 3. dependent-asset state transitions
        new_backup, new_outage = update_dependents(step)

        timeline.append(
            build_snapshot(G, step, hours_per_step, failed_substations, newly_failed | new_outage, asset_state,
                           unserved_load, load_shed_this_step, failed_substations - shed_done, total_initial_load)
        )

        changed = bool(newly_failed or new_backup or new_outage or load_shed_this_step > 0)
        # a buffered asset still counting down, or a tripped node that has not shed yet, is a
        # pending state change: keep stepping until the horizon or until nothing is pending
        pending = bool(failed_substations - shed_done) or any(asset_state[n] == "on_backup" for n in dependents)
        if not changed and not pending:
            break

    return timeline


def summarize_final(timeline: list[dict[str, Any]]) -> dict[str, Any]:
    """Headline counts from the final snapshot, with explicit labels."""
    final = timeline[-1]
    hospitals_feeder_lost = len(final["hospitals_on_generator"]) + len(final["hospitals_without_power"])
    pumps_feeder_lost = len(final["pumps_on_buffer"]) + len(final["wards_without_water"])
    return {
        "steps": final["step"],
        "hours": final["hours"],
        "people_affected": final["people_affected"],
        "substations_failed": len(final["failed_substations"]),
        "cascade_size": len(final["affected"]),
        "hospitals_feeder_lost": hospitals_feeder_lost,
        "hospitals_on_backup": len(final["hospitals_on_generator"]),
        "hospitals_without_power": len(final["hospitals_without_power"]),
        "pumps_feeder_lost": pumps_feeder_lost,
        "pumps_without_water": len(final["wards_without_water"]),
        "unserved_load_mw": round(final["unserved_load"], 2),
    }


def criticality_ranking(
    G: nx.DiGraph, max_steps: int = 12, hours_per_step: float = 2.0, top_n: int | None = 10
) -> pd.DataFrame:
    """Run ``cascade()`` with each substation as the sole initial failure; rank by impact.

    Ranked by simulated service population exposed (``people_affected``) at the final
    timestep, then by substations failed, then by node id — deterministic for a fixed graph.
    ``criticality_percentile`` is 100 for the top-ranked substation and approaches 0 for the
    least critical (``100 * (1 - (rank - 1) / n)``). Pass ``top_n=None`` for the full ranking.
    """
    rows = []
    substations = sorted(n for n, d in G.nodes(data=True) if d["type"] == "substation")
    for node in substations:
        timeline = cascade(G, [node], max_steps=max_steps, hours_per_step=hours_per_step)
        summary = summarize_final(timeline)
        rows.append({"node_id": node, "name": G.nodes[node].get("name", "") or node, **summary})
    df = (
        pd.DataFrame(rows)
        .sort_values(["people_affected", "substations_failed", "node_id"], ascending=[False, False, True])
        .reset_index(drop=True)
    )
    n = len(df)
    df.insert(0, "rank", range(1, n + 1))
    df["criticality_percentile"] = (100 * (1 - (df["rank"] - 1) / n)).round(2)
    return df.head(top_n) if top_n else df
