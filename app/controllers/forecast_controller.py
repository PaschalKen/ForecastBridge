import logging
from typing import Literal
from datetime import datetime, timedelta, timezone
from functools import lru_cache

import requests
from botocore.exceptions import BotoCoreError, ClientError
from fastapi import APIRouter, Depends, HTTPException, Query

from app.accuracy import AccuracyReport, compare, parse_actuals
from app.advice import Advice, build_advice, find_now_index
from app.forecast import HourlyForecast
from app.geocoding import GeocodingClient, get_geocoding
from app.history import MAX_HOURS_BEFORE, HistoryPoint, forecast_history
from app.location import LOCATIONS, Location, place_id_from
from app.storage import SnapshotStore
from app.weather import WeatherClient

logger = logging.getLogger(__name__)


class LocationNotFoundError(Exception):
    pass


class ProviderUnavailableError(Exception):
    pass


class HistoryUnavailableError(Exception):
    pass


# Accuracy reports already worked out this hour (each takes a few hundred S3 reads), shared by
# requests while this Lambda instance stays warm
_accuracy_cache: dict[tuple, AccuracyReport] = {}


class ForecastController:
    """Forecast logic, with no knowledge of HTTP.

    Checks the store for this hour's snapshot first; only calls Open-Meteo on a miss,
    then saves what it fetched so the next request this hour is served from the store.
    """

    def __init__(self, weather: WeatherClient, store: SnapshotStore, geocoding: GeocodingClient | None = None):
        self.weather = weather
        self.store = store
        self.geocoding = geocoding or get_geocoding()

    def get_forecast(self, name: str) -> list[HourlyForecast]:
        return WeatherClient.format_forecast(self._get_raw(name))

    def get_advice(self, name: str, units: str = "metric") -> list[Advice]:
        """Plain-language advice for the next few hours, starting from the current hour."""
        raw = self._get_raw(name)
        records = WeatherClient.format_forecast(raw)
        now_index = find_now_index(records, raw.get("utc_offset_seconds", 0))
        return build_advice(records, now_index, units)

    def get_history(self, name: str, target_time: str) -> list[HistoryPoint]:
        """How the forecast for one hour (local time, e.g. "2026-11-03T15:00") changed across
        the snapshots saved in S3."""
        location = self._resolve(name)

        # Snapshot keys are UTC hours but target_time is local, so search a little wider than
        # 48 hours (time zones are at most 14 hours from UTC); forecast_history then keeps only
        # the snapshots that really are 0 to 48 hours before the target.
        target = datetime.fromisoformat(target_time).replace(tzinfo=timezone.utc)
        start = target - timedelta(hours=MAX_HOURS_BEFORE + 14)
        end = target + timedelta(hours=14)

        try:
            snapshots = self.store.snapshots_between(location.name, start, end)
        except (BotoCoreError, ClientError) as error:
            # Unlike the cache, history only exists in S3, so here a storage problem is an error
            logger.warning("Could not read forecast history for %s", location.name, exc_info=True)
            raise HistoryUnavailableError() from error

        return forecast_history(snapshots, target_time)

    def get_accuracy(self, name: str, days: int) -> AccuracyReport:
        """How accurate the saved forecasts were over the last `days` full days (up to yesterday)."""
        location = self._resolve(name)

        # One report per place, length and hour is plenty: it only changes as new hours are recorded
        cache_key = (location.name, days, datetime.now(timezone.utc).strftime("%Y-%m-%dT%H"))
        if cache_key in _accuracy_cache:
            return _accuracy_cache[cache_key]

        today = datetime.now(timezone.utc).date()
        first_day, last_day = today - timedelta(days=days), today - timedelta(days=1)

        try:
            actuals = parse_actuals(self.weather.fetch_actuals(location, first_day, last_day))
        except requests.RequestException as error:
            raise ProviderUnavailableError() from error

        # Snapshots from 2 days before the first hour (forecasts reach 48 hours ahead) to the end
        # of the last day, with time zone margin; compare() keeps only real 1-48 hour forecasts.
        start = datetime.combine(first_day, datetime.min.time(), timezone.utc) - timedelta(hours=48 + 14)
        end = datetime.combine(last_day, datetime.min.time(), timezone.utc) + timedelta(hours=24 + 14)
        try:
            snapshots = self.store.snapshots_between(location.name, start, end)
        except (BotoCoreError, ClientError) as error:
            logger.warning("Could not read snapshots for accuracy of %s", location.name, exc_info=True)
            raise HistoryUnavailableError() from error

        report = compare(snapshots, actuals)
        if len(_accuracy_cache) > 100:  # a small cache: drop everything rather than grow forever
            _accuracy_cache.clear()
        _accuracy_cache[cache_key] = report
        return report

    def _get_raw(self, name: str) -> dict:
        """This hour's raw forecast for a location: from the store if saved, otherwise from
        Open-Meteo (then saved for the rest of the hour)."""
        location = self._resolve(name)

        # One timestamp for the load and the save, so both use the same hourly key
        now = datetime.now(timezone.utc)

        raw = self._load_from_store(location, now)
        # A snapshot saved before we asked for feels-like and UV is refetched (and overwritten)
        if raw is None or not WeatherClient.has_all_fields(raw):
            try:
                raw = self.weather.fetch_raw_forecast(location)
            except requests.RequestException as error:
                raise ProviderUnavailableError() from error
            self._save_to_store(location, raw, now)

        return raw

    def _resolve(self, name: str) -> Location:
        """A featured city ("london") or a searched place ("place-2654710") -> its Location."""
        location = Location.get_location(name)
        if location is not None:
            return location

        place_id = place_id_from(name)
        if place_id is None:
            raise LocationNotFoundError(name)

        try:
            place = self.geocoding.get(place_id)
        except requests.RequestException as error:
            raise ProviderUnavailableError() from error
        if place is None:
            raise LocationNotFoundError(name)
        return place

    # Storage is a bonus: if S3 has a problem, log it and carry on rather than fail the request.

    def _load_from_store(self, location: Location, now: datetime) -> dict | None:
        try:
            return self.store.load(location.name, now)
        except (BotoCoreError, ClientError):
            logger.warning("Could not read cached forecast for %s", location.name, exc_info=True)
            return None

    def _save_to_store(self, location: Location, raw: dict, now: datetime) -> None:
        try:
            self.store.save(location.name, raw, now)
        except (BotoCoreError, ClientError):
            logger.warning("Could not save forecast for %s", location.name, exc_info=True)


