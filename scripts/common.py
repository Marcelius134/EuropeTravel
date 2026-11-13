"""Shared helpers for the data build scripts."""
import json
import re
import time
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
CACHE = DATA / "cache"
COMPUTED = DATA / "computed"
CURATED = DATA / "curated"
GEO = ROOT / "static" / "geo"

USER_AGENT = "EuropeTravel-student-project/0.1 (https://github.com/Marcelius134/EuropeTravel)"

# NUTS country code -> English name. NUTS uses EL for Greece and UK for the
# United Kingdom, where ISO uses GR and GB.
COUNTRY_NAMES = {
    "AL": "Albania", "AT": "Austria", "BE": "Belgium", "BG": "Bulgaria",
    "CH": "Switzerland", "CY": "Cyprus", "CZ": "Czechia", "DE": "Germany",
    "DK": "Denmark", "EE": "Estonia", "EL": "Greece", "ES": "Spain",
    "FI": "Finland", "FR": "France", "HR": "Croatia", "HU": "Hungary",
    "IE": "Ireland", "IS": "Iceland", "IT": "Italy", "LI": "Liechtenstein",
    "LT": "Lithuania", "LU": "Luxembourg", "LV": "Latvia", "ME": "Montenegro",
    "MK": "North Macedonia", "MT": "Malta", "NL": "Netherlands", "NO": "Norway",
    "PL": "Poland", "PT": "Portugal", "RO": "Romania", "RS": "Serbia",
    "SE": "Sweden", "SI": "Slovenia", "SK": "Slovakia", "TR": "Turkey",
    "UK": "United Kingdom",
}
NUTS_TO_ISO = {"EL": "GR", "UK": "GB"}


def iso_country(nuts_country):
    return NUTS_TO_ISO.get(nuts_country, nuts_country)


def load_json(path, default=None):
    path = Path(path)
    if not path.exists():
        return default
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def save_json(path, data, compact=False):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        if compact:
            json.dump(data, handle, ensure_ascii=False, separators=(",", ":"))
        else:
            json.dump(data, handle, ensure_ascii=False, indent=1)
        handle.write("\n")


def slugify(text):
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def percentile_ranks(values):
    """Map {key: number or None} to {key: rank between 0 and 1 or None}.

    The smallest value gets 0, the largest gets 1 and ties share a rank.
    """
    known = sorted(v for v in values.values() if v is not None)
    if not known:
        return {key: None for key in values}
    if len(known) == 1:
        return {key: (0.5 if v is not None else None) for key, v in values.items()}
    first_index = {}
    last_index = {}
    for index, value in enumerate(known):
        first_index.setdefault(value, index)
        last_index[value] = index
    top = len(known) - 1
    return {
        key: (None if v is None else round((first_index[v] + last_index[v]) / 2 / top, 3))
        for key, v in values.items()
    }


def fetch(url, params=None, cache_file=None, as_json=True, headers=None, retries=4, timeout=60):
    """GET a URL, with an on-disk cache and polite retries.

    Returns parsed JSON (or text when as_json is False). Raises RuntimeError
    with a readable message when the request keeps failing.
    """
    import requests  # imported here so the app and tests do not need it

    if cache_file is not None:
        cache_file = Path(cache_file)
        if cache_file.exists():
            text = cache_file.read_text(encoding="utf-8")
            return json.loads(text) if as_json else text

    all_headers = {"User-Agent": USER_AGENT}
    all_headers.update(headers or {})
    last_error = None
    for attempt in range(retries):
        try:
            response = requests.get(url, params=params, headers=all_headers, timeout=timeout)
            if response.status_code in (429, 500, 502, 503, 504):
                last_error = f"HTTP {response.status_code}"
                time.sleep(3 * (attempt + 1) ** 2)
                continue
            response.raise_for_status()
            text = response.text
            result = json.loads(text) if as_json else text
            if cache_file is not None:
                cache_file.parent.mkdir(parents=True, exist_ok=True)
                cache_file.write_text(text, encoding="utf-8")
            return result
        except (requests.RequestException, ValueError) as error:
            last_error = str(error)
            time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"Could not fetch {url}: {last_error}")
