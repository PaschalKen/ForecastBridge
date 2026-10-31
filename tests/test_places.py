"""API tests for searching places and getting forecasts for searched places."""
import pytest
import requests
from fastapi.testclient import TestClient

from app.controllers.forecast_controller import ForecastController, get_controller
from app.geocoding import GeocodingClient, get_geocoding
from app.main import app
from tests.test_geocoding import BRIGHTON_UK, BRIGHTON_US
from tests.test_main import FakeStore, FakeWeatherClient

client = TestClient(app)


class FakeGeocodingClient:
    """Knows two Brightons, counts searches, never touches the internet."""

    def __init__(self):
        self.searches = 0
        self.places = {
            2654710: GeocodingClient.to_location(BRIGHTON_UK),
            5414941: GeocodingClient.to_location(BRIGHTON_US),
        }

    def search(self, query, count=5):
        self.searches += 1
        return list(self.places.values()) if "brighton".startswith(query.lower()) else []

    def get(self, place_id):
        return self.places.get(place_id)


class BrokenGeocodingClient:
    """Behaves as if the geocoding service is down."""

    def search(self, query, count=5):
        raise requests.RequestException("Geocoding down")

    def get(self, place_id):
        raise requests.RequestException("Geocoding down")


def use_geocoding(geocoding, weather=None, store=None):
    """Make /places, /forecast and /advice use these fakes."""
    weather = weather or FakeWeatherClient()
    store = store or FakeStore()
    app.dependency_overrides[get_geocoding] = lambda: geocoding
    app.dependency_overrides[get_controller] = lambda: ForecastController(weather, store, geocoding)
    return weather, store


@pytest.fixture(autouse=True)
def reset_overrides():
    yield
    app.dependency_overrides.clear()


# --- GET /locations ------------------------------------------------------------

def test_locations_returns_featured_cities_with_labels_and_timezones():
    response = client.get("/locations")

    assert response.status_code == 200
    assert response.json()[1] == {
        "name": "london", "latitude": 51.51, "longitude": -0.13,
        "label": "London", "timezone": "Europe/London",
    }


# --- GET /places ---------------------------------------------------------------

def test_places_returns_matches_with_labels():
    use_geocoding(FakeGeocodingClient())

    response = client.get("/places", params={"query": "brigh"})

    assert response.status_code == 200
    assert [p["label"] for p in response.json()] == [
        "Brighton, England, United Kingdom",
        "Brighton, Colorado, United States",
    ]
    assert response.json()[0]["name"] == "place-2654710"


def test_places_ignores_one_letter_searches():
    geocoding = FakeGeocodingClient()
    use_geocoding(geocoding)

    response = client.get("/places", params={"query": " b "})

    assert response.json() == []
    assert geocoding.searches == 0  # didn't even ask the geocoding service


def test_places_returns_503_when_search_is_down():
    use_geocoding(BrokenGeocodingClient())

    response = client.get("/places", params={"query": "brighton"})

    assert response.status_code == 503


# --- /forecast and /advice for a searched place --------------------------------

def test_forecast_for_a_searched_place():
    weather, store = use_geocoding(FakeGeocodingClient())

    response = client.get("/forecast", params={"location": "place-2654710"})

    assert response.status_code == 200
    assert len(response.json()) == 2
    assert "place-2654710" in store.snapshots  # cached under its own name, like a featured city


def test_forecast_accepts_a_bare_place_id():
    use_geocoding(FakeGeocodingClient())

    response = client.get("/forecast", params={"location": "5414941"})

    assert response.status_code == 200


def test_advice_for_a_searched_place():
    use_geocoding(FakeGeocodingClient())

    response = client.get("/advice", params={"location": "place-2654710"})

    assert response.status_code == 200
    assert response.json()[0]["kind"] == "rain-possible"


def test_unknown_place_id_returns_404():
    use_geocoding(FakeGeocodingClient())

    response = client.get("/forecast", params={"location": "place-999999999"})

    assert response.status_code == 404


def test_searched_place_returns_503_when_geocoding_is_down():
    use_geocoding(BrokenGeocodingClient())

    response = client.get("/forecast", params={"location": "place-2654710"})

    assert response.status_code == 503


def test_featured_city_still_works_when_geocoding_is_down():
    # Featured cities never need the geocoding service
    use_geocoding(BrokenGeocodingClient())

    response = client.get("/forecast", params={"location": "london"})

    assert response.status_code == 200
