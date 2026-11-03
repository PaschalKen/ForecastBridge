"""How accurate the saved forecasts were: each snapshot's forecast compared with what actually
happened (Open-Meteo's historical archive).

Pure functions: snapshots and recorded weather in, a report out. No internet, no AWS.
"""
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from app.weather import WeatherClient

RAINED_MM = 0.1            # at least this much rain in an hour counts as "it rained"
RAIN_LIKELY_PERCENT = 60   # a forecast at or above this said rain was likely (as in the advice)
DRY_BELOW_PERCENT = 30     # a forecast below this said it would stay dry
CHART_LEAD_HOURS = 24      # the chart compares each hour with the forecast made about a day before,
CHART_LEAD_TOLERANCE = 3   # using the snapshot nearest to 24 hours, if one is within 3 hours of it

# How far ahead a forecast was made, in hours (inclusive ranges)
LEAD_BANDS = [(1, 6), (7, 12), (13, 24), (25, 48)]


@dataclass(frozen=True)
class Actual:
    """What one hour's weather actually was."""
    time: str                # local time, as in the forecasts, e.g. "2026-11-02T15:00"
    temperature_c: float
    precipitation_mm: float


@dataclass(frozen=True)
class LeadAccuracy:
    """How good the forecasts made this far ahead were."""
    label: str                                 # e.g. "13 to 24 hours ahead"
    min_hours: int
    max_hours: int
    forecasts: int                             # forecast/actual pairs compared
    mean_error_c: float | None                 # average temperature error, ignoring + or -
    bias_c: float | None                       # average of (forecast - actual): + means forecasts ran warm
    within_2c_percent: int | None              # % of forecasts within 2°C of what happened
    rain_likely_correct_percent: int | None    # when rain was forecast as likely, % of hours it rained
    dry_correct_percent: int | None            # when dry was forecast, % of hours it stayed dry


@dataclass(frozen=True)
class ComparisonPoint:
    """One hour on the "forecast vs what happened" chart."""
    time: str
    actual_c: float
    forecast_c: float       # from the snapshot made about CHART_LEAD_HOURS before
    hours_before: int
    rained: bool
    forecast_rain_percent: int


@dataclass(frozen=True)
class AccuracyReport:
    compared_hours: int            # hours that have a recorded value and at least one forecast
    by_lead: list[LeadAccuracy]
    series: list[ComparisonPoint]  # oldest hour first


def parse_actuals(raw: dict) -> dict[str, Actual]:
    """The archive's response -> {local time: Actual}. Hours not recorded yet (None) are left out."""
    hourly = raw.get("hourly", {})
    actuals = {}
    for time, temperature, precipitation in zip(
        hourly.get("time", []), hourly.get("temperature_2m", []), hourly.get("precipitation", [])
    ):
        if temperature is not None and precipitation is not None:
            actuals[time] = Actual(time, temperature, precipitation)
    return actuals


def percent(part: int, whole: int) -> int | None:
    """Whole-number percentage, or None when there's nothing to measure."""
    return round(100 * part / whole) if whole else None


def compare(snapshots: list[tuple[datetime, dict]], actuals: dict[str, Actual]) -> AccuracyReport:
    """Every forecast in every snapshot for an hour with a recorded value, scored against it."""
    pairs = []  # (hours_before, forecast record, actual)
    for made_at, raw in snapshots:
        offset = timedelta(seconds=raw.get("utc_offset_seconds", 0))
        for record in WeatherClient.format_forecast(raw):
            actual = actuals.get(record.time)
            if actual is None:
                continue
            # Forecast times are local; snapshot times are UTC (as in the history feature)
            target_utc = datetime.fromisoformat(record.time).replace(tzinfo=timezone.utc) - offset
            hours_before = round((target_utc - made_at).total_seconds() / 3600)
            if 1 <= hours_before <= 48:  # only real forecasts: made before the hour, within 2 days
                pairs.append((hours_before, record, actual))

    by_lead = [_score(low, high, [p for p in pairs if low <= p[0] <= high]) for low, high in LEAD_BANDS]
    return AccuracyReport(
        compared_hours=len({actual.time for _, _, actual in pairs}),
        by_lead=by_lead,
        series=_chart_series(pairs),
    )


def _score(low: int, high: int, pairs: list) -> LeadAccuracy:
    differences = [record.temperature_c - actual.temperature_c for _, record, actual in pairs]
    errors = [abs(difference) for difference in differences]
    likely = [actual for _, record, actual in pairs if record.rain_chance_percent >= RAIN_LIKELY_PERCENT]
    dry = [actual for _, record, actual in pairs if record.rain_chance_percent < DRY_BELOW_PERCENT]

    return LeadAccuracy(
        label=f"{low} to {high} hours ahead",
        min_hours=low,
        max_hours=high,
        forecasts=len(pairs),
        mean_error_c=round(sum(errors) / len(errors), 1) if errors else None,
        bias_c=round(sum(differences) / len(differences), 1) if differences else None,
        within_2c_percent=percent(sum(error <= 2 for error in errors), len(errors)),
        rain_likely_correct_percent=percent(sum(a.precipitation_mm >= RAINED_MM for a in likely), len(likely)),
        dry_correct_percent=percent(sum(a.precipitation_mm < RAINED_MM for a in dry), len(dry)),
    )


def _chart_series(pairs: list) -> list[ComparisonPoint]:
    """For each hour, the forecast made nearest to CHART_LEAD_HOURS before it."""
    best = {}  # time -> (distance from 24h, hours_before, record, actual)
    for hours_before, record, actual in pairs:
        distance = abs(hours_before - CHART_LEAD_HOURS)
        if distance <= CHART_LEAD_TOLERANCE and (record.time not in best or distance < best[record.time][0]):
            best[record.time] = (distance, hours_before, record, actual)

    return [
        ComparisonPoint(
            time=time,
            actual_c=actual.temperature_c,
            forecast_c=record.temperature_c,
            hours_before=hours_before,
            rained=actual.precipitation_mm >= RAINED_MM,
            forecast_rain_percent=record.rain_chance_percent,
        )
        for time, (_, hours_before, record, actual) in sorted(best.items())
    ]
