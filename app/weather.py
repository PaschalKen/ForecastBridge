import requests

URL = "https://api.open-meteo.com/v1/forecast"

def fetch_forecast(latitude: float, longitude: float) -> dict:
    params = {
        "latitude": latitude,
        "longitude": longitude,
        "hourly": "temperature_2m,precipitation_probability,wind_speed_10m",
        "forecast_days": 2,
        "timezone": "Europe/London"
    }

    response = requests.get(URL, params=params, timeout=10)
    response.raise_for_status()  # Raise an error for bad responses
    return response.json()

if __name__ == "__main__":
    data = fetch_forecast(50.8, -1.09)
    print(data["hourly"]["time"][:3])
    print(data["hourly"]["temperature_2m"][:3])
