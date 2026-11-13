"""Tests for the pure functions in scripts/. Nothing here touches the network."""
import pytest

from scripts import climate, heritage, merge
from scripts.cities import pick_main_cities
from scripts.common import percentile_ranks, slugify
from scripts.geometry import coast_score


def test_slugify_handles_accents_and_punctuation():
    assert slugify("Irákleion") == "irakleion"
    assert slugify("Saint-Malo") == "saint-malo"
    assert slugify("Provence-Alpes-Côte d’Azur") == "provence-alpes-cote-dazur"


def test_percentile_ranks_spread_from_zero_to_one():
    ranks = percentile_ranks({"a": 10, "b": 30, "c": 20, "d": None})
    assert ranks == {"a": 0.0, "b": 1.0, "c": 0.5, "d": None}


def test_percentile_ranks_share_a_rank_on_ties():
    ranks = percentile_ranks({"a": 5, "b": 5, "c": 9})
    assert ranks["a"] == ranks["b"] == 0.25
    assert ranks["c"] == 1.0


def test_coast_score_is_full_at_half_coastline():
    assert coast_score(0.0) == 0.0
    assert coast_score(0.25) == 0.5
    assert coast_score(0.8) == 1.0


def test_parse_nasa_power():
    months = climate.MONTH_KEYS
    payload = {
        "properties": {
            "parameter": {
                "T2M_MAX": {**{key: 10.0 + index for index, key in enumerate(months)}, "ANN": 15.5},
                "PRECTOTCORR": {**{key: 2.0 for key in months}, "ANN": 2.0},
            }
        }
    }
    result = climate.parse_power(payload)
    assert result["source"] == "nasa-power"
    assert result["temp_max_c"][0] == 10.0 and result["temp_max_c"][11] == 21.0
    assert result["precip_mm"][0] == 62  # 2 mm a day over 31 days
    assert result["precip_mm"][3] == 60


def test_parse_nasa_power_rejects_missing_values():
    months = climate.MONTH_KEYS
    payload = {
        "properties": {
            "parameter": {
                "T2M_MAX": {key: -999.0 for key in months},
                "PRECTOTCORR": {key: 1.0 for key in months},
            }
        }
    }
    with pytest.raises(ValueError):
        climate.parse_power(payload)


def test_parse_open_meteo_averages_over_years():
    payload = {
        "daily": {
            "time": ["2021-01-01", "2021-01-02", "2022-01-01"]
            + [f"2021-{month:02d}-15" for month in range(2, 13)],
            "temperature_2m_max": [4.0, 6.0, 8.0] + [20.0] * 11,
            "precipitation_sum": [10.0, 0.0, 30.0] + [None] * 11,
        }
    }
    result = climate.parse_open_meteo(payload)
    assert result["source"] == "open-meteo"
    assert result["temp_max_c"][0] == 6.0
    assert result["precip_mm"][0] == 20  # 40 mm over two years
    assert result["temp_max_c"][6] == 20.0


def test_parse_wikidata_points_keeps_one_point_per_item():
    payload = {
        "results": {
            "bindings": [
                {"item": {"value": "Q1"}, "coord": {"value": "Point(12.4922 41.8902)"}},
                {"item": {"value": "Q1"}, "coord": {"value": "Point(12.5 41.9)"}},
                {"item": {"value": "Q2"}, "coord": {"value": "Point(-3.7 40.4)"}},
                {"item": {"value": "Q3"}, "coord": {"value": "not a point"}},
            ]
        }
    }
    assert heritage.parse_points(payload) == [(12.4922, 41.8902), (-3.7, 40.4)]


def test_heritage_score_weighs_world_heritage_above_castles():
    assert heritage.heritage_score(1, 0) == heritage.heritage_score(0, 25)


def test_nature_proxy_rewards_mountains_and_quiet():
    wild = merge.nature_proxy(mountain_share=0.9, crowd=0.0)
    city = merge.nature_proxy(mountain_share=0.0, crowd=1.0)
    assert wild == 1.0
    assert city == 0.0


GEOMETRY = {"centroid": [40.0, 10.0], "area_km2": 1000.0, "coast": 0.4, "coast_share": 0.2, "mountain_share": 0.3}


def test_merge_region_prefers_measured_climate_over_estimates():
    curated = {"climate": {"temp_max_c": [1] * 12, "precip_mm": [1] * 12}, "features": {"historic": 0.9}}
    measured = {"temp_max_c": [20] * 12, "precip_mm": [50] * 12, "source": "nasa-power"}
    region = merge.merge_region("ITI1", "Toscana", GEOMETRY, {"crowd": 0.5}, measured, None, curated)
    assert region["climate"]["temp_max_c"][0] == 20
    assert region["sources"]["climate"] == "nasa-power"
    assert region["features"]["historic"] == 0.9
    assert region["sources"]["historic"] == "curated-estimate"


