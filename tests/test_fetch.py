"""Tests for the download helper. The network call is replaced, so nothing leaves the machine."""
import json

import pytest

from scripts import climate, common, places


class FakeServer:
    """Stands in for common._http_get and answers from a prepared list."""

    def __init__(self, answers):
        self.answers = list(answers)
        self.calls = 0

    def __call__(self, url, params, headers, timeout):
        self.calls += 1
        answer = self.answers.pop(0)
        if isinstance(answer, Exception):
            raise answer
        status, text = answer[0], answer[1]
        retry_after = answer[2] if len(answer) > 2 else None
        return status, text, retry_after


@pytest.fixture
def waits(monkeypatch):
    """Record the waits between tries instead of sleeping."""
    recorded = []
    monkeypatch.setattr(common.time, "sleep", recorded.append)
    return recorded


def use(monkeypatch, *answers):
    server = FakeServer(answers)
    monkeypatch.setattr(common, "_http_get", server)
    return server


def test_fetch_returns_parsed_json_and_writes_the_cache(monkeypatch, tmp_path, waits):
    server = use(monkeypatch, (200, '{"ok": true}'))
    cache_file = tmp_path / "nested" / "answer.json"
    assert common.fetch("https://example.org", cache_file=cache_file) == {"ok": True}
    assert json.loads(cache_file.read_text()) == {"ok": True}
    assert not list(tmp_path.rglob("*.part"))
    assert server.calls == 1 and waits == []


def test_fetch_uses_the_cache_without_asking_again(monkeypatch, tmp_path, waits):
    cache_file = tmp_path / "answer.json"
    cache_file.write_text('{"from": "cache"}')
    server = use(monkeypatch)
    assert common.fetch("https://example.org", cache_file=cache_file) == {"from": "cache"}
    assert server.calls == 0


def test_fetch_replaces_a_damaged_cache_file(monkeypatch, tmp_path, waits):
    cache_file = tmp_path / "answer.json"
    cache_file.write_text('{"cut off')
    use(monkeypatch, (200, '{"fresh": 1}'))
    assert common.fetch("https://example.org", cache_file=cache_file) == {"fresh": 1}
    assert json.loads(cache_file.read_text()) == {"fresh": 1}


def test_fetch_retries_a_busy_server_then_succeeds(monkeypatch, waits):
    server = use(monkeypatch, (503, "busy"), (429, "slow down", "7"), (200, "[1, 2]"))
    assert common.fetch("https://example.org") == [1, 2]
    assert server.calls == 3
    assert waits == [3, 12]  # the second wait is the larger of our own 12 s and the server's 7 s


def test_fetch_waits_as_long_as_the_server_asks_but_not_forever(monkeypatch, waits):
    use(monkeypatch, (429, "", "40"), (429, "", "100000"), (200, "{}"))
    common.fetch("https://example.org")
    assert waits == [40, common.MAX_WAIT_SECONDS]


def test_fetch_retries_when_the_connection_drops(monkeypatch, waits):
    server = use(monkeypatch, OSError("connection reset"), (200, "{}"))
    assert common.fetch("https://example.org") == {}
    assert server.calls == 2


def test_fetch_retries_a_cut_off_body_and_does_not_cache_it(monkeypatch, tmp_path, waits):
    cache_file = tmp_path / "answer.json"
    use(monkeypatch, (200, '{"half":'), (200, '{"whole": 1}'))
    assert common.fetch("https://example.org", cache_file=cache_file) == {"whole": 1}
    assert json.loads(cache_file.read_text()) == {"whole": 1}


def test_fetch_gives_up_at_once_on_an_answer_that_will_not_change(monkeypatch, tmp_path, waits):
    cache_file = tmp_path / "answer.json"
    server = use(monkeypatch, (404, "no such page"))
    with pytest.raises(common.FetchError, match="HTTP 404"):
        common.fetch("https://example.org", cache_file=cache_file)
    assert server.calls == 1 and waits == []
    assert not cache_file.exists()


