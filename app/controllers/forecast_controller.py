import logging
from datetime import datetime, timezone
from functools import lru_cache

import requests
from botocore.exceptions import BotoCoreError, ClientError
from fastapi import APIRouter, Depends, HTTPException

from app.advice import Advice, build_advice, find_now_index
from app.forecast import HourlyForecast
from app.location import LOCATIONS, Location
from app.storage import SnapshotStore
from app.weather import WeatherClient

logger = logging.getLogger(__name__)


class LocationNotFoundError(Exception):
    pass


class ProviderUnavailableError(Exception):
    pass


class ForecastController:
    """Forecast logic, with no knowledge of HTTP.

    Checks the store for this hour's snapshot first; only calls Open-Meteo on a miss,
    then saves what it fetched so the next request this hour is served from the store.
    """

    def __init__(self, weather: WeatherClient, store: SnapshotStore):
        self.weather = weather
        self.store = store

    def get_forecast(self, name: str) -> list[HourlyForecast]:
        return WeatherClient.format_forecast(self._get_raw(name))

    def get_advice(self, name: str) -> list[Advice]:
        """Plain-language advice for the next few hours, starting from the current hour."""
        raw = self._get_raw(name)
        records = WeatherClient.format_forecast(raw)
        now_index = find_now_index(records, raw.get("utc_offset_seconds", 0))
        return build_advice(records, now_index)

    def _get_raw(self, name: str) -> dict:
        """This hour's raw forecast for a location: from the store if saved, otherwise from
        Open-Meteo (then saved for the rest of the hour)."""
        location = Location.get_location(name)
        if location is None:
            raise LocationNotFoundError(name)

        # One timestamp for the load and the save, so both use the same hourly key
        now = datetime.now(timezone.utc)

        raw = self._load_from_store(location, now)
        if raw is None:
            try:
                raw = self.weather.fetch_raw_forecast(location)
            except requests.RequestException as error:
                raise ProviderUnavailableError() from error
            self._save_to_store(location, raw, now)

        return raw

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
    return HTTPException(status_code=503, detail="Weather provider is unavailable. Try again later.")


@router.get("/forecast")
def get_forecast(location: str, controller: ForecastController = Depends(get_controller)) -> list[HourlyForecast]:
    """48 hourly records for a location."""
    try:
        return controller.get_forecast(location)
    except (LocationNotFoundError, ProviderUnavailableError) as error:
        raise to_http_error(location, error)


@router.get("/advice")
def get_advice(location: str, controller: ForecastController = Depends(get_controller)) -> list[Advice]:
    """Plain-language advice for the next 12 hours, e.g. "Rain likely from 3pm (80%)"."""
    try:
        return controller.get_advice(location)
    except (LocationNotFoundError, ProviderUnavailableError) as error:
        raise to_http_error(location, error)
