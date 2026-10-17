# AGENT.md

Context for AI coding assistants working on this repository.

## About this project

ForecastBridge is a learning project. The owner is learning Python and AWS from scratch
by building a weather data platform: fetch forecast data, tidy it, store it in the cloud,
and serve it through an API.

**Because the goal is learning:**
- Explain what code does and why, in plain language. Avoid unexplained jargon.
- Prefer hints and small steps over writing whole features, unless asked to write the code.
- Keep code simple and readable over clever or abstract.
- Do not skip ahead to later stages without being asked.

## Tech stack

- Python 3.12, in a virtual environment at `.venv/`
- `requests` for HTTP calls to the Open-Meteo API (free, no API key)
- FastAPI and uvicorn for the API
- pytest for tests
- Later: AWS (S3, Lambda, API Gateway, DynamoDB, CloudWatch)

## Layout

```
app/
  config.py    # settings, read from environment variables / .env
  locations.py # LOCATIONS: supported place names -> (latitude, longitude)
  weather.py   # fetch_forecast() calls Open-Meteo; format_forecast() reshapes the data
  main.py      # FastAPI app (Stage 3)
tests/
  test_weather.py   # format_forecast and fetch_forecast (requests.get is faked)
  test_main.py      # API routes via TestClient (fetch_forecast is faked)
pytest.ini          # pytest settings
requirements.txt  # Python packages: direct dependencies only, pinned
REQUIREMENTS.md   # feature requirements and their status
.env.example      # template for .env (the real .env is not committed)
```

## Commands

```bash
source .venv/bin/activate
pip install -r requirements.txt
python -m app.weather            # fetch and print a Portsmouth forecast
uvicorn app.main:app --reload    # run the API, docs at http://127.0.0.1:8000/docs
pytest                           # run tests
```

## Roadmap

- [x] Stage 0: Workspace, virtual environment, Git
- [x] Stage 1: Fetch a forecast from Open-Meteo
- [x] Stage 2: Tidy hourly data into one record per hour
- [ ] Stage 3: FastAPI app with `GET /health` and `GET /forecast?location=...` (404 done; 502 on provider failure still to do)
- [x] Stage 4: pytest tests that do not call the live weather service
- [ ] AWS 1: Account, billing alarm, IAM user (no root usage)
- [ ] AWS 2: Save forecast snapshots to S3
- [ ] AWS 3: Deploy the API to Lambda and API Gateway
- [ ] AWS 4: DynamoDB for fast lookups
- [ ] AWS 5: Logging, alarms, caching, automation

## Conventions

- Tidied records use the keys `time`, `temperature_c`, `rain_chance_percent`, `wind_kph`.
- Tests must not depend on the internet; use small hard-coded sample data.
- Pin versions in `requirements.txt`, and add new packages there when they are installed.
- Settings go in `app/config.py`, read with `os.getenv` and a sensible default. Add new ones to `.env.example`.
- Never commit secrets or AWS credentials.
- Update the roadmap in this file and the status in `REQUIREMENTS.md` when work is finished.
