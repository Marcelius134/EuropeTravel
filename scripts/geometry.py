"""Region boundaries and everything computed from their shapes.

Sources:
  - NUTS-2 boundaries: Eurostat GISCO, via github.com/eurostat/Nuts2json
  - Coastline and mountain ranges: Natural Earth (public domain)
"""
import math

from .common import CACHE, COMPUTED, COUNTRY_NAMES, GEO, fetch, load_json, save_json

NUTS_URL = "https://raw.githubusercontent.com/eurostat/Nuts2json/master/pub/v2/2021/4326/20M/nutsrg_2.json"
COAST_URL = "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/ne_50m_coastline.geojson"
RANGES_URL = "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/ne_10m_geography_regions_polys.geojson"

# Rough box around the area the app covers: (min lon, min lat, max lon, max lat).
EUROPE_BOX = (-32.0, 26.0, 46.0, 81.5)

KM_PER_DEGREE_LAT = 110.57
KM_PER_DEGREE_LON = 111.32
# The simplified region outlines and the coastline do not line up exactly,
# so a boundary counts as coastal when it runs within this distance of the sea.
COAST_TOLERANCE_DEGREES = 0.08
# A region whose outline is half coastline already feels fully "seaside".
COAST_SHARE_FOR_FULL_SCORE = 0.5


def build_boundaries():
    """Download the NUTS-2 polygons and save the GeoJSON the map draws."""
    raw = fetch(NUTS_URL, cache_file=CACHE / "nutsrg_2.json")
    features = []
    for feature in raw["features"]:
        region_id = feature["properties"]["id"]
        if region_id[:2] not in COUNTRY_NAMES or region_id.endswith("ZZ"):
            continue
        features.append({
            "type": "Feature",
            "properties": {"id": region_id, "name": feature["properties"]["na"]},
            "geometry": feature["geometry"],
        })
    features.sort(key=lambda f: f["properties"]["id"])
    save_json(GEO / "nuts2.geojson", {"type": "FeatureCollection", "features": features}, compact=True)
    print(f"boundaries: wrote {len(features)} regions to static/geo/nuts2.geojson")
    return features


def load_region_shapes():
    """Return {region id: shapely geometry} from the saved GeoJSON."""
    from shapely.geometry import shape

    geojson = load_json(GEO / "nuts2.geojson")
    if geojson is None:
        raise RuntimeError("static/geo/nuts2.geojson is missing. Run the 'boundaries' step first.")
    shapes = {}
    for feature in geojson["features"]:
        geometry = shape(feature["geometry"])
        if not geometry.is_valid:
            geometry = geometry.buffer(0)
        shapes[feature["properties"]["id"]] = geometry
    return shapes


def region_names():
    geojson = load_json(GEO / "nuts2.geojson")
    return {f["properties"]["id"]: f["properties"]["name"] for f in geojson["features"]}


def _squash(geometry, latitude):
    """Shrink longitudes so that one unit is the same distance in both directions."""
    from shapely import affinity

    return affinity.scale(geometry, xfact=math.cos(math.radians(latitude)), yfact=1.0, origin=(0, 0))


def largest_part(geometry):
    parts = getattr(geometry, "geoms", [geometry])
    return max(parts, key=lambda part: part.area)


def area_km2(geometry):
    latitude = geometry.representative_point().y
    squashed = _squash(geometry, latitude)
    return squashed.area * KM_PER_DEGREE_LON * KM_PER_DEGREE_LAT


def coast_share(geometry, coastline):
    """Share of a region's outline that lies on the sea, between 0 and 1."""
    from shapely.geometry import box

    min_lon, min_lat, max_lon, max_lat = geometry.bounds
    window = box(min_lon - 0.5, min_lat - 0.5, max_lon + 0.5, max_lat + 0.5)
    nearby_coast = coastline.intersection(window)
    if nearby_coast.is_empty:
        return 0.0
    latitude = (min_lat + max_lat) / 2
    outline = _squash(geometry.boundary, latitude)
    sea_edge = _squash(nearby_coast, latitude).buffer(COAST_TOLERANCE_DEGREES)
    if outline.length == 0:
        return 0.0
    return min(1.0, outline.intersection(sea_edge).length / outline.length)


def coast_score(share):
    return round(min(1.0, share / COAST_SHARE_FOR_FULL_SCORE), 3)


def _load_coastline():
    from shapely.geometry import box, shape
    from shapely.ops import unary_union

    raw = fetch(COAST_URL, cache_file=CACHE / "ne_50m_coastline.geojson")
    europe = box(*EUROPE_BOX)
    lines = [shape(f["geometry"]) for f in raw["features"]]
    return unary_union([line.intersection(europe) for line in lines if line.intersects(europe)])


def _load_mountains():
    from shapely.geometry import box, shape
    from shapely.ops import unary_union

    raw = fetch(RANGES_URL, cache_file=CACHE / "ne_10m_geography_regions_polys.geojson")
    europe = box(*EUROPE_BOX)
    ranges = []
    for feature in raw["features"]:
        if feature["properties"].get("FEATURECLA") != "Range/mtn":
            continue
        geometry = shape(feature["geometry"])
        if not geometry.is_valid:
            geometry = geometry.buffer(0)
        if geometry.intersects(europe):
            ranges.append(geometry)
    return unary_union(ranges)


def build_geometry():
    """Compute centroid, area, coast share and mountain share for every region."""
    shapes = load_region_shapes()
    coastline = _load_coastline()
    mountains = _load_mountains()
    result = {}
    for region_id, geometry in sorted(shapes.items()):
        point = largest_part(geometry).representative_point()
        share = coast_share(geometry, coastline)
        mountain = geometry.intersection(mountains).area / geometry.area if geometry.area else 0.0
        result[region_id] = {
            "centroid": [round(point.y, 4), round(point.x, 4)],
            "area_km2": round(area_km2(geometry), 1),
            "coast_share": round(share, 3),
            "coast": coast_score(share),
            "mountain_share": round(min(1.0, mountain), 3),
        }
    save_json(COMPUTED / "geometry.json", result)
    print(f"geometry: wrote {len(result)} regions to data/computed/geometry.json")
    return result
