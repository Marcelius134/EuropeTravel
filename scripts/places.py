"""City notes and places to visit, from Wikivoyage.

For each city the script fetches the English Wikivoyage article, checks that
the article really is about that city (its coordinates must be nearby), then
keeps the opening sentences and the "See" and "Do" listings that have a
position.

Wikivoyage text is licensed CC BY-SA 4.0, so the app credits it wherever it
is shown. https://en.wikivoyage.org
"""
import math
import re
import time

from .common import CACHE, COMPUTED, COUNTRY_NAMES, CURATED, fetch, load_json, save_json

API_URL = "https://en.wikivoyage.org/w/api.php"
# An article whose own coordinates are further than this from the city is about somewhere else.
MAX_ARTICLE_DISTANCE_KM = 40.0
# A listing further than this from the city centre is a day trip, not a place in the city.
MAX_PLACE_DISTANCE_KM = 25.0
PLACES_PER_CITY = 8
SUMMARY_MAX_CHARS = 320
DESCRIPTION_MAX_CHARS = 240
LISTING_TYPES = ("see", "do")

CATEGORY_WORDS = [
    ("museum", ("museum", "museo", "musee", "musée", "gallery", "galerie", "galleria")),
    ("beach", ("beach", "playa", "praia", "plage", "spiaggia", "strand", "plaj")),
    ("viewpoint", ("viewpoint", "view point", "lookout", "panorama", "observation", "belvedere", "mirador", "miradouro")),
    ("nature", ("park", "garden", "lake", "forest", "mountain", "island", "gorge", "waterfall", "trail", "nature reserve")),
    ("food", ("market", "brewery", "winery", "food hall")),
]


def distance_km(lat1, lon1, lat2, lon2):
    mean_lat = math.radians((lat1 + lat2) / 2)
    dx = (lon1 - lon2) * 111.32 * math.cos(mean_lat)
    dy = (lat1 - lat2) * 110.57
    return math.hypot(dx, dy)


# ---------- Reading wikitext ----------

def find_templates(wikitext, names):
    """Yield (name, body) for every {{name ...}} template, handling nested braces."""
    pattern = re.compile(r"\{\{\s*(" + "|".join(names) + r")\s*(?=[|}\n])", re.IGNORECASE)
    for match in pattern.finditer(wikitext):
        depth = 0
        index = match.start()
        while index < len(wikitext) - 1:
            pair = wikitext[index:index + 2]
            if pair == "{{":
                depth += 1
                index += 2
            elif pair == "}}":
                depth -= 1
                index += 2
                if depth == 0:
                    yield match.group(1).lower(), wikitext[match.end():index - 2]
                    break
            else:
                index += 1


def split_parameters(body):
    """Split a template body on the | characters that are not inside links or templates."""
    parts = []
    current = []
    depth = 0
    index = 0
    while index < len(body):
        pair = body[index:index + 2]
        if pair in ("{{", "[["):
            depth += 1
            current.append(pair)
            index += 2
        elif pair in ("}}", "]]"):
            depth = max(0, depth - 1)
            current.append(pair)
            index += 2
        elif body[index] == "|" and depth == 0:
            parts.append("".join(current))
            current = []
            index += 1
        else:
            current.append(body[index])
            index += 1
    parts.append("".join(current))
    return parts


def template_parameters(body):
    """Return (positional values, named values) of a template body."""
    positional = []
    named = {}
    for part in split_parameters(body):
        if "=" in part and re.match(r"^\s*[\w -]+\s*=", part):
            key, value = part.split("=", 1)
            named[key.strip().lower()] = value.strip()
        elif part.strip():
            positional.append(part.strip())
    return positional, named


def plain_text(wikitext):
    """Strip wiki markup down to readable text."""
    text = re.sub(r"<ref[^>]*>.*?</ref>|<ref[^>]*/>|<!--.*?-->", "", wikitext, flags=re.DOTALL)
    previous = None
    while previous != text:  # peel nested templates from the inside out
        previous = text
        text = re.sub(r"\{\{[^{}]*\}\}", "", text)
    text = re.sub(r"\[\[(?:File|Image):[^\]]*\]\]", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\[\[(?:[^\]|]*\|)?([^\]]*)\]\]", r"\1", text)
    text = re.sub(r"\[https?://\S+\s+([^\]]*)\]", r"\1", text)
    text = re.sub(r"\[https?://\S+\]", "", text)
    text = re.sub(r"'{2,}", "", text)
    text = re.sub(r"<[^>]+>", "", text)
    return re.sub(r"\s+", " ", text).strip()


def shorten(text, limit):
    """Cut text at the last sentence end that fits inside the limit."""
    if len(text) <= limit:
        return text
    cut = text[:limit]
    end = max(cut.rfind(". "), cut.rfind("! "), cut.rfind("? "))
    if end > limit * 0.4:
        return cut[:end + 1]
    return cut.rsplit(" ", 1)[0].rstrip(",;:") + "…"


