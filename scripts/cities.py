"""Cities, from the GeoNames list shipped in the `geonamescache` package.

GeoNames data is licensed CC BY 4.0 (https://www.geonames.org).
"""
from .common import COMPUTED, iso_country, load_json, percentile_ranks, save_json
from .geometry import load_region_shapes

# A city just off the simplified coastline still belongs to the nearest region.
SNAP_DISTANCE_DEGREES = 0.2


def cities_by_region():
    """Return {region id: [city dict, ...]} for every GeoNames city over 15,000 people."""
    import geonamescache
    from shapely import STRtree
    from shapely.geometry import Point

    shapes = load_region_shapes()
    ids = list(shapes)
    tree = STRtree([shapes[region_id] for region_id in ids])
    countries = {iso_country(region_id[:2]) for region_id in ids}

    grouped = {region_id: [] for region_id in ids}
    for city in geonamescache.GeonamesCache().get_cities().values():
        if city["countrycode"] not in countries:
            continue
        point = Point(city["longitude"], city["latitude"])
        match = None
        for index in tree.query(point, predicate="within"):
            match = ids[index]
            break
        if match is None:
            index = tree.nearest(point)
            if shapes[ids[index]].distance(point) <= SNAP_DISTANCE_DEGREES:
                match = ids[index]
        if match is None or iso_country(match[:2]) != city["countrycode"]:
            continue
        grouped[match].append({
            "geonameid": city["geonameid"],
            "name": city["name"],
            "lat": round(city["latitude"], 4),
            "lon": round(city["longitude"], 4),
            "population": city["population"],
        })
    for cities in grouped.values():
        cities.sort(key=lambda c: -c["population"])
    return grouped


def build_settlement(grouped=None):
    """Urban population per km2 for every region, ranked from 0 (quiet) to 1 (busy)."""
    grouped = grouped or cities_by_region()
    geometry = load_json(COMPUTED / "geometry.json")
    if geometry is None:
        raise RuntimeError("data/computed/geometry.json is missing. Run the 'geometry' step first.")
    density = {}
    for region_id, info in geometry.items():
        urban = sum(city["population"] for city in grouped.get(region_id, []))
        density[region_id] = urban / info["area_km2"] if info["area_km2"] else None
    ranks = percentile_ranks(density)
    result = {
        region_id: {
            "urban_population": sum(c["population"] for c in grouped.get(region_id, [])),
            "urban_density": None if density[region_id] is None else round(density[region_id], 2),
            "crowd": ranks[region_id],
        }
        for region_id in geometry
    }
    save_json(COMPUTED / "settlement.json", result)
    print(f"settlement: wrote {len(result)} regions to data/computed/settlement.json")
    return result
