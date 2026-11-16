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


class FetchError(RuntimeError):
    """A download failed for good. The message says which URL and why."""


# Worth another try: the server was busy or briefly broken.
RETRY_STATUSES = (408, 425, 429, 500, 502, 503, 504)
# Never wait longer than this for one retry, whatever the server asks for.
MAX_WAIT_SECONDS = 90


def _http_get(url, params, headers, timeout):
    """One GET. Returns (status code, body text, Retry-After header or None).

    Kept separate so the tests can replace it and never touch the network.
    Raises OSError when there is no answer at all.
    """
    try:
        import requests  # imported here so the app and tests do not need it
    except ImportError:
        raise FetchError("The 'requests' package is missing. Run: pip install -r requirements-data.txt")
    try:
        response = requests.get(url, params=params, headers=headers, timeout=timeout)
    except requests.RequestException as error:
        raise OSError(str(error))
    return response.status_code, response.text, response.headers.get("Retry-After")


def _read_cache(cache_file, as_json):
    """Return the cached answer, or None when there is none or it is damaged."""
    if cache_file is None or not cache_file.exists():
        return None
    try:
        text = cache_file.read_text(encoding="utf-8")
        return json.loads(text) if as_json else text
    except (OSError, ValueError):
        # A download that was cut off mid-write. Throw it away and fetch again.
        cache_file.unlink(missing_ok=True)
        return None


def _write_cache(cache_file, text):
    """Write through a temporary file so a stopped run never leaves half a file."""
    cache_file.parent.mkdir(parents=True, exist_ok=True)
    temporary = cache_file.with_name(cache_file.name + ".part")
    temporary.write_text(text, encoding="utf-8")
    temporary.replace(cache_file)


def _wait_seconds(attempt, retry_after):
    try:
        asked = float(retry_after)
    except (TypeError, ValueError):
        asked = 0.0
    return min(MAX_WAIT_SECONDS, max(asked, 3 * (attempt + 1) ** 2))


def fetch(url, params=None, cache_file=None, as_json=True, headers=None, retries=4, timeout=60):
    """GET a URL, with an on-disk cache and polite retries.

    Returns parsed JSON (or text when as_json is False). Raises FetchError,
    a RuntimeError, with a readable message when the request fails for good:
    straight away for answers like 400 or 404 that will not change, and after
    `retries` attempts for busy servers, dropped connections and cut-off bodies.
    """
    cache_file = Path(cache_file) if cache_file is not None else None
    cached = _read_cache(cache_file, as_json)
    if cached is not None:
        return cached

    all_headers = {"User-Agent": USER_AGENT}
    all_headers.update(headers or {})
    last_error = "no attempt was made"
    for attempt in range(retries):
        try:
            status, text, retry_after = _http_get(url, params, all_headers, timeout)
        except OSError as error:
            last_error = str(error) or "no answer"
            time.sleep(_wait_seconds(attempt, None))
            continue
        if status in RETRY_STATUSES:
            last_error = f"HTTP {status}"
            time.sleep(_wait_seconds(attempt, retry_after))
            continue
        if status >= 400:
            raise FetchError(f"Could not fetch {url}: HTTP {status}: {text[:200].strip()}")
        try:
            result = json.loads(text) if as_json else text
        except ValueError:
            last_error = "the answer was not valid JSON (probably cut off)"
            time.sleep(_wait_seconds(attempt, None))
            continue
        if cache_file is not None:
            _write_cache(cache_file, text)
        return result
    raise FetchError(f"Could not fetch {url} after {retries} tries: {last_error}")


def forget_cached(cache_file):
    """Delete a cached answer that turned out to be useless, so it is fetched again."""
    Path(cache_file).unlink(missing_ok=True)
