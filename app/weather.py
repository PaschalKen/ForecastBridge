import requests

from app.config import OPEN_METEO_URL

def fetch_forecast(latitude: float, longitude: float) -> dict:
    params = {
        "latitude": latitude,
        "longitude": longitude,
        "hourly": "temperature_2m,precipitation_probability,wind_speed_10m",
        "forecast_days": 2,
        "timezone": "Europe/London"
    }

    response = requests.get(OPEN_METEO_URL,params=params, timeout=10)
    response.raise_for_status()  # Raise an error for bad responses
    return response.json()

def format_forecast(data: dict) -> list[dict]:
    """Turn Open-Meteo's separate hourly lists into one record per hour."""
    hourly = data["hourly"]
    records = []

    for time, temperature, rain_chance, wind in zip(
        hourly["time"],
        hourly["temperature_2m"],
        hourly["precipitation_probability"],
        hourly["wind_speed_10m"],
    ):
        records.append({
            "time": time,
            "temperature_c": temperature,
            "rain_chance_percent": rain_chance,
            "wind_kph": wind,  # Open-Meteo returns km/h by default
        })

    return records

if __name__ == "__main__":
    data = fetch_forecast(50.8, -1.09)
    for record in format_forecast(data)[:3]:
        print(record)