def test_fetch_gives_up_after_the_last_try_with_the_reason(monkeypatch, waits):
    server = use(monkeypatch, (503, ""), (503, ""), OSError("timed out"))
    with pytest.raises(common.FetchError, match="after 3 tries: timed out"):
        common.fetch("https://example.org", retries=3)
    assert server.calls == 3


def test_fetch_can_return_plain_text(monkeypatch, waits):
    use(monkeypatch, (200, "not json at all"))
    assert common.fetch("https://example.org", as_json=False) == "not json at all"


def test_fetch_error_is_a_runtime_error_so_the_steps_catch_it():
    assert issubclass(common.FetchError, RuntimeError)


# ---------- The steps' own handling of bad answers ----------

POWER_OK = {
    "properties": {
        "parameter": {
            "T2M_MAX": {key: 20.0 for key in climate.MONTH_KEYS},
            "PRECTOTCORR": {key: 2.0 for key in climate.MONTH_KEYS},
        }
    }
}


def test_climate_falls_back_to_open_meteo_when_power_is_unusable(monkeypatch, tmp_path, waits):
    monkeypatch.setattr(climate, "CACHE", tmp_path)
    days = [f"2021-{month:02d}-15" for month in range(1, 13)]
    open_meteo = {"daily": {"time": days, "temperature_2m_max": [10.0] * 12, "precipitation_sum": [3.0] * 12}}
    use(monkeypatch, (200, json.dumps({"properties": {"parameter": {}}})), (200, json.dumps(open_meteo)))
    result = climate.fetch_region_climate("XX00", 50.0, 10.0)
    assert result["source"] == "open-meteo"
    # The useless NASA POWER answer is not kept, so a later run asks again.
    assert not (tmp_path / "climate" / "XX00.power.json").exists()


def test_climate_reports_both_sources_when_neither_works(monkeypatch, tmp_path, waits):
    monkeypatch.setattr(climate, "CACHE", tmp_path)
    use(monkeypatch, (422, "bad point"), (400, '{"error": true}'))
    with pytest.raises(RuntimeError, match="HTTP 400"):
        climate.fetch_region_climate("XX00", 50.0, 10.0)


def test_climate_rejects_impossible_numbers():
    payload = json.loads(json.dumps(POWER_OK))
    payload["properties"]["parameter"]["T2M_MAX"]["JUL"] = 90.0
    with pytest.raises(ValueError, match="out of range"):
        climate.parse_power(payload)
    assert climate.parse_power(POWER_OK)["precip_mm"][0] == 62


def test_build_climate_stops_when_the_services_are_down(monkeypatch, tmp_path, waits):
    monkeypatch.setattr(climate, "CACHE", tmp_path / "cache")
    monkeypatch.setattr(climate, "COMPUTED", tmp_path)
    regions = {f"XX{number:02d}": {"centroid": [50.0, 10.0]} for number in range(20)}
    (tmp_path / "geometry.json").write_text(json.dumps(regions))
    monkeypatch.setattr(common, "_http_get", lambda *args: (_ for _ in ()).throw(OSError("offline")))
    with pytest.raises(RuntimeError, match="one after another"):
        climate.build_climate(pause_seconds=0)
    assert json.loads((tmp_path / "climate.json").read_text()) == {}


def test_wikivoyage_refusal_is_not_cached_or_mistaken_for_a_missing_article(monkeypatch, tmp_path, waits):
    monkeypatch.setattr(places, "CACHE", tmp_path)
    use(monkeypatch, (200, json.dumps({"error": {"code": "maxlag", "info": "Waiting for a database server"}})))
    city = {"id": "xx-testville", "name": "Testville", "lat": 50.0, "lon": 10.0}
    with pytest.raises(RuntimeError, match="Waiting for a database server"):
        places.fetch_article(city, "Testland")
    assert not list(tmp_path.rglob("*.json"))
