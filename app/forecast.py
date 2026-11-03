from dataclasses import dataclass


@dataclass(frozen=True)
class HourlyForecast:
    """The weather for one hour at one location."""
    time: str  # e.g. "2026-10-17T09:00", in the place's local time
    temperature_c: float
    rain_chance_percent: int
    wind_kph: float
    # Added in Nov 2026: snapshots saved before then don't have these, so they can be None
    feels_like_c: float | None = None  # "apparent temperature": wind and humidity included
    uv_index: float | None = None      # 0-2 low, 3-5 moderate, 6-7 high, 8+ very high
