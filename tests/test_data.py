"""Checks that the generated data files agree with each other."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def load(relative):
    with open(ROOT / relative, encoding="utf-8") as handle:
        return json.load(handle)


def test_every_map_polygon_has_a_region_record():
    polygon_ids = {f["properties"]["id"] for f in load("static/geo/nuts2.geojson")["features"]}
    region_ids = {r["id"] for r in load("data/regions.json")}
    assert polygon_ids == region_ids
    assert len(region_ids) > 300


def test_region_values_are_in_range():
    for region in load("data/regions.json"):
        for name in ("coast", "nature", "historic", "crowd"):
            value = region["features"][name]
            assert value is None or 0 <= value <= 1, (region["id"], name, value)
        if region["climate"]:
            assert len(region["climate"]["temp_max_c"]) == 12, region["id"]
            assert len(region["climate"]["precip_mm"]) == 12, region["id"]
            assert all(-30 < t < 50 for t in region["climate"]["temp_max_c"]), region["id"]
            assert all(0 <= p < 800 for p in region["climate"]["precip_mm"]), region["id"]
        lat, lon = region["centroid"]
        assert 25 < lat < 82 and -35 < lon < 50, region["id"]


def test_every_value_says_where_it_came_from():
    for region in load("data/regions.json"):
        for name, value in region["features"].items():
            assert (value is None) == (region["sources"][name] is None), (region["id"], name)
        assert (region["climate"] is None) == (region["sources"]["climate"] is None), region["id"]


def test_cities_belong_to_known_regions_and_have_unique_ids():
    region_ids = {r["id"] for r in load("data/regions.json")}
    cities = load("data/cities.json")
    ids = [city["id"] for city in cities]
    assert len(ids) == len(set(ids))
    for city in cities:
        assert city["region_id"] in region_ids, city["id"]
        assert 25 < city["lat"] < 82 and -35 < city["lon"] < 50, city["id"]


def test_every_curated_city_made_it_into_the_city_list():
    curated = load("data/curated/cities.json")["cities"]
    by_region = {}
    for city in load("data/cities.json"):
        by_region.setdefault(city["region_id"], set()).add(city["name"])
    for entry in curated:
        assert entry["name"] in by_region[entry["region_id"]], entry["name"]
