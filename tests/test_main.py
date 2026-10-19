import pytest
import requests
from botocore.exceptions import EndpointConnectionError
from fastapi.testclient import TestClient

from app.controllers.forecast_controller import ForecastController, get_controller
from app.main import app
from app.weather import WeatherClient
from tests.test_weather import SAMPLE_DATA

# TestClient sends requests to the app directly, without starting uvicorn.
client = TestClient(app)


class FakeWeatherClient(WeatherClient):
    """Returns sample data instead of calling Open-Meteo, and counts the calls."""

    def __init__(self):
        super().__init__()
        self.calls = 0

    def fetch_raw_forecast(self, location):
        self.calls += 1
        return SAMPLE_DATA


class BrokenWeatherClient(WeatherClient):
    """Behaves as if Open-Meteo is down."""

    def fetch_raw_forecast(self, location):
        raise requests.RequestException("Provider down")


class FakeStore:
    """Keeps snapshots in a dictionary instead of S3."""

    def __init__(self):
        self.snapshots = {}

    def load(self, location_name, when=None):
        return self.snapshots.get(location_name)

    def save(self, location_name, data, when=None):
        self.snapshots[location_name] = data
        return f"raw/{location_name}/test.json"


class BrokenStore:
    """Behaves as if S3 is unreachable."""

    def load(self, location_name, when=None):
        raise EndpointConnectionError(endpoint_url="https://s3.example")

    def save(self, location_name, data, when=None):
        raise EndpointConnectionError(endpoint_url="https://s3.example")


def use(weather_client, store):
    """Make the /forecast route use the given weather client and store."""
    app.dependency_overrides[get_controller] = lambda: ForecastController(weather_client, store)


@pytest.fixture(autouse=True)
def reset_overrides():
    # Runs around every test, so one test's fakes never leak into the next
    yield
    app.dependency_overrides.clear()


def test_health_returns_ok():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_forecast_for_known_location_returns_records():
    use(FakeWeatherClient(), FakeStore())

    response = client.get("/forecast", params={"location": "portsmouth"})

    assert response.status_code == 200
    assert len(response.json()) == 2
    assert response.json()[0]["temperature_c"] == 12.4


def test_forecast_location_is_not_case_sensitive():
    use(FakeWeatherClient(), FakeStore())

    response = client.get("/forecast", params={"location": "London"})

    assert response.status_code == 200


def test_forecast_for_unknown_location_returns_404():
    use(FakeWeatherClient(), FakeStore())

    response = client.get("/forecast", params={"location": "paris"})

    assert response.status_code == 404
    assert "paris" in response.json()["detail"]


def test_forecast_without_location_returns_422():
    response = client.get("/forecast")

    assert response.status_code == 422


def test_forecast_when_fetch_fails_returns_503():
    use(BrokenWeatherClient(), FakeStore())

    response = client.get("/forecast", params={"location": "portsmouth"})

    assert response.status_code == 503


def test_cache_miss_fetches_and_saves():
    weather, store = FakeWeatherClient(), FakeStore()
    use(weather, store)

    client.get("/forecast", params={"location": "portsmouth"})

    assert weather.calls == 1
    assert store.snapshots["portsmouth"] == SAMPLE_DATA


def test_cache_hit_does_not_call_open_meteo():
    weather, store = FakeWeatherClient(), FakeStore()
    store.snapshots["portsmouth"] = SAMPLE_DATA
    use(weather, store)

    response = client.get("/forecast", params={"location": "portsmouth"})

    assert response.status_code == 200
    assert weather.calls == 0


def test_second_request_in_same_hour_is_served_from_store():
    weather, store = FakeWeatherClient(), FakeStore()
    use(weather, store)

    client.get("/forecast", params={"location": "portsmouth"})
    client.get("/forecast", params={"location": "portsmouth"})

    assert weather.calls == 1


def test_cached_forecast_still_served_when_open_meteo_is_down():
    store = FakeStore()
    store.snapshots["portsmouth"] = SAMPLE_DATA
    use(BrokenWeatherClient(), store)

    response = client.get("/forecast", params={"location": "portsmouth"})

    assert response.status_code == 200


def test_storage_failure_does_not_break_the_request():
    use(FakeWeatherClient(), BrokenStore())

    response = client.get("/forecast", params={"location": "portsmouth"})

    assert response.status_code == 200
    assert len(response.json()) == 2


def test_home_page_serves_the_front_end():
    response = client.get("/")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "ForecastBridge" in response.text


def test_static_files_are_served():
    response = client.get("/static/app.js")

    assert response.status_code == 200
