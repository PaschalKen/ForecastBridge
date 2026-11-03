from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.controllers import forecast_controller, location_controller

STATIC_DIR = Path(__file__).parent / "static"

app = FastAPI(title="ForecastBridge")
app.include_router(forecast_controller.router)
app.include_router(location_controller.router)

# Serve the front end's files (app.js, style.css, ...) under /static/...
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.middleware("http")
async def always_check_for_new_front_end(request: Request, call_next):
    """Tell browsers to check for a newer page, app.js or style.css before using a saved copy.

    Without this, browsers guess how long their saved copy is fine and can keep showing an old
    stylesheet after a change. "no-cache" doesn't stop caching: the browser keeps its copy, asks
    "has this changed?" on each load, and the server answers "304 Not Modified" (no file sent)
    when it hasn't, so it stays fast.
    """
    response = await call_next(request)
    if request.url.path in ("/", "/how-accurate") or request.url.path.startswith("/static/"):
        response.headers["Cache-Control"] = "no-cache"
    return response


@app.get("/", include_in_schema=False)
def root():
    """The front end's main page."""
    return FileResponse(STATIC_DIR / "index.html")

@app.get("/how-accurate", include_in_schema=False)
def accuracy_page():
    """How accurate the saved forecasts were (the data comes from GET /accuracy)."""
    return FileResponse(STATIC_DIR / "accuracy.html")

@app.get("/health")
def health_check():
    return {"status": "ok"}
