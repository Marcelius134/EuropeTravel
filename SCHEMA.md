# Data schema

Three generated files feed the app. All of them are built by
`python -m scripts.build_data` from `data/computed/` (measured values) and
`data/curated/` (hand-written values).

## `data/regions.json`

One object per NUTS-2 region. The `id` matches the `id` property of the
polygons in `static/geo/nuts2.geojson`.

| Field | Type | Meaning |
|---|---|---|
| `id` | string | NUTS-2 code, for example `ITI1`. |
| `name` | string | Display name. English where curated, otherwise the Eurostat name. |
| `country` | string | NUTS country code (`EL` is Greece, `UK` is the United Kingdom). |
| `country_name` | string | Country name in English. |
| `centroid` | [lat, lon] | A point inside the region. |
| `area_km2` | number | Area from the simplified boundary. |
| `climate` | object or null | `temp_max_c` and `precip_mm`, 12 values each, January first. |
| `features` | object | `coast`, `nature`, `historic`, `crowd`. Each is 0 to 1 or null. |
| `summary` | string or null | One or two sentences. Null means the app writes one from the features. |
| `highlights` | [string] | Things people commonly do there. |
| `sources` | object | Where each value came from, per field. |

### Feature scales

Every feature is a number from 0 to 1, or null when it is unknown.

| Feature | 0 | 1 | How it is measured |
|---|---|---|---|
| `coast` | no sea border | island or mostly coastline | Share of the boundary lying on the Natural Earth coastline. |
| `nature` | flat and built-up | mountainous and wild | Share covered by mountain ranges, plus low settlement density. |
| `historic` | little heritage | very rich heritage | World Heritage sites and castles from Wikidata, ranked across regions. |
| `crowd` | quiet | busy | People living in towns over 15,000 per km², ranked across regions. |

Temperature and rainfall are not stored as features. The matcher derives them
from `climate` for the chosen month (or for June to August when no month is
chosen):

- temperature: 10 °C or colder is 0, 34 °C or hotter is 1. In thirds: cool is
  below 18 °C, mild is 18 to 26 °C, hot is above 26 °C.
- rainfall: 0 mm in the month is 0, 120 mm or more is 1. In thirds: dry is
  below 40 mm, some rain is 40 to 80 mm, rainy is above 80 mm.

### Sources

`sources` records one label per field:

| Label | Meaning |
|---|---|
| `natural-earth` | Computed from Natural Earth geometry. |
| `geonames` | Computed from the GeoNames city list. |
| `nasa-power`, `open-meteo` | Climate downloaded by the build script. |
| `wikidata` | Heritage counts downloaded by the build script. |
| `proxy` | Estimated from other measured values. |
| `curated-estimate` | Written by hand from general knowledge. Replace when measured data exists. |

## `data/cities.json`

| Field | Type | Meaning |
|---|---|---|
| `id` | string | Slug, for example `rome-it`. |
| `name` | string | City name. |
| `region_id` | string | The NUTS-2 region it belongs to. |
| `lat`, `lon` | number | Position. |
| `population` | number | From GeoNames. |
| `summary` | string or null | Short description. |
| `things_to_do` | [string] | Short suggestions. |
| `sources` | object | `position`, `text`. |

## `data/places.json`

| Field | Type | Meaning |
|---|---|---|
| `id` | string | Slug, unique across all places. |
| `city_id` | string | The city it belongs to. |
| `name` | string | Place name. |
| `category` | string | `historic`, `museum`, `beach`, `nature`, `viewpoint`, `food` or `other`. |
| `lat`, `lon` | number | Position of the pin. |
| `description` | string | One or two sentences. |
| `source` | string | `curated-estimate` or `wikivoyage`. |

## Matching

`matcher.py` turns the filters into a score per region.

1. Every value is on a 0 to 1 scale, cut into thirds: low, medium, high.
2. For one filter, the match is 100% when the region's value is in the wanted
   third. Outside it the match falls in a straight line, reaching 0% when the
   value is 0.2 away from the wanted third.
3. The region's score is the average match over the chosen filters.
4. A region with no value for a chosen filter gets no score. It is drawn
   with a dashed outline rather than counted as a poor match.

The page lights up every region whose score reaches the threshold (70% by
default).

### Best months

`matcher.score_by_month` repeats the same scoring twelve times for one region,
once per month. Only temperature and rainfall change between months, so the
region card shows the "Best months" bars only when one of those two filters is
chosen.

## What the browser keeps

Nothing personal is sent to the server. Two things are kept in the browser's
`localStorage`:

| Key | Value |
|---|---|
| `et-theme` | `"night"` or `"warm"` |
| `et-saved` | A list of `{ "kind": "region" or "city", "id", "name", "where" }`, newest first, at most 40 |
