"""D1 step 1 — fetch substation / hospital / water-infrastructure nodes from OSM Overpass.

Tries cities in `config.yaml: cities.order` until one returns enough substation nodes.
Caches every raw response to data/raw/{layer}_{city}.json and never re-fetches a cached file.
The only network calls in this entire codebase happen here.
"""

from __future__ import annotations

import json
import random
import urllib.request
from pathlib import Path
from typing import Any

import overpy
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = REPO_ROOT / "data" / "raw"

# overpy calls the bare urllib.request.urlopen() with no headers, which some network
# proxies reject (406 Not Acceptable) as a non-browser client. Install a realistic
# User-Agent on the global opener so overpy's requests go through — this is a transport
# fix only, it does not change the query, the endpoint, or the data returned.
_opener = urllib.request.build_opener()
_opener.addheaders = [("User-Agent", "Mozilla/5.0 (compatible; silent-cascade-demo/1.0)")]
urllib.request.install_opener(_opener)

QUERIES = {
    "substation": """
        [out:json][timeout:{timeout}];
        (
          node["power"="substation"]({bbox});
          way["power"="substation"]({bbox});
        );
        out center;
    """,
    "hospital": """
        [out:json][timeout:{timeout}];
        (
          node["amenity"="hospital"]({bbox});
          way["amenity"="hospital"]({bbox});
        );
        out center;
    """,
    "water": """
        [out:json][timeout:{timeout}];
        (
          node["man_made"="water_works"]({bbox});
          way["man_made"="water_works"]({bbox});
          node["man_made"="pumping_station"]({bbox});
          node["man_made"="water_tower"]({bbox});
        );
        out center;
    """,
}


