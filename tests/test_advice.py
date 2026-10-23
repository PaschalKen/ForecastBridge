from datetime import datetime, timezone

from app.advice import (
    Advice,
    build_advice,
    find_now_index,
    format_hour,
    rain_advice,
    temperature_advice,
    wind_advice,
)
from app.forecast import HourlyForecast


def hour(time: str, temp: float = 12, rain: int = 0, wind: float = 10) -> HourlyForecast:
    """One hour of forecast. Anything not given is mild, dry and calm."""
    return HourlyForecast(time=time, temperature_c=temp, rain_chance_percent=rain, wind_kph=wind)


def day(start_hour: int, count: int, **changes) -> list[HourlyForecast]:
    """`count` mild, dry, calm hours from `start_hour` on 21 Oct, with some hours changed.

    changes maps an hour to a dict of values, e.g. day(9, 12, **{"15": {"rain": 80}})
    """
    hours = []
    for h in range(start_hour, start_hour + count):
        hours.append(hour(f"2026-10-21T{h:02d}:00", **changes.get(str(h), {})))
    return hours


# --- format_hour --------------------------------------------------------------

def test_format_hour_morning_and_afternoon():
    assert format_hour("2026-10-21T09:00") == "9am"
    assert format_hour("2026-10-21T15:00") == "3pm"


def test_format_hour_midnight_and_noon():
    assert format_hour("2026-10-21T00:00") == "12am"
    assert format_hour("2026-10-21T12:00") == "12pm"


# --- rain_advice --------------------------------------------------------------

def test_rain_likely_reports_the_first_wet_hour():
    hours = day(9, 12, **{"15": {"rain": 80}, "18": {"rain": 95}})

    assert rain_advice(hours) == Advice("rain", "Rain likely from 3pm (80%)")


def test_small_chance_of_rain_reports_the_most_likely_hour():
    hours = day(9, 12, **{"14": {"rain": 35}, "18": {"rain": 45}})

    assert rain_advice(hours) == Advice("rain-possible", "Small chance of rain around 6pm (45%)")


def test_dry_when_no_hour_reaches_30_percent():
    hours = day(9, 12, **{"14": {"rain": 29}})

    assert rain_advice(hours) == Advice("dry", "Dry for the next 12 hours")


def test_dry_message_uses_the_number_of_hours_given():
    assert rain_advice(day(18, 5)) == Advice("dry", "Dry for the next 5 hours")


# --- temperature_advice -------------------------------------------------------

def test_reports_the_coldest_hour():
    hours = day(0, 12, **{"6": {"temp": 11}, "7": {"temp": 11.5}})

    assert temperature_advice(hours) == [Advice("cold", "Coldest at 6am: 11°C")]


def test_suggests_a_jacket_below_10_degrees():
    hours = day(0, 12, **{"6": {"temp": 4}})

    assert temperature_advice(hours) == [
        Advice("cold", "Coldest at 6am: 4°C"),
        Advice("jacket", "Take a jacket"),
    ]


def test_keeps_decimal_temperatures():
    hours = day(0, 12, **{"5": {"temp": 9.5}})

    assert temperature_advice(hours)[0] == Advice("cold", "Coldest at 5am: 9.5°C")


# --- wind_advice --------------------------------------------------------------

def test_windy_reports_the_strongest_hour():
    hours = day(9, 12, **{"16": {"wind": 31}, "17": {"wind": 35}})

    assert wind_advice(hours) == Advice("wind", "Windy around 5pm, up to 35 km/h")


def test_no_wind_advice_below_30_kph():
    hours = day(9, 12, **{"16": {"wind": 29.9}})

    assert wind_advice(hours) is None


# --- build_advice -------------------------------------------------------------

def test_build_advice_only_looks_at_the_next_12_hours_from_now():
    # 48 hours from midnight; "now" is index 9 (9am). Rain at 8pm is inside the window,
    # rain at 10pm (index 22) is outside it.
    records = day(0, 24, **{"20": {"rain": 70}}) + day(0, 24)
    records[22] = hour("2026-10-21T22:00", rain=90)

    advice = build_advice(records, now_index=9)

    assert advice[0] == Advice("rain", "Rain likely from 8pm (70%)")


def test_build_advice_returns_rain_then_temperature_then_wind():
    records = day(0, 24, **{"10": {"rain": 70, "temp": 5, "wind": 40}})

    kinds = [a.kind for a in build_advice(records, now_index=9)]

    assert kinds == ["rain", "cold", "jacket", "wind"]


def test_build_advice_leaves_out_wind_when_calm():
    kinds = [a.kind for a in build_advice(day(0, 24), now_index=9)]

    assert kinds == ["dry", "cold"]


def test_build_advice_with_no_hours_left_returns_nothing():
    assert build_advice(day(0, 24), now_index=24) == []


# --- find_now_index -----------------------------------------------------------

def test_find_now_index_converts_utc_to_uk_summer_time():
    # 14:30 UTC is 15:30 in UK summer time (offset +3600 seconds), so "now" is the 15:00 record
    now = datetime(2026, 10, 21, 14, 30, tzinfo=timezone.utc)

    assert find_now_index(day(0, 24), utc_offset_seconds=3600, now=now) == 15


def test_find_now_index_in_winter_time_uses_utc():
    now = datetime(2026, 10, 21, 14, 30, tzinfo=timezone.utc)

    assert find_now_index(day(0, 24), utc_offset_seconds=0, now=now) == 14


def test_find_now_index_falls_back_to_the_first_hour():
    now = datetime(2027, 1, 1, 12, 0, tzinfo=timezone.utc)

    assert find_now_index(day(0, 24), utc_offset_seconds=0, now=now) == 0