def test_merge_region_without_any_extra_data():
    region = merge.merge_region("ITI1", "Toscana", GEOMETRY, {"crowd": 0.5}, None, None, None)
    assert region["name"] == "Toscana"
    assert region["country_name"] == "Italy"
    assert region["climate"] is None and region["sources"]["climate"] is None
    assert region["features"]["historic"] is None
    assert region["sources"]["nature"] == "proxy"
    assert region["sources"]["crowd"] == "geonames"


def test_merge_region_uses_wikidata_when_nothing_is_curated():
    heritage_entry = {"world_heritage_sites": 3, "castles": 10, "historic": 0.8}
    region = merge.merge_region("ITI1", "Toscana", GEOMETRY, {"crowd": 0.5}, None, heritage_entry, None)
    assert region["features"]["historic"] == 0.8
    assert region["sources"]["historic"] == "wikidata"


def city(name, population, lat, lon):
    return {"name": name, "population": population, "lat": lat, "lon": lon}


def test_pick_main_cities_skips_districts_of_a_bigger_city():
    cities = [
        city("Innsbruck", 132000, 47.262, 11.394),
        city("Pradl", 30000, 47.262, 11.410),  # about 1 km from the centre
        city("Kufstein", 19000, 47.583, 12.167),
    ]
    assert [c["name"] for c in pick_main_cities(cities)] == ["Innsbruck", "Kufstein"]


def test_pick_main_cities_always_keeps_the_named_ones():
    cities = [city(f"Town {n}", 100000 - n, 40 + n, 10.0) for n in range(6)] + [city("Lagos", 20000, 37.1, -8.67)]
    picked = pick_main_cities(cities, always={"Lagos"})
    assert len(picked) == 5
    assert picked[-1]["name"] == "Lagos"


def test_merge_cities_uses_curated_names_and_notes():
    top = {"ES61": [city("Sevilla", 686741, 37.38, -5.97), city("Málaga", 578460, 36.72, -4.42)]}
    curated = [{
        "region_id": "ES61", "name": "Seville", "geonames_name": "Sevilla", "lat": 37.39, "lon": -5.98,
        "summary": "Hot.", "things_to_do": ["Alcazar"],
    }]
    notes = {"malaga-es": {"summary": "A port city.", "things_to_do": ["Picasso Museum"]}}
    cities = merge.merge_cities(top, curated, notes)
    assert [c["id"] for c in cities] == ["seville-es", "malaga-es"]
    assert cities[0]["summary"] == "Hot." and cities[0]["sources"]["text"] == "curated-estimate"
    assert cities[0]["lat"] == 37.38  # the GeoNames position wins when the city is listed
    assert cities[1]["summary"] == "A port city." and cities[1]["sources"]["text"] == "wikivoyage"


def test_merge_cities_adds_a_curated_city_missing_from_geonames():
    curated = [{
        "region_id": "PT15", "name": "Sagres", "geonames_name": "Sagres", "lat": 37.0, "lon": -8.94,
        "summary": "Wind and cliffs.", "things_to_do": [],
    }]
    cities = merge.merge_cities({"PT15": []}, curated)
    assert cities[0]["id"] == "sagres-pt"
    assert cities[0]["population"] is None
    assert cities[0]["sources"]["position"] == "curated-estimate"


# ---------- Wikivoyage parsing ----------

from scripts import places  # noqa: E402

BARI_WIKITEXT = """{{pagebanner|Bari banner.jpg}}
'''Bari''' is the capital of [[Apulia]] in [[Italy]].<ref>source</ref>

==See==
* {{see
| name=Basilica di San Nicola | alt= | url=http://www.basilicasannicola.it/ | email=
| address=Largo Abate Elia | lat=41.1302 | long=16.8704 | directions=
| phone= | hours=07:00-20:30 | price=Free
| content=A [[Romanesque architecture|Romanesque]] church holding the relics of '''Saint Nicholas'''. Very busy in May.
}}
* {{see | name=Museo Archeologico | lat=41.1295 | long=16.8660 | content=Finds from {{convert|2000|year}} of history.}}
* {{see | name=No position here | content=Skipped because it has no coordinates.}}
* {{see | name=Castel del Monte | lat=41.0847 | long=16.2709 | content=A castle far outside the city.}}

==Do==
* {{do | name=Pane e Pomodoro | lat=41.1175 | long=16.8870 | content=The city beach.}}

==Eat==
* {{eat | name=Some trattoria | lat=41.12 | long=16.87 | content=Not collected.}}

{{geo|41.1253|16.8667}}
{{IsPartOf|Apulia}}
"""


