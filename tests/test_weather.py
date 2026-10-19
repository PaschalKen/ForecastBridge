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
    }
}

PORTSMOUTH = Location("portsmouth", 50.80, -1.09)


def test_format_forecast_makes_one_record_per_hour():
    records = WeatherClient.format_forecast(SAMPLE_DATA)

    assert records == [
        HourlyForecast(time="2026-10-17T00:00", temperature_c=12.4, rain_chance_percent=20, wind_kph=15.2),
        HourlyForecast(time="2026-10-17T01:00", temperature_c=11.9, rain_chance_percent=35, wind_kph=14.8),
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
