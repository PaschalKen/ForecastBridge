import sys
from datetime import date

import requests

from app.config import ARCHIVE_URL, OPEN_METEO_URL
from app.forecast import HourlyForecast
from app.location import LOCATIONS, Location


# The hourly values asked from Open-Meteo. A cached snapshot missing any of them is out of date.
HOURLY_FIELDS = [
    "temperature_2m",
    "precipitation_probability",
    "wind_speed_10m",
    "apparent_temperature",
    "uv_index",
]


class WeatherClient:
    """Talks to Open-Meteo. One client is reused for every location."""

    def __init__(self, url: str = OPEN_METEO_URL, timeout: int = 10, archive_url: str = ARCHIVE_URL):
        self.url = url
        self.timeout = timeout
        self.archive_url = archive_url

    def fetch_raw_forecast(self, location: Location) -> dict:
        """Open-Meteo's response exactly as received (the collector saves this)."""
        params = {
            "latitude": location.latitude,
            "longitude": location.longitude,
            "hourly": ",".join(HOURLY_FIELDS),
            "forecast_days": 2,
            "timezone": location.timezone,  # times come back in the place's own time zone
        }

        response = requests.get(self.url, params=params, timeout=self.timeout)
        response.raise_for_status()  # Raise an error for bad responses
        return response.json()

    def fetch_actuals(self, location: Location, start: date, end: date) -> dict:
        """What the weather actually was, hour by hour, from start to end (local dates, inclusive):
        Open-Meteo's historical archive, as received. Recent hours can be missing (None)."""
        params = {
            "latitude": location.latitude,
            "longitude": location.longitude,
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "hourly": "temperature_2m,precipitation",
            "timezone": location.timezone,  # same local times as the forecasts, so hours line up
        }
        response = requests.get(self.archive_url, params=params, timeout=self.timeout)
        response.raise_for_status()
        return response.json()

    def get_forecast(self, location: Location) -> list[HourlyForecast]:
        """Hourly records for one location (the API returns this)."""
        return self.format_forecast(self.fetch_raw_forecast(location))

    @staticmethod
    def format_forecast(data: dict) -> list[HourlyForecast]:
        """Turn Open-Meteo's separate hourly lists into one record per hour."""
        hourly = data["hourly"]
        hours = len(hourly["time"])
        # Older snapshots don't have the newer fields: use None for every hour instead
        feels_like = hourly.get("apparent_temperature") or [None] * hours
        uv = hourly.get("uv_index") or [None] * hours
        records = []

        for time, temperature, rain_chance, wind, feels, uv_index in zip(
            hourly["time"],
            hourly["temperature_2m"],
            hourly["precipitation_probability"],
            hourly["wind_speed_10m"],
            feels_like,
            uv,
        ):
            records.append(HourlyForecast(
                time=time,
                temperature_c=temperature,
                rain_chance_percent=rain_chance,
                wind_kph=wind,  # Open-Meteo returns km/h by default
                feels_like_c=feels,
                uv_index=uv_index,
            ))

        return records

    @staticmethod
    def has_all_fields(data: dict) -> bool:
        """True if a saved snapshot has every hourly field we now ask for."""
        return all(field in data.get("hourly", {}) for field in HOURLY_FIELDS)


if __name__ == "__main__":
    # Usage: python -m app.weather london
    name = sys.argv[1] if len(sys.argv) > 1 else "portsmouth"
    location = Location.get_location(name)
    if location is None:
        sys.exit(f"Unknown location '{name}'. Try one of: {', '.join(LOCATIONS)}")

    for record in WeatherClient().get_forecast(location)[:3]:
        print(record)
