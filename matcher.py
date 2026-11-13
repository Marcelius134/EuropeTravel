"""Scores how well each region fits the traveller's filters.

The page sends the chosen filters, for example
    {"temperature": "high", "coast": "high", "crowd": "low"}
and optionally a month (1 to 12). Every region gets a score from 0 to 100,
or None when the region has no data for one of the chosen filters.
"""

# Each level is one third of the 0 to 1 scale: (start, end).
LEVEL_BANDS = {"low": (0.0, 1 / 3), "medium": (1 / 3, 2 / 3), "high": (2 / 3, 1.0)}
# Outside its band a value still earns partial credit, falling to nothing
# once it is this far away.
NEAR_MISS_DISTANCE = 0.2

# The order here is the order of the filter panel.
FILTERS = {
    "temperature": {
        "label": "Temperature",
        "levels": {"low": "Cool", "medium": "Mild", "high": "Hot"},
        "seasonal": True,
    },
    "rainfall": {
        "label": "Rainfall",
        "levels": {"low": "Dry", "medium": "Some rain", "high": "Rainy"},
        "seasonal": True,
    },
    "coast": {
        "label": "Sea and coast",
        "levels": {"low": "Inland", "medium": "Some coast", "high": "Seaside"},
        "seasonal": False,
    },
    "nature": {
        "label": "Mountains and wild nature",
        "levels": {"low": "Flat, built-up", "medium": "Mixed", "high": "Wild"},
        "seasonal": False,
    },
    "historic": {
        "label": "Historic feel",
        "levels": {"low": "Little", "medium": "Some", "high": "Rich"},
        "seasonal": False,
    },
    "crowd": {
        "label": "Crowds",
        "levels": {"low": "Quiet", "medium": "Moderate", "high": "Busy"},
        "seasonal": False,
    },
}

MONTH_NAMES = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]
SUMMER_MONTHS = (6, 7, 8)

# Summer-style daily highs are placed on a scale from 10 C to 34 C. In thirds
# that makes "cool" below 18 C, "mild" 18 to 26 C and "hot" above 26 C.
TEMP_COLD_C = 10.0
TEMP_HOT_C = 34.0
# Monthly rain is placed on a scale from 0 to 120 mm. In thirds that makes
# "dry" below 40 mm, "some rain" 40 to 80 mm and "rainy" above 80 mm.
RAIN_WET_MM = 120.0

DEFAULT_THRESHOLD = 70


class FilterError(ValueError):
    """The request named a filter, level or month that does not exist."""


def _clamp(value):
    return max(0.0, min(1.0, value))


def validate(filters, month):
    """Check the request and return (filters, month) in a clean form."""
    if not isinstance(filters, dict):
        raise FilterError("'filters' must be an object such as {\"coast\": \"high\"}.")
    clean = {}
    for name, level in filters.items():
        if name not in FILTERS:
            raise FilterError(f"Unknown filter '{name}'. Use one of: {', '.join(FILTERS)}.")
        if level is None:
            continue
        if level not in LEVEL_BANDS:
            raise FilterError(f"Unknown level '{level}' for '{name}'. Use low, medium or high.")
        clean[name] = level
    if month is not None:
        if isinstance(month, bool) or not isinstance(month, int) or not 1 <= month <= 12:
            raise FilterError("'month' must be a number from 1 to 12, or null for summer.")
    return clean, month


def climate_value(region, kind, month=None):
    """Average of a climate series for one month, or for June to August."""
    climate = region.get("climate")
    if not climate:
        return None
    series = climate["temp_max_c"] if kind == "temperature" else climate["precip_mm"]
    months = (month,) if month else SUMMER_MONTHS
    return sum(series[m - 1] for m in months) / len(months)


def feature_value(region, name, month=None):
    """The region's value for one filter on the 0 to 1 scale, or None if unknown."""
    if name == "temperature":
        degrees = climate_value(region, "temperature", month)
        if degrees is None:
            return None
        return _clamp((degrees - TEMP_COLD_C) / (TEMP_HOT_C - TEMP_COLD_C))
    if name == "rainfall":
        millimetres = climate_value(region, "rainfall", month)
        if millimetres is None:
            return None
        return _clamp(millimetres / RAIN_WET_MM)
    return region["features"].get(name)


def level_of(value):
    """Name the third of the scale a value falls in."""
    if value is None:
        return None
    if value < 1 / 3:
        return "low"
    if value < 2 / 3:
        return "medium"
    return "high"


def match_one(value, level):
    """How well a value fits the wanted level, from 0 to 1.

    Inside the level's third of the scale the fit is perfect. Outside it the
    fit drops in a straight line and reaches 0 at NEAR_MISS_DISTANCE away.
    """
    start, end = LEVEL_BANDS[level]
    if value < start:
        distance = start - value
    elif value > end:
        distance = value - end
    else:
        return 1.0
    return _clamp(1.0 - distance / NEAR_MISS_DISTANCE)


def _depth(value, level):
    """How far inside the wanted end of the scale a value sits. Only breaks ties."""
    start, end = LEVEL_BANDS[level]
    centre = {"low": 0.0, "medium": 0.5, "high": 1.0}[level]
    return 1.0 - abs(value - centre)


def score_region(region, filters, month=None):
    """Score one region against already validated filters."""
    matches = {}
    missing = []
    depth = 0.0
    for name, level in filters.items():
        value = feature_value(region, name, month)
        if value is None:
            missing.append(name)
        else:
            matches[name] = round(match_one(value, level) * 100)
            depth += _depth(value, level)
    if missing or not matches:
        score = None
    else:
        score = round(sum(matches.values()) / len(matches))
    return {"id": region["id"], "score": score, "matches": matches, "missing": missing, "_depth": depth}


def score_all(regions, filters, month=None):
    """Score every region. Returns a list ordered best first, unknown last."""
    filters, month = validate(filters, month)
    results = [score_region(region, filters, month) for region in regions]
    # Best score first; equal scores are ordered by how firmly the region sits
    # in the wanted range, then by id so the order never changes between runs.
    results.sort(key=lambda r: (r["score"] is None, -(r["score"] or 0), -r["_depth"], r["id"]))
    for result in results:
        del result["_depth"]
    return results


def describe(region):
    """A plain sentence about a region, used when nobody has written a summary."""
    features = region["features"]
    parts = []
    coast = level_of(features.get("coast"))
    if coast == "high":
        parts.append("a long coastline")
    elif coast == "medium":
        parts.append("some coastline")
    elif coast == "low":
        parts.append("no real coastline")
    nature = level_of(features.get("nature"))
    if nature == "high":
        parts.append("mountainous, thinly settled country")
    elif nature == "low":
        parts.append("mostly flat or built-up land")
    historic = level_of(features.get("historic"))
    if historic == "high":
        parts.append("a lot of heritage to see")
    crowd = level_of(features.get("crowd"))
    if crowd == "high":
        parts.append("busy towns")
    elif crowd == "low":
        parts.append("few crowds")

    sentence = f"A region of {region['country_name']}"
    if parts:
        sentence += " with " + ", ".join(parts[:-1]) + (" and " if len(parts) > 1 else "") + parts[-1]
    sentence += "."

    summer = climate_value(region, "temperature")
    if summer is not None:
        sentence += f" Summer afternoons reach about {round(summer)} °C."
    return sentence
