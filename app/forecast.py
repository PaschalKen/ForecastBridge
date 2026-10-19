from dataclasses import dataclass


@dataclass(frozen=True)
class HourlyForecast:
    """The weather for one hour at one location."""
    time: str  # e.g. "2026-10-17T09:00", UK local time
    temperature_c: float
    rain_chance_percent: int
    wind_kph: float
