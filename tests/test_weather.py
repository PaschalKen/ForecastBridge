from app import weather
from app.forecast import HourlyForecast
from app.location import Location
from app.weather import WeatherClient

# A small, hand-made copy of what Open-Meteo returns, so tests never need the internet.
SAMPLE_DATA = {
    "hourly": {
        "time": ["2026-10-17T00:00", "2026-10-17T01:00"],
        "temperature_2m": [12.4, 11.9],
        "precipitation_probability": [20, 35],
        "wind_speed_10m": [15.2, 14.8],
        "apparent_temperature": [10.1, 9.6],
        "uv_index": [0.0, 0.0],
    }
}

PORTSMOUTH = Location("portsmouth", 50.80, -1.09)


def test_format_forecast_makes_one_record_per_hour():
    records = WeatherClient.format_forecast(SAMPLE_DATA)

    assert records == [
        HourlyForecast(time="2026-10-17T00:00", temperature_c=12.4, rain_chance_percent=20, wind_kph=15.2,
                       feels_like_c=10.1, uv_index=0.0),
        HourlyForecast(time="2026-10-17T01:00", temperature_c=11.9, rain_chance_percent=35, wind_kph=14.8,
                       feels_like_c=9.6, uv_index=0.0),
    ]


def test_format_forecast_with_no_hours_returns_empty_list():
    empty = {"hourly": {"time": [], "temperature_2m": [], "precipitation_probability": [], "wind_speed_10m": []}}

    assert WeatherClient.format_forecast(empty) == []


class FakeResponse:
    """Stands in for a requests.Response, so no real HTTP call is made."""

    def raise_for_status(self):
        pass

    def json(self):
        return SAMPLE_DATA


def test_fetch_raw_forecast_sends_coordinates_and_returns_json(monkeypatch):
    calls = []

    def fake_get(url, params, timeout):
        calls.append({"url": url, "params": params, "timeout": timeout})
        return FakeResponse()

    # Swap requests.get for our fake for the length of this test only
    monkeypatch.setattr(weather.requests, "get", fake_get)

    client = WeatherClient(url="https://example.test/forecast", timeout=5)
    result = client.fetch_raw_forecast(PORTSMOUTH)

    assert result == SAMPLE_DATA
    assert calls[0]["url"] == "https://example.test/forecast"
    assert calls[0]["params"]["latitude"] == 50.80
    assert calls[0]["params"]["longitude"] == -1.09
    assert calls[0]["timeout"] == 5


def test_get_location_ignores_capitals_and_returns_none_if_unknown():
    assert Location.get_location("London").name == "london"
    assert Location.get_location("paris") is None


def test_fetch_raw_forecast_asks_for_the_places_own_timezone(monkeypatch):
    calls = []

    def fake_get(url, params, timeout):
        calls.append(params)
        return FakeResponse()

    monkeypatch.setattr(weather.requests, "get", fake_get)
    paris = Location("place-2988507", 48.85, 2.35, label="Paris, Île-de-France, France", timezone="Europe/Paris")

    WeatherClient().fetch_raw_forecast(paris)

    assert calls[0]["timezone"] == "Europe/Paris"


def test_format_forecast_handles_snapshots_saved_before_feels_like_and_uv():
    old_snapshot = {"hourly": {k: v for k, v in SAMPLE_DATA["hourly"].items()
                               if k not in ("apparent_temperature", "uv_index")}}

    records = WeatherClient.format_forecast(old_snapshot)

    assert records[0].temperature_c == 12.4
    assert records[0].feels_like_c is None
    assert records[0].uv_index is None


def test_has_all_fields_spots_snapshots_missing_newer_fields():
    old_snapshot = {"hourly": {k: v for k, v in SAMPLE_DATA["hourly"].items() if k != "uv_index"}}

    assert WeatherClient.has_all_fields(SAMPLE_DATA) is True
    assert WeatherClient.has_all_fields(old_snapshot) is False