@lru_cache
def get_store() -> SnapshotStore:
    """One store (and S3 client) for the whole app, created on first use."""
    return SnapshotStore.from_config()


def get_controller() -> ForecastController:
    """FastAPI calls this to build the controller for each request (tests can swap it)."""
    return ForecastController(WeatherClient(), get_store())

router = APIRouter()


def to_http_error(location: str, error: Exception) -> HTTPException:
    """Turn the controller's errors into HTTP responses (shared by every route here)."""
    if isinstance(error, LocationNotFoundError):
        return HTTPException(
            status_code=404,
            detail=f"Location '{location.lower()}' not found. Available: {', '.join(LOCATIONS)}",
        )
    if isinstance(error, HistoryUnavailableError):
        return HTTPException(status_code=503, detail="Saved forecasts are unavailable. Try again later.")
    return HTTPException(status_code=503, detail="Weather provider is unavailable. Try again later.")


@router.get("/forecast")
def get_forecast(location: str, controller: ForecastController = Depends(get_controller)) -> list[HourlyForecast]:
    """48 hourly records for a location."""
    try:
        return controller.get_forecast(location)
    except (LocationNotFoundError, ProviderUnavailableError) as error:
        raise to_http_error(location, error)


@router.get("/advice")
def get_advice(
    location: str,
    units: Literal["metric", "imperial"] = "metric",
    controller: ForecastController = Depends(get_controller),
) -> list[Advice]:
    """Plain-language advice for the next 12 hours, e.g. "Rain likely from 3pm (80%)".
    `units=imperial` gives temperatures in °F and wind in mph."""
    try:
        return controller.get_advice(location, units)
    except (LocationNotFoundError, ProviderUnavailableError) as error:
        raise to_http_error(location, error)


@router.get("/history")
def get_history(
    location: str,
    time: str = Query(pattern=r"^\d{4}-\d{2}-\d{2}T\d{2}:00$", examples=["2026-11-03T15:00"]),
    controller: ForecastController = Depends(get_controller),
) -> list[HistoryPoint]:
    """How the forecast for one hour changed: what each saved hourly snapshot (up to 48 hours
    before) said about it, oldest first. `time` is in the place's local time, as /forecast shows it."""
    try:
        return controller.get_history(location, time)
    except (LocationNotFoundError, ProviderUnavailableError, HistoryUnavailableError) as error:
        raise to_http_error(location, error)


@router.get("/accuracy")
def get_accuracy(
    location: str,
    days: int = Query(7, ge=1, le=14),
    controller: ForecastController = Depends(get_controller),
) -> AccuracyReport:
    """How accurate the saved forecasts were over the last `days` full days: each forecast compared
    with what actually happened (Open-Meteo's historical archive), grouped by how far ahead it was made."""
    try:
        return controller.get_accuracy(location, days)
    except (LocationNotFoundError, ProviderUnavailableError, HistoryUnavailableError) as error:
        raise to_http_error(location, error)
