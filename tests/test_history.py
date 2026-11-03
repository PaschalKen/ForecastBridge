from datetime import datetime, timezone

import boto3
import pytest
from moto import mock_aws

from app.history import HistoryPoint, forecast_history
from app.storage import SnapshotStore


def snapshot(start_day: str, temps: dict[str, float], offset_seconds: int = 0) -> dict:
    """A raw Open-Meteo response covering 2 days from midnight on start_day, all 10°C except the
    hours in `temps` (local "HH" on start_day, or "+1 HH" on the next day)."""
    times, temperatures = [], []
    for day_index, day in enumerate([start_day, _next_day(start_day)]):
        for hour in range(24):
            time = f"{day}T{hour:02d}:00"
            times.append(time)
            label = f"{hour:02d}" if day_index == 0 else f"+1 {hour:02d}"
            temperatures.append(temps.get(label, 10.0))
    return {
        "utc_offset_seconds": offset_seconds,
        "hourly": {
            "time": times,
            "temperature_2m": temperatures,
            "precipitation_probability": [20] * 48,
            "wind_speed_10m": [12.5] * 48,
        },
    }


def _next_day(day: str) -> str:
    return datetime.fromordinal(datetime.fromisoformat(day).toordinal() + 1).strftime("%Y-%m-%d")


def utc(text: str) -> datetime:
    return datetime.fromisoformat(text).replace(tzinfo=timezone.utc)


# --- forecast_history ----------------------------------------------------------

def test_history_reports_what_each_snapshot_forecast_for_the_hour():
    snapshots = [
        (utc("2026-11-02T09:00"), snapshot("2026-11-02", {"15": 12.0})),
        (utc("2026-11-02T12:00"), snapshot("2026-11-02", {"15": 11.0})),
    ]

    history = forecast_history(snapshots, "2026-11-02T15:00")

    assert history == [
        HistoryPoint("2026-11-02T09:00Z", 6, 12.0, 20, 12.5),
        HistoryPoint("2026-11-02T12:00Z", 3, 11.0, 20, 12.5),
    ]


def test_history_is_oldest_forecast_first():
    snapshots = [
        (utc("2026-11-02T12:00"), snapshot("2026-11-02", {})),
        (utc("2026-11-01T12:00"), snapshot("2026-11-01", {})),
    ]

    history = forecast_history(snapshots, "2026-11-02T15:00")

    assert [p.hours_before for p in history] == [27, 3]


def test_history_converts_local_time_to_utc_with_the_snapshots_offset():
    # UK summer time: 15:00 local is 14:00 UTC, so a snapshot saved at 12:00 UTC is 2 hours before
    snapshots = [(utc("2026-08-02T12:00"), snapshot("2026-08-02", {}, offset_seconds=3600))]

    assert forecast_history(snapshots, "2026-08-02T15:00")[0].hours_before == 2


def test_history_includes_a_snapshot_saved_during_the_hour():
    snapshots = [(utc("2026-11-02T15:00"), snapshot("2026-11-02", {}))]

    assert forecast_history(snapshots, "2026-11-02T15:00")[0].hours_before == 0


def test_history_leaves_out_snapshots_saved_after_the_hour():
    snapshots = [(utc("2026-11-02T16:00"), snapshot("2026-11-02", {}))]

    assert forecast_history(snapshots, "2026-11-02T15:00") == []


def test_history_leaves_out_snapshots_that_do_not_include_the_hour():
    # Saved on 30 Oct, so it only covers 30 and 31 Oct
    snapshots = [(utc("2026-10-30T12:00"), snapshot("2026-10-30", {}))]

    assert forecast_history(snapshots, "2026-11-02T15:00") == []


# --- SnapshotStore.snapshots_between (moto's fake S3) ---------------------------

@pytest.fixture
def store(monkeypatch):
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")
    monkeypatch.delenv("AWS_PROFILE", raising=False)

    with mock_aws():
        s3 = boto3.client("s3")
        s3.create_bucket(Bucket="test-bucket")
        yield SnapshotStore("test-bucket", s3)


def test_snapshots_between_returns_saved_hours_in_range_oldest_first(store):
    for when in ["2026-11-01T22:00", "2026-11-02T09:00", "2026-11-01T23:00", "2026-11-02T20:00"]:
        store.save("london", {"saved": when}, utc(when))

    found = store.snapshots_between("london", utc("2026-11-01T23:00"), utc("2026-11-02T12:00"))

    assert [(when, raw["saved"]) for when, raw in found] == [
        (utc("2026-11-01T23:00"), "2026-11-01T23:00"),
        (utc("2026-11-02T09:00"), "2026-11-02T09:00"),
    ]


def test_snapshots_between_ignores_other_places_and_old_style_keys(store):
    store.save("london", {"ok": True}, utc("2026-11-02T09:00"))
    store.save("manchester", {"ok": False}, utc("2026-11-02T09:00"))
    store.s3_client.put_object(Bucket="test-bucket", Key="raw/london/2026-11-02/08-11-17.json", Body="{}")

    found = store.snapshots_between("london", utc("2026-11-02T00:00"), utc("2026-11-02T23:00"))

    assert [raw for _, raw in found] == [{"ok": True}]


def test_snapshots_between_with_nothing_saved_returns_empty_list(store):
    assert store.snapshots_between("london", utc("2026-11-01T00:00"), utc("2026-11-03T00:00")) == []
