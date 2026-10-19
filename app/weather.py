import sys

import requests

from app.config import OPEN_METEO_URL
from app.forecast import HourlyForecast
from app.location import LOCATIONS, Location


class WeatherClient:
    """Talks to Open-Meteo. One client is reused for every location."""

    def __init__(self, url: str = OPEN_METEO_URL, timeout: int = 10):
        self.url = url
        self.timeout = timeout

    def fetch_raw_forecast(self, location: Location) -> dict:
        """Open-Meteo's response exactly as received (the collector saves this)."""
        params = {
            "latitude": location.latitude,
            "longitude": location.longitude,
            "hourly": "temperature_2m,precipitation_probability,wind_speed_10m",
            "forecast_days": 2,
            "timezone": "Europe/London",
        }

        response = requests.get(self.url, params=params, timeout=self.timeout)
        response.raise_for_status()  # Raise an error for bad responses
        return response.json()

    def get_forecast(self, location: Location) -> list[HourlyForecast]:
        """Hourly records for one location (the API returns this)."""
        return self.format_forecast(self.fetch_raw_forecast(location))

    @staticmethod
    def format_forecast(data: dict) -> list[HourlyForecast]:
        """Turn Open-Meteo's separate hourly lists into one record per hour."""
        hourly = data["hourly"]
        records = []

        for time, temperature, rain_chance, wind in zip(
            hourly["time"],
            hourly["temperature_2m"],
            hourly["precipitation_probability"],
            hourly["wind_speed_10m"],
        ):
            records.append(HourlyForecast(
                time=time,
                temperature_c=temperature,
                rain_chance_percent=rain_chance,
                wind_kph=wind,  # Open-Meteo returns km/h by default
            ))

        return records


if __name__ == "__main__":
    # Usage: python -m app.weather london
    name = sys.argv[1] if len(sys.argv) > 1 else "portsmouth"
    location = Location.get_location(name)
    if location is None:
        sys.exit(f"Unknown location '{name}'. Try one of: {', '.join(LOCATIONS)}")

    for record in WeatherClient().get_forecast(location)[:3]:
        print(record)