def _number(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def article_position(wikitext):
    """The coordinates a Wikivoyage article gives for itself, or None."""
    for _, body in find_templates(wikitext, ["geo"]):
        positional, _ = template_parameters(body)
        if len(positional) >= 2:
            lat, lon = _number(positional[0]), _number(positional[1])
            if lat is not None and lon is not None:
                return lat, lon
    return None


def is_disambiguation(wikitext):
    return bool(re.search(r"\{\{\s*(disamb|disambiguation)\b", wikitext, re.IGNORECASE))


def guess_category(listing_type, name, description):
    text = (name + " " + description).lower()
    for category, words in CATEGORY_WORDS:
        if any(word in text for word in words):
            return category
    return "historic" if listing_type == "see" else "other"


def parse_listings(wikitext, city_lat, city_lon, limit=PLACES_PER_CITY):
    """Pick the See and Do listings that have a name and a position near the city."""
    places = []
    seen = set()
    for listing_type, body in find_templates(wikitext, LISTING_TYPES):
        _, named = template_parameters(body)
        name = plain_text(named.get("name", ""))
        lat, lon = _number(named.get("lat")), _number(named.get("long"))
        if not name or lat is None or lon is None or name.lower() in seen:
            continue
        if distance_km(lat, lon, city_lat, city_lon) > MAX_PLACE_DISTANCE_KM:
            continue
        description = shorten(plain_text(named.get("content", "")), DESCRIPTION_MAX_CHARS)
        seen.add(name.lower())
        places.append({
            "name": name,
            "category": guess_category(listing_type, name, description),
            "lat": round(lat, 5),
            "lon": round(lon, 5),
            "description": description,
        })
        if len(places) >= limit:
            break
    return places


def parse_article(payload, city_lat, city_lon):
    """Turn one API response into {"title", "summary", "places"}, or None if it is the wrong page."""
    pages = payload.get("query", {}).get("pages", [])
    if not pages or pages[0].get("missing"):
        return None
    page = pages[0]
    try:
        wikitext = page["revisions"][0]["slots"]["main"]["content"]
    except (KeyError, IndexError):
        return None
    if is_disambiguation(wikitext):
        return None
    position = article_position(wikitext)
    if position is None or distance_km(position[0], position[1], city_lat, city_lon) > MAX_ARTICLE_DISTANCE_KM:
        return None
    extract = re.sub(r"\s+", " ", page.get("extract") or "").strip()
    return {
        "title": page["title"],
        "summary": shorten(extract, SUMMARY_MAX_CHARS) if extract else None,
        "places": parse_listings(wikitext, city_lat, city_lon),
    }


# ---------- Downloading ----------

def fetch_article(city, country_name):
    """Try the plain city name, then 'Name (Country)'. Returns a parsed article or None."""
    for attempt, title in enumerate([city["name"], f"{city['name']} ({country_name})"]):
        payload = fetch(
            API_URL,
            params={
                "action": "query", "format": "json", "formatversion": 2, "redirects": 1,
                "titles": title, "prop": "extracts|revisions",
                "exintro": 1, "explaintext": 1, "rvprop": "content", "rvslots": "main",
            },
            cache_file=CACHE / "wikivoyage" / f"{city['id']}.{attempt}.json",
        )
        article = parse_article(payload, city["lat"], city["lon"])
        if article:
            return article
    return None


def build_places(pause_seconds=0.3):
    from . import merge

    cities = merge.build_cities()
    curated_places = load_json(CURATED / "places.json", {"places": {}})["places"]
    notes = load_json(COMPUTED / "city_notes.json", {})
    places = load_json(COMPUTED / "places.json", {})
    checked = set(load_json(CACHE / "wikivoyage" / "_checked.json", []))
    found = 0
    for number, city in enumerate(cities, start=1):
        if city["id"] in checked or city["id"] in curated_places:
            continue
        try:
            article = fetch_article(city, COUNTRY_NAMES[city["region_id"][:2]])
        except RuntimeError as error:
            print(f"places: {number}/{len(cities)} {city['name']} FAILED: {error}")
            continue
        checked.add(city["id"])
        if article:
            found += 1
            if article["summary"]:
                notes[city["id"]] = {"summary": article["summary"], "things_to_do": [], "title": article["title"]}
            if article["places"]:
                places[city["id"]] = article["places"]
            print(f"places: {number}/{len(cities)} {city['name']} ok ({len(article['places'])} places)")
        else:
            print(f"places: {number}/{len(cities)} {city['name']} has no matching article")
        if number % 25 == 0:
            _save(notes, places, checked)
        time.sleep(pause_seconds)
    _save(notes, places, checked)
    print(f"places: found articles for {found} more cities; {len(notes)} cities have notes in total")


def _save(notes, places, checked):
    save_json(COMPUTED / "city_notes.json", dict(sorted(notes.items())))
    save_json(COMPUTED / "places.json", dict(sorted(places.items())))
    save_json(CACHE / "wikivoyage" / "_checked.json", sorted(checked))
