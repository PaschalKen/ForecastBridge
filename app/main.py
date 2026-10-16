from fastapi import FastAPI

app = FastAPI(title="ForecastBridge")

@app.get("/")
def root():
    return {"message": "Welcome to ForecastBridge!"}

@app.get("/health")
def health_check():
    return {"status": "ok"}
