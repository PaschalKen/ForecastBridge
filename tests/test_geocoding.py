import pytest
import requests

from app import geocoding
from app.geocoding import GeocodingClient
from app.location import Location, place_id_from

# Hand-made copies of what Open-Meteo's geocoding API returns, so tests never need the internet
BRIGHTON_UK = {
    "id": 2654710, "name": "Brighton", "latitude": 50.82838, "longitude": -0.13947,
    "timezone": "Europe/London", "country": "United Kingdom", "admin1": "England",
}
BRIGHTON_US = {
    "id": 5414941, "name": "Brighton", "latitude": 39.98526, "longitude": -104.82053,
    "timezone": "America/Denver", "country": "United States", "admin1": "Colorado",
}


class FakeResponse:
    def __init__(self, data, status_code=200):
        self.data = data
        self.status_code = status_code

    def json(self):
        return self.data

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"{self.status_code} error")


def fake_requests(monkeypatch, response):
    """Make geocoding's requests.get return `response`, and record each call's URL and params."""
    calls = []

    def fake_get(url, params, timeout):
        calls.append({"url": url, "params": params})
        return response

    monkeypatch.setattr(geocoding.requests, "get", fake_get)
    return calls


# --- to_location ---------------------------------------------------------------

def test_to_location_builds_a_place_name_label_and_timezone():
    location = GeocodingClient.to_location(BRIGHTON_UK)

    assert location == Location(
        name="place-2654710",
        latitude=50.82838,
        longitude=-0.13947,
        label="Brighton, England, United Kingdom",
        timezone="Europe/London",
    )


def test_to_location_skips_a_missing_region():
    result = {**BRIGHTON_UK, "admin1": None}

    assert GeocodingClient.to_location(result).label == "Brighton, United Kingdom"


def test_to_location_does_not_repeat_a_region_with_the_same_name():
    singapore = {"id": 1880252, "name": "Singapore", "latitude": 1.29, "longitude": 103.85,
                 "timezone": "Asia/Singapore", "country": "Singapore", "admin1": "Singapore"}

    assert GeocodingClient.to_location(singapore).label == "Singapore"


# --- search --------------------------------------------------------------------

def test_search_returns_matching_places_in_order(monkeypatch):
    calls = fake_requests(monkeypatch, FakeResponse({"results": [BRIGHTON_UK, BRIGHTON_US]}))

    places = GeocodingClient(url="https://geo.test/v1").search("brighton")

    assert [p.label for p in places] == ["Brighton, England, United Kingdom", "Brighton, Colorado, United States"]
    assert calls[0]["url"] == "https://geo.test/v1/search"
    assert calls[0]["params"]["name"] == "brighton"


def test_search_with_no_matches_returns_empty_list(monkeypatch):
    # With no matches, Open-Meteo leaves out the "results" key entirely
    fake_requests(monkeypatch, FakeResponse({"generationtime_ms": 0.2}))

    assert GeocodingClient().search("zzqqxx") == []


def test_search_raises_when_the_service_fails(monkeypatch):
    fake_requests(monkeypatch, FakeResponse({}, status_code=500))

    with pytest.raises(requests.HTTPError):
        GeocodingClient().search("brighton")


# --- get -----------------------------------------------------------------------

def test_get_returns_the_place(monkeypatch):
    calls = fake_requests(monkeypatch, FakeResponse(BRIGHTON_UK))

    place = GeocodingClient(url="https://geo.test/v1").get(2654710)

    assert place.name == "place-2654710"
    assert calls[0]["url"] == "https://geo.test/v1/get"
    assert calls[0]["params"] == {"id": 2654710}


def test_get_unknown_id_returns_none(monkeypatch):
    # Open-Meteo answers an unknown id with 400 {"reason": "Location ID not found.", "error": true}
    fake_requests(monkeypatch, FakeResponse({"error": True}, status_code=400))

    assert GeocodingClient().get(999999999) is None


def test_get_remembers_places_so_repeat_lookups_skip_the_network(monkeypatch):
    calls = fake_requests(monkeypatch, FakeResponse(BRIGHTON_UK))
    client = GeocodingClient()

    client.get(2654710)
    client.get(2654710)

    assert len(calls) == 1


# --- Location helpers ----------------------------------------------------------

def test_featured_city_label_defaults_to_its_name_in_title_case():
    assert Location.get_location("london").label == "London"
    assert Location.get_location("london").timezone == "Europe/London"


def test_place_id_from_accepts_place_names_and_bare_ids():
    assert place_id_from("place-2654710") == 2654710
    assert place_id_from("2654710") == 2654710


def test_place_id_from_returns_none_for_anything_else():
    assert place_id_from("paris") is None
    assert place_id_from("place-abc") is None
