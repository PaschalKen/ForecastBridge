import requests

from fastapi import FastAPI, HTTPException

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
    location = location.lower()

    if location not in LOCATIONS:
        raise HTTPException(
            status_code=404,
            detail=f"Location '{location}' not found.",
        )
    
    latitude, longitude = LOCATIONS[location]

    try:
        data = fetch_forecast(latitude, longitude)
    except requests.RequestException:
        raise HTTPException(
            status_code=503,
            detail=f"Weather provider is unavailable. Try again later.",
        )
    
    return format_forecast(data)
