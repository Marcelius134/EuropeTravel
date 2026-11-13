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
