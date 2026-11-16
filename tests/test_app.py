import pytest

from app import create_app


@pytest.fixture(scope="module")
def client():
    app = create_app()
    app.config.update(TESTING=True)
    return app.test_client()


def test_index_page_loads(client):
    response = client.get("/")
    assert response.status_code == 200
    assert b"EuropeTravel" in response.data


def test_index_page_offers_both_themes(client):
    page = client.get("/").data
    assert b'data-theme-choice="night"' in page
    assert b'data-theme-choice="warm"' in page


def test_health(client):
    body = client.get("/api/health").get_json()
    assert body["status"] == "ok"
    assert body["regions"] > 300


def test_meta_lists_the_filters_in_panel_order(client):
    body = client.get("/api/meta").get_json()
    assert [f["name"] for f in body["filters"]] == [
        "temperature", "rainfall", "coast", "nature", "historic", "crowd",
    ]
    assert len(body["months"]) == 12
    assert body["default_threshold"] == 70


def test_match_scores_every_region(client):
    response = client.post("/api/match", json={"filters": {"coast": "high"}})
    results = response.get_json()["results"]
    assert response.status_code == 200
    assert len(results) > 300
    scores = [r["score"] for r in results if r["score"] is not None]
    assert scores == sorted(scores, reverse=True)
    assert results[0]["score"] == 100


def test_match_with_no_filters_scores_nothing(client):
    results = client.post("/api/match", json={"filters": {}}).get_json()["results"]
    assert all(r["score"] is None for r in results)


def test_match_rejects_unknown_filter(client):
    response = client.post("/api/match", json={"filters": {"budget": "low"}})
    assert response.status_code == 400
    assert "budget" in response.get_json()["error"]


def test_match_rejects_a_body_that_is_not_json(client):
    assert client.post("/api/match", data="hello").status_code == 400


def test_region_detail(client):
    body = client.get("/api/regions/ITI1").get_json()
    assert body["name"] == "Tuscany"
    assert body["country_name"] == "Italy"
    assert body["levels"]["historic"]["level"] == "high"
    assert len(body["climate"]["temp_max_c"]) == 12


def test_region_detail_uses_the_month(client):
    july = client.get("/api/regions/ITI1?month=7").get_json()
    january = client.get("/api/regions/ITI1?month=1").get_json()
    assert july["levels"]["temperature"]["level"] == "high"
    assert january["levels"]["temperature"]["level"] == "low"


def test_region_without_a_written_summary_gets_a_generated_one(client):
    regions = client.get("/api/regions").get_json()["regions"]
    assert len(regions) > 300
    body = client.get("/api/regions/AL01").get_json()
    assert body["summary"]
    assert body["summary_is_generated"] is True


def test_unknown_region_is_a_404(client):
    response = client.get("/api/regions/ZZ99")
    assert response.status_code == 404
    assert "ZZ99" in response.get_json()["error"]


def test_bad_month_is_rejected(client):
    assert client.get("/api/regions/ITI1?month=13").status_code == 400


def test_region_detail_lists_its_cities(client):
    cities = client.get("/api/regions/ITI4").get_json()["cities"]
    assert "Rome" in [city["name"] for city in cities]
    rome = next(city for city in cities if city["name"] == "Rome")
    assert rome["has_notes"] is True
    assert rome["region_id"] == "ITI4"


def test_city_list_is_brief(client):
    cities = client.get("/api/cities").get_json()["cities"]
    assert len(cities) > 1000
    assert set(cities[0]) == {"id", "name", "region_id", "lat", "lon", "population", "has_notes"}


def test_city_detail(client):
    body = client.get("/api/cities/bari-it").get_json()
    assert body["name"] == "Bari"
    assert body["region_name"] == "Apulia"
    assert body["country_name"] == "Italy"
    assert body["summary"]
    assert len(body["things_to_do"]) >= 3


def test_unknown_city_is_a_404(client):
    assert client.get("/api/cities/atlantis-xx").status_code == 404


def test_city_detail_includes_its_places(client):
    places = client.get("/api/cities/rome-it").get_json()["places"]
    assert "Colosseum" in [place["name"] for place in places]
    colosseum = next(place for place in places if place["name"] == "Colosseum")
    assert colosseum["category"] == "historic"
    assert abs(colosseum["lat"] - 41.89) < 0.01 and abs(colosseum["lon"] - 12.49) < 0.01


def test_city_without_places_returns_an_empty_list(client):
    assert client.get("/api/cities/telfs-at").get_json()["places"] == []


def test_unknown_api_address_answers_in_json(client):
    response = client.get("/api/nothing-here")
    assert response.status_code == 404
    assert "no API address" in response.get_json()["error"]


def test_wrong_method_answers_in_json(client):
    response = client.get("/api/match")
    assert response.status_code == 405
    assert "does not accept GET" in response.get_json()["error"]


def test_unknown_page_is_a_plain_404(client):
    response = client.get("/nothing-here")
    assert response.status_code == 404
    assert response.get_json(silent=True) is None


def test_a_damaged_data_file_is_reported_clearly(tmp_path):
    from store import Store

    (tmp_path / "regions.json").write_text("[{", encoding="utf-8")
    with pytest.raises(RuntimeError, match="is damaged"):
        Store(tmp_path)


def test_the_app_starts_without_any_data(tmp_path):
    from app import create_app
    from store import Store

    empty = create_app(Store(tmp_path)).test_client()
    assert empty.get("/api/meta").get_json()["region_count"] == 0
    assert empty.post("/api/match", json={"filters": {"coast": "high"}}).get_json() == {"results": []}


def test_region_year_scores_every_month(client):
    response = client.post("/api/regions/ES61/year", json={"filters": {"temperature": "high"}})
    body = response.get_json()
    assert response.status_code == 200
    assert body["id"] == "ES61" and body["seasonal"] is True
    assert len(body["scores"]) == 12
    assert body["scores"][6] > body["scores"][0]  # Andalusia is hotter in July than in January


def test_region_year_reports_bad_requests(client):
    assert client.post("/api/regions/ZZ99/year", json={"filters": {}}).status_code == 404
    assert client.post("/api/regions/ES61/year", json={"filters": {"weather": "high"}}).status_code == 400
    assert client.post("/api/regions/ES61/year", data="nonsense").status_code == 400
