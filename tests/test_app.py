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
