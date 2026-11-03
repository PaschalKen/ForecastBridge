from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from app.accuracy import Actual, compare, parse_actuals
from app.controllers import forecast_controller
from app.controllers.forecast_controller import ForecastController, get_controller
from app.main import app
from tests.test_main import BrokenStore, FakeStore, FakeWeatherClient


def utc(text: str) -> datetime:
    return datetime.fromisoformat(text).replace(tzinfo=timezone.utc)


def snapshot(hours: dict[str, tuple[float, int]], offset_seconds: int = 0) -> dict:
    """A raw forecast for just the given local hours: time -> (temperature, rain chance %)."""
    times = sorted(hours)
    return {
        "utc_offset_seconds": offset_seconds,
        "hourly": {
            "time": times,
            "temperature_2m": [hours[t][0] for t in times],
            "precipitation_probability": [hours[t][1] for t in times],
            "wind_speed_10m": [10.0] * len(times),
        },
    }


def actuals(values: dict[str, tuple[float, float]]) -> dict[str, Actual]:
    """time -> (actual temperature, actual rain mm)"""
    return {t: Actual(t, temp, rain) for t, (temp, rain) in values.items()}


def band(report, low):
    return next(b for b in report.by_lead if b.min_hours == low)


# --- parse_actuals ------------------------------------------------------------------

def test_parse_actuals_skips_hours_not_recorded_yet():
    raw = {"hourly": {
        "time": ["2026-11-01T00:00", "2026-11-01T01:00"],
        "temperature_2m": [9.5, None],
        "precipitation": [0.0, None],
    }}

    assert parse_actuals(raw) == {"2026-11-01T00:00": Actual("2026-11-01T00:00", 9.5, 0.0)}


# --- compare: temperature -----------------------------------------------------------

def test_compare_scores_temperature_error_and_bias_by_how_far_ahead():
    # Made 3 hours before 15:00 (1-6h band): 2°C too warm. Made 20 hours before (13-24h band): 1°C too cold.
    snapshots = [
        (utc("2026-11-02T12:00"), snapshot({"2026-11-02T15:00": (12.0, 0)})),
        (utc("2026-11-01T19:00"), snapshot({"2026-11-02T15:00": (9.0, 0)})),
    ]
    report = compare(snapshots, actuals({"2026-11-02T15:00": (10.0, 0.0)}))

    assert report.compared_hours == 1
    assert (band(report, 1).forecasts, band(report, 1).mean_error_c, band(report, 1).bias_c) == (1, 2.0, 2.0)
    assert (band(report, 13).forecasts, band(report, 13).mean_error_c, band(report, 13).bias_c) == (1, 1.0, -1.0)
    assert band(report, 7).forecasts == 0
    assert band(report, 7).mean_error_c is None


def test_within_2c_percent():
    snapshots = [
        (utc("2026-11-02T12:00"), snapshot({"2026-11-02T14:00": (11.5, 0), "2026-11-02T15:00": (13.0, 0)})),
    ]
    report = compare(snapshots, actuals({"2026-11-02T14:00": (10.0, 0.0), "2026-11-02T15:00": (10.0, 0.0)}))

    assert band(report, 1).within_2c_percent == 50  # 1.5°C off counts, 3°C off doesn't


def test_compare_ignores_snapshots_saved_during_or_after_the_hour():
    snapshots = [(utc("2026-11-02T15:00"), snapshot({"2026-11-02T15:00": (10.0, 0)}))]

    report = compare(snapshots, actuals({"2026-11-02T15:00": (10.0, 0.0)}))

    assert report.compared_hours == 0


def test_compare_ignores_hours_without_a_recorded_value():
    snapshots = [(utc("2026-11-02T12:00"), snapshot({"2026-11-02T15:00": (10.0, 0)}))]

    assert compare(snapshots, {}).compared_hours == 0


def test_compare_uses_the_snapshots_offset_for_local_times():
    # UK summer: 15:00 local is 14:00 UTC, so a snapshot saved at 13:00 UTC is 1 hour before (1-6h band)
    snapshots = [(utc("2026-08-02T13:00"), snapshot({"2026-08-02T15:00": (20.0, 0)}, offset_seconds=3600))]

    report = compare(snapshots, actuals({"2026-08-02T15:00": (20.0, 0.0)}))

    assert band(report, 1).forecasts == 1


# --- compare: rain ----------------------------------------------------------------

