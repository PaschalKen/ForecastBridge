from fastapi import FastAPI

from app.locations import LOCATIONS
from app.weather import fetch_forecast, format_forecast

app = FastAPI(title="ForecastBridge")

@app.get("/")
def root():
    return {"message": "Welcome to ForecastBridge!"}

@app.get("/health")
def health_check():
    return {"status": "ok"}

@app.get("/forecast")
def get_forecast(location: str):
    latitude, longitude = LOCATIONS[location]
    data = fetch_forecast(latitude, longitude)
    return format_forecast(data)
