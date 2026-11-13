import pytest

from app import create_app


@pytest.fixture()
def client():
    app = create_app()
    app.config.update(TESTING=True)
    return app.test_client()


def test_index_page_loads(client):
    response = client.get("/")
    assert response.status_code == 200
    assert b"EuropeTravel" in response.data


def test_health(client):
    assert client.get("/api/health").get_json() == {"status": "ok"}