def test_rain_scores():
    hours = {f"2026-11-02T{h}:00": (10.0, chance) for h, chance in [("14", 80), ("15", 70), ("16", 10), ("17", 20)]}
    snapshots = [(utc("2026-11-02T12:00"), snapshot(hours))]
    recorded = actuals({
        "2026-11-02T14:00": (10.0, 1.2),  # rain likely, and it rained: right
        "2026-11-02T15:00": (10.0, 0.0),  # rain likely, but dry: wrong
        "2026-11-02T16:00": (10.0, 0.0),  # dry forecast, and dry: right
        "2026-11-02T17:00": (10.0, 0.0),  # dry forecast, and dry: right
    })

    report = compare(snapshots, recorded)

    assert band(report, 1).rain_likely_correct_percent == 50
    assert band(report, 1).dry_correct_percent == 100


def test_rain_scores_are_none_with_nothing_to_measure():
    snapshots = [(utc("2026-11-02T12:00"), snapshot({"2026-11-02T15:00": (10.0, 45)}))]  # neither likely nor dry

    report = compare(snapshots, actuals({"2026-11-02T15:00": (10.0, 0.0)}))

    assert band(report, 1).rain_likely_correct_percent is None
    assert band(report, 1).dry_correct_percent is None


# --- compare: chart series -----------------------------------------------------------

def test_chart_uses_the_forecast_made_nearest_to_24_hours_before():
    snapshots = [
        (utc("2026-11-01T13:00"), snapshot({"2026-11-02T15:00": (11.0, 0)})),  # 26h before
        (utc("2026-11-01T14:00"), snapshot({"2026-11-02T15:00": (12.0, 0)})),  # 25h before: nearest
        (utc("2026-11-02T12:00"), snapshot({"2026-11-02T15:00": (13.0, 0)})),  # 3h before: too close
    ]

    report = compare(snapshots, actuals({"2026-11-02T15:00": (10.0, 0.5)}))

    assert len(report.series) == 1
    point = report.series[0]
    assert (point.forecast_c, point.hours_before, point.actual_c, point.rained) == (12.0, 25, 10.0, True)


def test_chart_leaves_out_hours_with_no_forecast_near_24_hours_before():
    snapshots = [(utc("2026-11-02T12:00"), snapshot({"2026-11-02T15:00": (13.0, 0)}))]  # only 3h before

    assert compare(snapshots, actuals({"2026-11-02T15:00": (10.0, 0.0)})).series == []


# --- GET /accuracy -------------------------------------------------------------------

client = TestClient(app)

# The endpoint looks at the last few days from today, so the test data is dated yesterday
YESTERDAY = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d")
TARGET = f"{YESTERDAY}T01:00"
RECORDED = {"hourly": {"time": [TARGET], "temperature_2m": [11.0], "precipitation": [0.0]}}


class FakeArchiveWeatherClient(FakeWeatherClient):
    def fetch_actuals(self, location, start, end):
        return RECORDED


class BrokenArchiveWeatherClient(FakeWeatherClient):
    def fetch_actuals(self, location, start, end):
        import requests
        raise requests.RequestException("Archive down")


def use(weather, store):
    forecast_controller._accuracy_cache.clear()  # each test starts without cached reports
    app.dependency_overrides[get_controller] = lambda: ForecastController(weather, store)


def teardown_function():
    app.dependency_overrides.clear()
    forecast_controller._accuracy_cache.clear()


def test_accuracy_endpoint_returns_a_report():
    store = FakeStore()
    # Forecast 11.9°C for 01:00 yesterday, saved 3 hours before; recorded 11.0°C
    store.history = [(utc(TARGET) - timedelta(hours=3), snapshot({TARGET: (11.9, 35)}))]
    use(FakeArchiveWeatherClient(), store)

    response = client.get("/accuracy", params={"location": "portsmouth", "days": 7})

    assert response.status_code == 200
    report = response.json()
    assert report["compared_hours"] == 1
    assert report["by_lead"][0] == {
        "label": "1 to 6 hours ahead", "min_hours": 1, "max_hours": 6, "forecasts": 1,
        "mean_error_c": 0.9, "bias_c": 0.9, "within_2c_percent": 100,
        "rain_likely_correct_percent": None, "dry_correct_percent": None,
    }


def test_accuracy_rejects_too_many_days():
    use(FakeArchiveWeatherClient(), FakeStore())

    response = client.get("/accuracy", params={"location": "london", "days": 30})

    assert response.status_code == 422


def test_accuracy_for_unknown_location_returns_404():
    use(FakeArchiveWeatherClient(), FakeStore())

    assert client.get("/accuracy", params={"location": "paris"}).status_code == 404


def test_accuracy_returns_503_when_the_archive_is_down():
    use(BrokenArchiveWeatherClient(), FakeStore())

    assert client.get("/accuracy", params={"location": "london"}).status_code == 503


def test_accuracy_returns_503_when_storage_is_down():
    use(FakeArchiveWeatherClient(), BrokenStore())

    assert client.get("/accuracy", params={"location": "london"}).status_code == 503
