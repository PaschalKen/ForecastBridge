from fastapi import FastAPI

from app.controllers import forecast_controller

app = FastAPI(title="ForecastBridge")
app.include_router(forecast_controller.router)

@app.get("/")
def root():
    return {"message": "Welcome to ForecastBridge!"}

@app.get("/health")
def health_check():
    return {"status": "ok"}
