"""Plain-language advice from hourly forecasts, e.g. "Rain likely from 3pm (80%)".

Every function here is pure: hourly records in, advice out. No internet, no AWS.
The tests in tests/test_advice.py describe exactly what each function returns.
"""
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from app.forecast import HourlyForecast

HOURS_AHEAD = 12             # how far ahead the advice looks
RAIN_LIKELY_PERCENT = 60     # at or above this: "Rain likely"
RAIN_POSSIBLE_PERCENT = 30   # at or above this (but below likely): "Small chance of rain"
JACKET_BELOW_C = 10          # coldest hour below this: "Take a jacket"
WINDY_KPH = 30               # strongest wind at or above this: "Windy"


@dataclass(frozen=True)
class Advice:
    kind: str     # "rain", "rain-possible", "dry", "cold", "jacket" or "wind"
    message: str  # the sentence shown to the user


def format_hour(time: str) -> str:
    """"2026-10-21T15:00" -> "3pm", "2026-10-21T09:00" -> "9am", "...T00:00" -> "12am"."""
    hour = int(time[11:13])
    suffix = "am" if hour < 12 else "pm"
    return f"{hour % 12 or 12}{suffix}"  # 0 and 12 both show as 12


def format_number(value: float) -> str:
    """4.0 -> "4", 9.5 -> "9.5" (f"{value:g}" drops a trailing .0)."""
    return f"{value:g}"


def rain_advice(hours: list[HourlyForecast]) -> Advice:
    """Rain likely (the first wet hour), a small chance (the most likely hour), or dry."""
    for hour in hours:
        if hour.rain_chance_percent >= RAIN_LIKELY_PERCENT:
            return Advice("rain", f"Rain likely from {format_hour(hour.time)} ({hour.rain_chance_percent}%)")

    # max() returns the first hour if several share the highest chance
    wettest = max(hours, key=lambda h: h.rain_chance_percent)
    if wettest.rain_chance_percent >= RAIN_POSSIBLE_PERCENT:
        return Advice(
            "rain-possible",
            f"Small chance of rain around {format_hour(wettest.time)} ({wettest.rain_chance_percent}%)",
        )

    return Advice("dry", f"Dry for the next {len(hours)} hours")


def temperature_advice(hours: list[HourlyForecast]) -> list[Advice]:
    """The coldest hour, plus a jacket suggestion if it's below JACKET_BELOW_C."""
    coldest = min(hours, key=lambda h: h.temperature_c)
    advice = [Advice("cold", f"Coldest at {format_hour(coldest.time)}: {format_number(coldest.temperature_c)}°C")]

    if coldest.temperature_c < JACKET_BELOW_C:
        advice.append(Advice("jacket", "Take a jacket"))

    return advice


def wind_advice(hours: list[HourlyForecast]) -> Advice | None:
    """The windiest hour if it reaches WINDY_KPH, otherwise None."""
    windiest = max(hours, key=lambda h: h.wind_kph)
    if windiest.wind_kph < WINDY_KPH:
        return None

    return Advice("wind", f"Windy around {format_hour(windiest.time)}, up to {format_number(windiest.wind_kph)} km/h")


def build_advice(records: list[HourlyForecast], now_index: int) -> list[Advice]:
    """All the advice for the HOURS_AHEAD hours starting at records[now_index]:
    rain, then temperature, then wind (only if windy). [] if no hours are left."""
    hours = records[now_index:now_index + HOURS_AHEAD]
    if not hours:
        return []

    advice = [rain_advice(hours)] + temperature_advice(hours)

    wind = wind_advice(hours)
    if wind is not None:
        advice.append(wind)

    return advice


def find_now_index(records: list[HourlyForecast], utc_offset_seconds: int, now: datetime | None = None) -> int:
    """Index of the record for the current hour, or 0 if it isn't in the data.

    The records' times are local to the forecast's timezone (UK time here), but the server's
    clock is UTC. Open-Meteo sends the offset (3600 in summer, 0 in winter), so local time is
    simply UTC + offset. No timezone library needed.
    """
    now = now or datetime.now(timezone.utc)
    local_hour = (now + timedelta(seconds=utc_offset_seconds)).strftime("%Y-%m-%dT%H:00")

    for index, record in enumerate(records):
        if record.time == local_hour:
            return index
    return 0
