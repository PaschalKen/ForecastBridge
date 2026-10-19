from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.controllers import forecast_controller, location_controller

STATIC_DIR = Path(__file__).parent / "static"

app = FastAPI(title="ForecastBridge")
app.include_router(forecast_controller.router)
app.include_router(location_controller.router)

# Serve the front end's files (app.js, style.css, ...) under /static/...
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

@app.get("/", include_in_schema=False)
def root():
    """The front end's main page."""
    return FileResponse(STATIC_DIR / "index.html")

@app.get("/health")
def health_check():
    return {"status": "ok"}
