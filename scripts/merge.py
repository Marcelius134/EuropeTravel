"""Combine measured values and hand-written values into the files the app reads."""
from .common import COMPUTED, COUNTRY_NAMES, CURATED, DATA, load_json, save_json
from .geometry import region_names

# Mountains alone make a region fully "wild" once they cover this share of it.
MOUNTAIN_SHARE_FOR_FULL_SCORE = 0.6
MOUNTAIN_WEIGHT = 0.65
QUIETNESS_WEIGHT = 0.35


def nature_proxy(mountain_share, crowd):
    """Estimate 'nature' from terrain and how sparsely the region is settled."""
    mountains = min(1.0, mountain_share / MOUNTAIN_SHARE_FOR_FULL_SCORE)
    quietness = 1.0 - (crowd if crowd is not None else 0.5)
    return round(MOUNTAIN_WEIGHT * mountains + QUIETNESS_WEIGHT * quietness, 3)


def merge_region(region_id, name, geometry, settlement, climate, heritage, curated):
    """Build one region record. Each argument is that region's entry or None."""
    curated = curated or {}
    curated_features = curated.get("features", {})
    features = {}
    sources = {}

    features["coast"] = geometry["coast"]
    sources["coast"] = "natural-earth"

    crowd_measured = settlement["crowd"] if settlement else None
    if "nature" in curated_features:
        features["nature"], sources["nature"] = curated_features["nature"], "curated-estimate"
    else:
        features["nature"] = nature_proxy(geometry["mountain_share"], crowd_measured)
        sources["nature"] = "proxy"

    if "historic" in curated_features:
        features["historic"], sources["historic"] = curated_features["historic"], "curated-estimate"
    elif heritage:
        features["historic"], sources["historic"] = heritage["historic"], "wikidata"
    else:
        features["historic"], sources["historic"] = None, None

    if "crowd" in curated_features:
        features["crowd"], sources["crowd"] = curated_features["crowd"], "curated-estimate"
    else:
        features["crowd"] = crowd_measured
        sources["crowd"] = "geonames" if crowd_measured is not None else None

    if climate:
        climate_out = {"temp_max_c": climate["temp_max_c"], "precip_mm": climate["precip_mm"]}
        sources["climate"] = climate["source"]
    elif "climate" in curated:
        climate_out, sources["climate"] = curated["climate"], "curated-estimate"
    else:
        climate_out, sources["climate"] = None, None

    return {
        "id": region_id,
        "name": curated.get("name", name),
        "country": region_id[:2],
        "country_name": COUNTRY_NAMES[region_id[:2]],
        "centroid": geometry["centroid"],
        "area_km2": geometry["area_km2"],
        "climate": climate_out,
        "features": features,
        "summary": curated.get("summary"),
        "highlights": curated.get("highlights", []),
        "sources": sources,
    }


def build_regions():
    geometry = load_json(COMPUTED / "geometry.json")
    if geometry is None:
        raise RuntimeError("data/computed/geometry.json is missing. Run the 'geometry' step first.")
    settlement = load_json(COMPUTED / "settlement.json", {})
    climate = load_json(COMPUTED / "climate.json", {})
    heritage = load_json(COMPUTED / "heritage.json", {})
    curated = load_json(CURATED / "regions.json", {"regions": {}})["regions"]
    names = region_names()

    unknown = sorted(set(curated) - set(geometry))
    if unknown:
        raise RuntimeError("data/curated/regions.json has ids that are not NUTS-2 regions: " + ", ".join(unknown))

    regions = [
        merge_region(
            region_id, names[region_id], geometry[region_id], settlement.get(region_id),
            climate.get(region_id), heritage.get(region_id), curated.get(region_id),
        )
        for region_id in sorted(geometry)
    ]
    save_json(DATA / "regions.json", regions)
    with_climate = sum(1 for region in regions if region["climate"])
    with_history = sum(1 for region in regions if region["features"]["historic"] is not None)
    print(
        f"merge: wrote {len(regions)} regions to data/regions.json "
        f"({with_climate} with climate, {with_history} with a heritage score)"
    )
    return regions


def build_all_outputs():
    build_regions()
