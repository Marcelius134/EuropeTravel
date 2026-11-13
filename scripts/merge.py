"""Combine measured values and hand-written values into the files the app reads."""
from .common import COMPUTED, COUNTRY_NAMES, CURATED, DATA, iso_country, load_json, save_json, slugify
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


def merge_cities(top_cities, curated_cities, travel_notes=None):
    """Build the city list from the GeoNames picks and the hand-written notes.

    top_cities:     {region id: [GeoNames city, ...]}
    curated_cities: list of hand-written entries, matched by geonames_name
    travel_notes:   {city id: {"summary": ..., "things_to_do": [...]}} from Wikivoyage
    """
    travel_notes = travel_notes or {}
    curated_by_key = {(entry["region_id"], entry["geonames_name"]): entry for entry in curated_cities}
    seen_curated = set()

    rows = []
    for region_id, records in top_cities.items():
        for record in records:
            key = (region_id, record["name"])
            seen_curated.add(key)
            rows.append((region_id, record, curated_by_key.get(key)))
    # A curated city that GeoNames does not list still appears, at its hand-written position.
    for key, entry in curated_by_key.items():
        if key in seen_curated:
            continue
        if entry.get("lat") is None or entry.get("lon") is None:
            raise RuntimeError(f"Curated city {entry['name']} is not in GeoNames and has no lat/lon.")
        record = {"name": entry["geonames_name"], "lat": entry["lat"], "lon": entry["lon"], "population": None}
        rows.append((entry["region_id"], record, entry))

    cities = []
    used_ids = set()
    for region_id, record, entry in rows:
        name = entry["name"] if entry else record["name"]
        city_id = slugify(name) + "-" + iso_country(region_id[:2]).lower()
        if city_id in used_ids:
            city_id += "-" + region_id.lower()
        used_ids.add(city_id)
        fetched = travel_notes.get(city_id, {})
        if entry:
            summary, things, text_source = entry["summary"], entry["things_to_do"], "curated-estimate"
        elif fetched.get("summary"):
            summary, things, text_source = fetched["summary"], fetched.get("things_to_do", []), "wikivoyage"
        else:
            summary, things, text_source = None, [], None
        cities.append({
            "id": city_id,
            "name": name,
            "region_id": region_id,
            "lat": record["lat"],
            "lon": record["lon"],
            "population": record.get("population"),
            "summary": summary,
            "things_to_do": things,
            "sources": {
                "position": "geonames" if record.get("population") else "curated-estimate",
                "text": text_source,
            },
        })
    cities.sort(key=lambda city: (city["region_id"], -(city["population"] or 0), city["id"]))
    return cities


def build_cities():
    top_cities = load_json(COMPUTED / "cities.json")
    if top_cities is None:
        raise RuntimeError("data/computed/cities.json is missing. Run the 'cities' step first.")
    curated = load_json(CURATED / "cities.json", {"cities": []})["cities"]
    notes = load_json(COMPUTED / "city_notes.json", {})
    cities = merge_cities(top_cities, curated, notes)
    save_json(DATA / "cities.json", cities)
    with_text = sum(1 for city in cities if city["summary"])
    print(f"merge: wrote {len(cities)} cities to data/cities.json ({with_text} with travel notes)")
    return cities


def merge_places(cities, curated_places, fetched_places):
    """Build the place list. Hand-written places win for a city that has them."""
    city_ids = {city["id"] for city in cities}
    unknown = sorted(set(curated_places) - city_ids)
    if unknown:
        raise RuntimeError("data/curated/places.json names cities that do not exist: " + ", ".join(unknown))
    places = []
    used_ids = set()
    for city in cities:
        city_id = city["id"]
        if city_id in curated_places:
            entries, source = curated_places[city_id], "curated-estimate"
        else:
            entries, source = fetched_places.get(city_id, []), "wikivoyage"
        for entry in entries:
            place_id = city_id + "-" + slugify(entry["name"])
            while place_id in used_ids:
                place_id += "-2"
            used_ids.add(place_id)
            places.append({
                "id": place_id,
                "city_id": city_id,
                "name": entry["name"],
                "category": entry["category"],
                "lat": entry["lat"],
                "lon": entry["lon"],
                "description": entry.get("description", ""),
                "source": source,
            })
    return places


def build_places(cities=None):
    cities = cities or load_json(DATA / "cities.json", [])
    curated = load_json(CURATED / "places.json", {"places": {}})["places"]
    fetched = load_json(COMPUTED / "places.json", {})
    places = merge_places(cities, curated, fetched)
    save_json(DATA / "places.json", places)
    print(f"merge: wrote {len(places)} places to data/places.json")
    return places


def build_all_outputs():
    build_regions()
    cities = build_cities()
    build_places(cities)
