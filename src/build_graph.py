"""D1 step 2 — turn cached OSM layers into the node/edge tables and a NetworkX graph.

Reads data/raw/{layer}_{city}.json (written by fetch_data.py), assigns attributes from
config.yaml's `assumptions` block (all seeded), builds topology per CLAUDE.md's rules, and
writes data/processed/{nodes.csv, edges.csv, graph.gpickle}.
"""

from __future__ import annotations

import json
import math
import pickle
import random
from pathlib import Path
from typing import Any

import networkx as nx
import pandas as pd
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = REPO_ROOT / "data" / "raw"
PROCESSED_DIR = REPO_ROOT / "data" / "processed"


def load_config() -> dict[str, Any]:
    with open(REPO_ROOT / "config.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in km."""
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def _load_layer(layer: str, city: str) -> list[dict[str, Any]]:
    path = RAW_DIR / f"{layer}_{city}.json"
    elements: list[dict[str, Any]] = []
    if path.exists():
        with open(path, encoding="utf-8") as f:
            elements.extend(json.load(f)["elements"])
    synth_path = RAW_DIR / f"{layer}_{city}_synthetic.json"
    if synth_path.exists():
        with open(synth_path, encoding="utf-8") as f:
            elements.extend(json.load(f)["elements"])
    return elements


def build_nodes(city: str, cfg: dict[str, Any]) -> pd.DataFrame:
    """Assemble the node table for one city from cached raw layers."""
    seed = cfg["seed"]
    rng = random.Random(seed)
    a = cfg["assumptions"]

    rows: list[dict[str, Any]] = []

    substations = _load_layer("substation", city)
    print(f"[build_graph] {len(substations)} raw substation elements")
    for i, el in enumerate(substations):
        cap = rng.uniform(*a["capacity_mw_range"])
        load = rng.uniform(*a["load_fraction_of_capacity_range"]) * cap
        pop = rng.randint(int(a["population_served_range"][0]), int(a["population_served_range"][1]))
        rows.append(
            {
                "id": f"sub_{i+1:03d}",
                "type": "substation",
                "lat": el["lat"],
                "lon": el["lon"],
                "name": el.get("tags", {}).get("name", ""),
                "capacity": round(cap, 2),
                "load": round(load, 2),
                "population_served": pop,
                "buffer_hours": "",
                "provenance": el.get("provenance", "observed"),
            }
        )

    hospitals = _load_layer("hospital", city)
    print(f"[build_graph] {len(hospitals)} raw hospital elements")
    for i, el in enumerate(hospitals):
        rows.append(
            {
                "id": f"hosp_{i+1:03d}",
                "type": "hospital",
                "lat": el["lat"],
                "lon": el["lon"],
                "name": el.get("tags", {}).get("name", ""),
                "capacity": "",
                "load": "",
                "population_served": "",
                "buffer_hours": a["hospital_buffer_hours"],
                "provenance": el.get("provenance", "observed"),
            }
        )

    pumps = _load_layer("water", city)
    print(f"[build_graph] {len(pumps)} raw water/pump elements")
    for i, el in enumerate(pumps):
        rows.append(
            {
                "id": f"pump_{i+1:03d}",
                "type": "pump",
                "lat": el["lat"],
                "lon": el["lon"],
                "name": el.get("tags", {}).get("name", ""),
                "capacity": "",
                "load": "",
                "population_served": "",
                "buffer_hours": a["pump_buffer_hours"],
                "provenance": el.get("provenance", "observed"),
            }
        )

    df = pd.DataFrame(rows)
    if df.empty:
        raise RuntimeError(f"No nodes assembled for city={city}. Check data/raw/ cache.")
    return df


def _knn_substation_edges(nodes: pd.DataFrame, k: int = 3) -> list[tuple[str, str]]:
    subs = nodes[nodes["type"] == "substation"]
    edges: set[tuple[str, str]] = set()
    for _, row in subs.iterrows():
        dists = []
        for _, other in subs.iterrows():
            if other["id"] == row["id"]:
                continue
            d = haversine_km(row["lat"], row["lon"], other["lat"], other["lon"])
            dists.append((d, other["id"]))
        dists.sort(key=lambda x: x[0])
        for _, nid in dists[:k]:
            pair = tuple(sorted((row["id"], nid)))
            edges.add(pair)
    return sorted(edges)


def _nearest_substation_edges(nodes: pd.DataFrame, asset_type: str) -> list[tuple[str, str]]:
    subs = nodes[nodes["type"] == "substation"]
    assets = nodes[nodes["type"] == asset_type]
    edges = []
    for _, asset in assets.iterrows():
        best = None
        best_d = math.inf
        for _, sub in subs.iterrows():
            d = haversine_km(asset["lat"], asset["lon"], sub["lat"], sub["lon"])
            if d < best_d:
                best_d = d
                best = sub["id"]
        if best is not None:
            edges.append((best, asset["id"]))  # directed sub -> asset
    return edges


def build_edges(nodes: pd.DataFrame) -> pd.DataFrame:
    """Grid edges (sub<->sub, KNN=3) + supply edges (sub->hospital/pump, nearest)."""
    rows = []
    for src, tgt in _knn_substation_edges(nodes, k=3):
        rows.append({"source": src, "target": tgt, "type": "grid", "provenance": "inferred"})
    for src, tgt in _nearest_substation_edges(nodes, "hospital"):
        rows.append({"source": src, "target": tgt, "type": "supply", "provenance": "inferred"})
    for src, tgt in _nearest_substation_edges(nodes, "pump"):
        rows.append({"source": src, "target": tgt, "type": "supply", "provenance": "inferred"})
    return pd.DataFrame(rows)


def to_networkx(nodes: pd.DataFrame, edges: pd.DataFrame) -> nx.DiGraph:
    """Directed graph: grid edges added both directions, supply edges sub->asset only."""
    G = nx.DiGraph()
    for _, row in nodes.iterrows():
        attrs = row.to_dict()
        node_id = attrs.pop("id")
        G.add_node(node_id, **attrs)
    for _, row in edges.iterrows():
        if row["type"] == "grid":
            G.add_edge(row["source"], row["target"], type=row["type"], provenance=row["provenance"])
            G.add_edge(row["target"], row["source"], type=row["type"], provenance=row["provenance"])
        else:
            G.add_edge(row["source"], row["target"], type=row["type"], provenance=row["provenance"])
    return G


def build(city: str, cfg: dict[str, Any]) -> tuple[pd.DataFrame, pd.DataFrame, nx.DiGraph]:
    nodes = build_nodes(city, cfg)
    edges = build_edges(nodes)
    G = to_networkx(nodes, edges)

    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    nodes.to_csv(PROCESSED_DIR / "nodes.csv", index=False)
    edges.to_csv(PROCESSED_DIR / "edges.csv", index=False)
    with open(PROCESSED_DIR / "graph.gpickle", "wb") as f:
        pickle.dump(G, f)

    print(f"[build_graph] wrote {len(nodes)} nodes, {len(edges)} edges for city={city}")
    print(f"[build_graph] -> {PROCESSED_DIR/'nodes.csv'}")
    print(f"[build_graph] -> {PROCESSED_DIR/'edges.csv'}")
    print(f"[build_graph] -> {PROCESSED_DIR/'graph.gpickle'}")
    return nodes, edges, G


def main() -> None:
    cfg = load_config()
    # Determine which city fetch_data.py actually accepted by checking which raw files exist
    # with enough substation elements — mirrors fetch_with_fallback's logic without re-fetching.
    from fetch_data import fetch_with_fallback  # local import: avoids network cost if unused

    accepted_city = None
    for city in cfg["cities"]["order"]:
        if city not in cfg["cities"]:
            continue
        path = RAW_DIR / f"substation_{city}.json"
        if path.exists():
            with open(path, encoding="utf-8") as f:
                n = len(json.load(f)["elements"])
            if n >= cfg["overpass"]["min_nodes_to_accept_city"]:
                accepted_city = city
                break
    if accepted_city is None:
        print("[build_graph] no cached city clears the threshold yet; running fetch_data.py")
        accepted_city, _ = fetch_with_fallback(cfg)

    print(f"[build_graph] building graph for city={accepted_city}")
    build(accepted_city, cfg)


if __name__ == "__main__":
    main()