def load_config() -> dict[str, Any]:
    with open(REPO_ROOT / "config.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _bbox_str(bbox: list[float]) -> str:
    # OSM/Overpass bbox order is (south, west, north, east) — matches config.yaml.
    return ",".join(str(v) for v in bbox)


def _result_to_plain(result: overpy.Result) -> dict[str, Any]:
    """Flatten an overpy Result into plain dicts so it's JSON-cacheable."""
    elements = []
    for n in result.nodes:
        elements.append(
            {
                "osm_type": "node",
                "id": n.id,
                "lat": float(n.lat),
                "lon": float(n.lon),
                "tags": dict(n.tags),
            }
        )
    for w in result.ways:
        center_lat = getattr(w, "center_lat", None)
        center_lon = getattr(w, "center_lon", None)
        if center_lat is None or center_lon is None:
            # fallback: average of node coords if the way carries them
            try:
                lats = [float(nd.lat) for nd in w.nodes]
                lons = [float(nd.lon) for nd in w.nodes]
                center_lat = sum(lats) / len(lats)
                center_lon = sum(lons) / len(lons)
            except Exception:
                continue
        elements.append(
            {
                "osm_type": "way",
                "id": w.id,
                "lat": float(center_lat),
                "lon": float(center_lon),
                "tags": dict(w.tags),
            }
        )
    return {"elements": elements}


def _convert_raw_overpass_json(raw: dict[str, Any]) -> dict[str, Any]:
    """Convert a standard Overpass API JSON response (e.g. exported from overpass-turbo.eu's
    "download / copy as raw OSM data" option) into this repo's plain cache schema."""
    elements = []
    for el in raw.get("elements", []):
        if el.get("type") == "node":
            lat, lon = el.get("lat"), el.get("lon")
        elif el.get("type") == "way":
            center = el.get("center", {})
            lat, lon = center.get("lat"), center.get("lon")
        else:
            continue
        if lat is None or lon is None:
            continue
        elements.append(
            {
                "osm_type": el["type"],
                "id": el["id"],
                "lat": float(lat),
                "lon": float(lon),
                "tags": el.get("tags", {}),
            }
        )
    return {"elements": elements}


def fetch_layer(layer: str, city: str, bbox: list[float], cfg: dict[str, Any]) -> dict[str, Any]:
    """Fetch one OSM layer for one city, using the on-disk cache if present.

    Also checks data/raw/manual/{layer}_{city}.json — a manually-provided raw Overpass JSON
    export (e.g. from overpass-turbo.eu) — for use when live Overpass access is blocked.
    """
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    cache_path = RAW_DIR / f"{layer}_{city}.json"

    if cache_path.exists():
        print(f"[fetch_data] cache hit: {cache_path.name}")
        with open(cache_path, encoding="utf-8") as f:
            return json.load(f)

    manual_path = RAW_DIR / "manual" / f"{layer}_{city}.json"
    if manual_path.exists():
        print(f"[fetch_data] using manually-provided Overpass export: {manual_path}")
        with open(manual_path, encoding="utf-8") as f:
            raw = json.load(f)
        plain = _convert_raw_overpass_json(raw)
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump(plain, f, indent=2)
        print(f"[fetch_data] converted {len(plain['elements'])} {layer} elements from manual export -> {cache_path.name}")
        return plain

    print(f"[fetch_data] fetching {layer} for {city} from Overpass...")
    api = overpy.Overpass(url=cfg["overpass"]["endpoint"])
    query = QUERIES[layer].format(timeout=cfg["overpass"]["timeout"], bbox=_bbox_str(bbox))
    try:
        result = api.query(query)
    except Exception as exc:
        print(f"[fetch_data] WARNING: Overpass query failed for {layer}/{city}: {exc}")
        return {"elements": []}

    plain = _result_to_plain(result)
    with open(cache_path, "w", encoding="utf-8") as f:
        json.dump(plain, f, indent=2)
    print(f"[fetch_data] cached {len(plain['elements'])} {layer} elements -> {cache_path.name}")
    return plain


def synthesize_water_nodes(city: str, bbox: list[float], count: int, seed: int) -> dict[str, Any]:
    """Synthesise pumping-station points within bbox when OSM water data is too sparse.

    Marks provenance="synthetic" on every element so build_graph.py can propagate it.
    """
    rng = random.Random(seed)
    south, west, north, east = bbox
    elements = []
    for i in range(count):
        lat = rng.uniform(south, north)
        lon = rng.uniform(west, east)
        elements.append(
            {
                "osm_type": "synthetic",
                "id": f"synthetic_pump_{city}_{i:03d}",
                "lat": lat,
                "lon": lon,
                "tags": {"man_made": "pumping_station", "name": ""},
                "provenance": "synthetic",
            }
        )
    print(
        f"[fetch_data] WARNING: fewer than the configured minimum water nodes found for "
        f"{city}; synthesising {count} pumping stations at random points in bbox. "
        f"provenance=synthetic."
    )
    cache_path = RAW_DIR / f"water_{city}_synthetic.json"
    with open(cache_path, "w", encoding="utf-8") as f:
        json.dump({"elements": elements}, f, indent=2)
    return {"elements": elements}


def fetch_city(city: str, cfg: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Fetch all three layers for one city. Returns {layer: plain_result}."""
    bbox = cfg["cities"][city]["bbox"]
    layers: dict[str, dict[str, Any]] = {}
    for layer in ("substation", "hospital", "water"):
        layers[layer] = fetch_layer(layer, city, bbox, cfg)

    min_water = cfg["overpass"]["min_water_nodes_before_synthesis"]
    if len(layers["water"]["elements"]) < min_water:
        synth = synthesize_water_nodes(
            city, bbox, cfg["overpass"]["synthetic_water_node_count"], cfg["seed"]
        )
        layers["water"]["elements"].extend(synth["elements"])

    return layers


def fetch_with_fallback(cfg: dict[str, Any]) -> tuple[str, dict[str, dict[str, Any]]]:
    """Try cities in configured order until substation count clears the minimum."""
    min_nodes = cfg["overpass"]["min_nodes_to_accept_city"]
    for city in cfg["cities"]["order"]:
        if city not in cfg["cities"]:
            print(f"[fetch_data] skipping '{city}': no bbox configured for it.")
            continue
        print(f"[fetch_data] trying city: {city}")
        layers = fetch_city(city, cfg)
        n_sub = len(layers["substation"]["elements"])
        print(f"[fetch_data] {city}: {n_sub} substation nodes")
        if n_sub >= min_nodes:
            print(f"[fetch_data] accepted city: {city} ({n_sub} substation nodes)")
            return city, layers
        print(
            f"[fetch_data] {city} has only {n_sub} substation nodes "
            f"(< {min_nodes} required) — trying next fallback city."
        )
    raise RuntimeError(
        "No configured city cleared the minimum substation-node threshold. "
        "Stopping rather than silently using an under-populated graph — "
        "ask the user which city/data source to use next."
    )


def main() -> None:
    cfg = load_config()
    city, layers = fetch_with_fallback(cfg)
    print(f"[fetch_data] DONE. city={city}")
    for layer, data in layers.items():
        print(f"  {layer}: {len(data['elements'])} elements")


if __name__ == "__main__":
    main()