def test_plain_text_strips_wiki_markup():
    text = places.plain_text("A [[Romanesque architecture|Romanesque]] church in '''Bari'''{{citation needed}}.<ref>x</ref>")
    assert text == "A Romanesque church in Bari."


def test_split_parameters_ignores_pipes_inside_links():
    assert places.split_parameters("name=A|content=See [[B|b]] and {{c|d}}|lat=1") == [
        "name=A", "content=See [[B|b]] and {{c|d}}", "lat=1",
    ]


def test_article_position_reads_the_geo_template():
    assert places.article_position(BARI_WIKITEXT) == (41.1253, 16.8667)
    assert places.article_position("no template here") is None


def test_parse_listings_keeps_see_and_do_with_a_nearby_position():
    found = places.parse_listings(BARI_WIKITEXT, 41.1177, 16.8512)
    assert [place["name"] for place in found] == ["Basilica di San Nicola", "Museo Archeologico", "Pane e Pomodoro"]
    basilica, museum, beach = found
    assert basilica["category"] == "historic"
    assert basilica["description"].startswith("A Romanesque church holding the relics of Saint Nicholas.")
    assert museum["category"] == "museum"
    assert museum["description"] == "Finds from of history."
    assert beach["category"] == "beach"
    assert (beach["lat"], beach["lon"]) == (41.1175, 16.887)


def wikivoyage_payload(wikitext, extract="Bari is a port city. It faces the Adriatic."):
    return {"query": {"pages": [{
        "title": "Bari", "extract": extract,
        "revisions": [{"slots": {"main": {"content": wikitext}}}],
    }]}}


def test_parse_article_accepts_the_right_city():
    article = places.parse_article(wikivoyage_payload(BARI_WIKITEXT), 41.1177, 16.8512)
    assert article["title"] == "Bari"
    assert article["summary"] == "Bari is a port city. It faces the Adriatic."
    assert len(article["places"]) == 3


def test_parse_article_rejects_a_same_named_city_elsewhere():
    # Lagos in Portugal must not pick up the article about Lagos in Nigeria.
    nigeria = "'''Lagos''' is the largest city in Nigeria.\n{{geo|6.45|3.39}}"
    assert places.parse_article(wikivoyage_payload(nigeria), 37.10, -8.67) is None


def test_parse_article_rejects_disambiguation_and_missing_pages():
    assert places.parse_article(wikivoyage_payload("{{disamb}}\n* [[Bergen (Norway)]]"), 60.39, 5.32) is None
    assert places.parse_article({"query": {"pages": [{"title": "Nowhere", "missing": True}]}}, 0, 0) is None
    assert places.parse_article({}, 0, 0) is None


def test_shorten_cuts_at_a_sentence_end():
    text = "First sentence here. Second sentence is quite a bit longer than the first one."
    assert places.shorten(text, 40) == "First sentence here."
    assert places.shorten("Short.", 40) == "Short."


def test_merge_places_prefers_hand_written_places():
    cities = [{"id": "bari-it"}, {"id": "lecce-it"}]
    curated = {"bari-it": [{"name": "Old Town", "category": "historic", "lat": 41.1, "lon": 16.8, "description": "x"}]}
    fetched = {
        "bari-it": [{"name": "Ignored", "category": "other", "lat": 41.1, "lon": 16.8, "description": ""}],
        "lecce-it": [{"name": "Duomo", "category": "historic", "lat": 40.35, "lon": 18.17, "description": "y"}],
    }
    result = merge.merge_places(cities, curated, fetched)
    assert [(p["id"], p["source"]) for p in result] == [
        ("bari-it-old-town", "curated-estimate"), ("lecce-it-duomo", "wikivoyage"),
    ]


def test_merge_places_rejects_an_unknown_city():
    with pytest.raises(RuntimeError):
        merge.merge_places([{"id": "bari-it"}], {"atlantis-xx": []}, {})


def test_fill_empty_holes_keeps_holes_that_hold_another_region():
    from shapely.geometry import Polygon

    from scripts.geometry import fill_empty_holes

    outer = [(0, 0), (10, 0), (10, 10), (0, 10)]
    city_hole = [(1, 1), (3, 1), (3, 3), (1, 3)]
    empty_hole = [(6, 6), (8, 6), (8, 8), (6, 8)]
    shapes = {
        "AA01": Polygon(outer, [city_hole, empty_hole]),
        "AA02": Polygon(city_hole),
    }
    filled = fill_empty_holes(shapes)
    assert len(filled["AA01"].interiors) == 1
    assert filled["AA01"].contains(Polygon(empty_hole).representative_point())
    assert not filled["AA01"].contains(Polygon(city_hole).representative_point())
