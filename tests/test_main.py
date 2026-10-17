import requests

from fastapi.testclient import TestClient

from app import main
from tests.test_weather import SAMPLE_DATA

# TestClient sends requests to the app directly, without starting uvicorn.
client = TestClient(main.app)


def fake_fetch_forecast(latitude, longitude):
    return SAMPLE_DATA


def test_health_returns_ok():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_forecast_for_known_location_returns_records(monkeypatch):
    # main.py imported fetch_forecast by name, so we replace it inside main
    monkeypatch.setattr(main, "fetch_forecast", fake_fetch_forecast)

    response = client.get("/forecast", params={"location": "portsmouth"})

    assert response.status_code == 200
    assert len(response.json()) == 2
    assert response.json()[0]["temperature_c"] == 12.4


def test_forecast_location_is_not_case_sensitive(monkeypatch):
    monkeypatch.setattr(main, "fetch_forecast", fake_fetch_forecast)

    response = client.get("/forecast", params={"location": "London"})

    assert response.status_code == 200


def test_forecast_for_unknown_location_returns_404():
    response = client.get("/forecast", params={"location": "paris"})

    assert response.status_code == 404
    assert "paris" in response.json()["detail"]


def test_forecast_without_location_returns_422():
    response = client.get("/forecast")

    assert response.status_code == 422

def test_forecast_when_fetch_fails_returns_503(monkeypatch):
    def broken_fetch(latitude, longitude):
        raise requests.RequestException("Provider down")
    
    monkeypatch.setattr(main, "fetch_forecast", broken_fetch)

    response = client.get("/forecast", params={"location": "portsmouth"})

    assert response.status_code == 503