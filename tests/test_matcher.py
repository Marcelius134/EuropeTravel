import pytest

import matcher


def make_region(**overrides):
    region = {
        "id": "XX00",
        "name": "Testland",
        "country_name": "Nowhere",
        "climate": {
            # January .. December
            "temp_max_c": [10, 12, 15, 18, 22, 28, 32, 32, 27, 21, 15, 11],
            "precip_mm": [90, 80, 60, 50, 40, 20, 5, 5, 30, 70, 100, 110],
        },
        "features": {"coast": 1.0, "nature": 0.5, "historic": 0.9, "crowd": 0.1},
    }
    region.update(overrides)
    return region


def test_value_inside_the_wanted_third_is_a_full_match():
    assert matcher.match_one(0.9, "high") == 1.0
    assert matcher.match_one(0.5, "medium") == 1.0
    assert matcher.match_one(0.0, "low") == 1.0


def test_match_falls_off_outside_the_wanted_third():
    just_outside = matcher.match_one(2 / 3 - 0.1, "high")
    assert just_outside == pytest.approx(0.5)
    assert matcher.match_one(0.1, "high") == 0.0


def test_summer_is_used_when_no_month_is_given():
    region = make_region()
    assert matcher.climate_value(region, "temperature") == pytest.approx((28 + 32 + 32) / 3)
    assert matcher.climate_value(region, "temperature", month=1) == 10


def test_temperature_and_rainfall_are_scaled_to_zero_one():
    region = make_region()
    assert matcher.feature_value(region, "temperature", month=1) == 0.0
    assert matcher.feature_value(region, "temperature", month=7) == pytest.approx((32 - 10) / 24)
    assert matcher.feature_value(region, "rainfall", month=12) == pytest.approx(110 / 120)


def test_score_is_the_average_of_the_filter_matches():
    region = make_region()
    result = matcher.score_region(region, {"coast": "high", "crowd": "high"})
    assert result["matches"] == {"coast": 100, "crowd": 0}
    assert result["score"] == 50


def test_month_changes_the_score():
    region = make_region()
    assert matcher.score_region(region, {"temperature": "high"}, month=7)["score"] == 100
    assert matcher.score_region(region, {"temperature": "high"}, month=1)["score"] == 0


def test_region_without_data_is_not_scored():
    region = make_region(climate=None)
    result = matcher.score_region(region, {"temperature": "high", "coast": "high"})
    assert result["score"] is None
    assert result["missing"] == ["temperature"]


def test_unknown_feature_value_is_not_scored():
    region = make_region(features={"coast": 1.0, "nature": 0.5, "historic": None, "crowd": 0.1})
    assert matcher.score_region(region, {"historic": "high"})["score"] is None


def test_results_are_ordered_best_first_with_unknown_last():
    hot = make_region(id="AA01")
    cold = make_region(id="AA02", climate={"temp_max_c": [5] * 12, "precip_mm": [50] * 12})
    unknown = make_region(id="AA03", climate=None)
    results = matcher.score_all([unknown, cold, hot], {"temperature": "high"})
    assert [r["id"] for r in results] == ["AA01", "AA02", "AA03"]
    assert "_depth" not in results[0]


def test_equal_scores_put_the_firmer_match_first():
    barely = make_region(id="AA01", features={"coast": 0.7, "nature": 0, "historic": 0, "crowd": 0})
    firmly = make_region(id="AA02", features={"coast": 1.0, "nature": 0, "historic": 0, "crowd": 0})
    results = matcher.score_all([barely, firmly], {"coast": "high"})
    assert [r["id"] for r in results] == ["AA02", "AA01"]


@pytest.mark.parametrize(
    "filters, month",
    [({"weather": "high"}, None), ({"coast": "very"}, None), ({"coast": "high"}, 13), ({"coast": "high"}, "7"), ("coast", None)],
)
def test_bad_requests_are_rejected(filters, month):
    with pytest.raises(matcher.FilterError):
        matcher.score_all([make_region()], filters, month)


def test_empty_level_is_ignored():
    filters, _ = matcher.validate({"coast": None, "crowd": "low"}, None)
    assert filters == {"crowd": "low"}


def test_level_names():
    assert matcher.level_of(0.1) == "low"
    assert matcher.level_of(0.5) == "medium"
    assert matcher.level_of(0.9) == "high"
    assert matcher.level_of(None) is None


def test_generated_description_mentions_what_is_known():
    text = matcher.describe(make_region())
    assert "Nowhere" in text and "coastline" in text and "few crowds" in text
    assert "31 °C" in text
