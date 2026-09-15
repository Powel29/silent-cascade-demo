"""Shared fixtures: make src/ importable and provide a tiny deterministic graph."""

from __future__ import annotations

import sys
from pathlib import Path

import networkx as nx
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(REPO_ROOT))


def make_graph(
    subs: dict[str, tuple[float, float, int]],
    grid: list[tuple[str, str]],
    hospitals: dict[str, tuple[str, float]] | None = None,
    pumps: dict[str, tuple[str, float]] | None = None,
) -> nx.DiGraph:
    """subs: id -> (capacity, load, population); grid: undirected substation pairs;
    hospitals/pumps: id -> (feeder substation, buffer_hours)."""
    G = nx.DiGraph()
    for i, (nid, (cap, load, pop)) in enumerate(subs.items()):
        G.add_node(nid, type="substation", lat=12.9 + i * 0.01, lon=77.6 + i * 0.01, name=nid.upper(),
                   capacity=float(cap), load=float(load), population_served=pop, buffer_hours="", provenance="test")
    for a, b in grid:
        G.add_edge(a, b, type="grid", provenance="test")
        G.add_edge(b, a, type="grid", provenance="test")
    for nid, (feeder, buf) in (hospitals or {}).items():
        G.add_node(nid, type="hospital", lat=12.95, lon=77.65, name=nid, capacity="", load="", population_served="",
                   buffer_hours=buf, provenance="test")
        G.add_edge(feeder, nid, type="supply", provenance="test")
    for nid, (feeder, buf) in (pumps or {}).items():
        G.add_node(nid, type="pump", lat=12.96, lon=77.66, name=nid, capacity="", load="", population_served="",
                   buffer_hours=buf, provenance="test")
        G.add_edge(feeder, nid, type="supply", provenance="test")
    return G


@pytest.fixture
def chain_graph() -> nx.DiGraph:
    """A - B - C chain. A carries 100; B and C have little headroom, so A's failure trips B and
    B's (own + received) load then trips C. C has no live neighbour left, so its load goes
    unserved."""
    return make_graph(
        subs={"A": (120, 100, 1000), "B": (120, 80, 2000), "C": (120, 90, 3000)},
        grid=[("A", "B"), ("B", "C")],
        hospitals={"H1": ("A", 8.0), "H2": ("C", 8.0)},
        pumps={"P1": ("B", 6.0)},
    )
