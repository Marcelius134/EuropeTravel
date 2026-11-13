"""Heritage counts per region, from Wikidata.

Counts UNESCO World Heritage sites and castles that have coordinates, then
ranks the regions. Wikidata is CC0. https://query.wikidata.org
"""
import re

from .common import CACHE, COMPUTED, fetch, percentile_ranks, save_json
from .geometry import EUROPE_BOX, load_region_shapes

SPARQL_URL = "https://query.wikidata.org/sparql"

WORLD_HERITAGE_QUERY = """
SELECT ?item ?coord WHERE {
  ?item wdt:P1435 wd:Q9259 ;
        wdt:P625 ?coord .
}
"""
CASTLE_QUERY = """
SELECT ?item ?coord WHERE {
  ?item wdt:P31 wd:Q23413 ;
        wdt:P625 ?coord .
}
"""
# One World Heritage site weighs as much as this many castles.
CASTLES_PER_HERITAGE_SITE = 25

_POINT = re.compile(r"Point\(\s*(-?[\d.]+(?:[eE]-?\d+)?)\s+(-?[\d.]+(?:[eE]-?\d+)?)\s*\)")


def parse_points(payload):
    """Return unique (lon, lat) points, one per item, from a SPARQL JSON result."""
    points = {}
    for row in payload["results"]["bindings"]:
        match = _POINT.search(row["coord"]["value"])
        if match:
            points.setdefault(row["item"]["value"], (float(match.group(1)), float(match.group(2))))
    return list(points.values())


def _run_query(name, query):
    payload = fetch(
        SPARQL_URL,
        params={"query": query, "format": "json"},
        headers={"Accept": "application/sparql-results+json"},
        cache_file=CACHE / "wikidata" / f"{name}.json",
        timeout=120,
    )
    return parse_points(payload)


def count_by_region(points, shapes):
    from shapely import STRtree
    from shapely.geometry import Point

    ids = list(shapes)
    tree = STRtree([shapes[region_id] for region_id in ids])
    min_lon, min_lat, max_lon, max_lat = EUROPE_BOX
    counts = {region_id: 0 for region_id in ids}
    for lon, lat in points:
        if not (min_lon <= lon <= max_lon and min_lat <= lat <= max_lat):
            continue
        for index in tree.query(Point(lon, lat), predicate="within"):
            counts[ids[index]] += 1
            break
    return counts


def heritage_score(world_heritage_sites, castles):
    return world_heritage_sites + castles / CASTLES_PER_HERITAGE_SITE


def build_heritage():
    shapes = load_region_shapes()
    sites = count_by_region(_run_query("world_heritage", WORLD_HERITAGE_QUERY), shapes)
    castles = count_by_region(_run_query("castles", CASTLE_QUERY), shapes)
    raw = {region_id: heritage_score(sites[region_id], castles[region_id]) for region_id in shapes}
    ranks = percentile_ranks(raw)
    result = {
        region_id: {
            "world_heritage_sites": sites[region_id],
            "castles": castles[region_id],
            "historic": ranks[region_id],
        }
        for region_id in sorted(shapes)
    }
    save_json(COMPUTED / "heritage.json", result)
    print(f"heritage: wrote {len(result)} regions to data/computed/heritage.json")
    return result
