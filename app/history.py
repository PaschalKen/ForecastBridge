"""How the forecast for one hour changed across the hourly snapshots saved in S3.

Pure functions: snapshots in, history out. No internet, no AWS.
"""
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from app.weather import WeatherClient

MAX_HOURS_BEFORE = 48  # a snapshot holds 2 days of forecast, so nothing older can include the hour


@dataclass(frozen=True)
class HistoryPoint:
    """What one saved snapshot forecast for the chosen hour."""
    forecast_made: str      # the UTC hour the snapshot was saved, e.g. "2026-11-01T14:00Z"
    hours_before: int       # how far ahead of the chosen hour that was (0 = during that hour)
    temperature_c: float
    rain_chance_percent: int
    wind_kph: float


def forecast_history(snapshots: list[tuple[datetime, dict]], target_time: str) -> list[HistoryPoint]:
    """For the hour `target_time` (local time, as the API shows it, e.g. "2026-11-03T15:00"), what
    each snapshot forecast for it, oldest forecast first. Snapshots that don't include that hour,
    or were saved after it, are left out."""
    points = []

    for made_at, raw in snapshots:
        record = next((r for r in WeatherClient.format_forecast(raw) if r.time == target_time), None)
        if record is None:
            continue

        # Forecast times are local; snapshot times are UTC. The snapshot's own offset converts
        # between them (it's 0 in UK winter, 3600 in summer), like find_now_index does.
        target_utc = datetime.fromisoformat(target_time).replace(tzinfo=timezone.utc) - timedelta(
            seconds=raw.get("utc_offset_seconds", 0)
        )
        hours_before = round((target_utc - made_at).total_seconds() / 3600)
        if not 0 <= hours_before <= MAX_HOURS_BEFORE:
            continue

        points.append(HistoryPoint(
            forecast_made=made_at.strftime("%Y-%m-%dT%H:00Z"),
            hours_before=hours_before,
            temperature_c=record.temperature_c,
            rain_chance_percent=record.rain_chance_percent,
            wind_kph=record.wind_kph,
        ))

    return sorted(points, key=lambda p: p.hours_before, reverse=True)
