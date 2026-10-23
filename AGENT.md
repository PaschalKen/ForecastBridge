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
  location.py  # Location dataclass, LOCATIONS registry, Location.get_location(name)
  forecast.py  # HourlyForecast dataclass (one hour of weather)
  weather.py   # WeatherClient: fetch_raw_forecast(location), get_forecast(location)
  storage.py   # SnapshotStore: save(location_name, data) to S3
  collector.py # Collector (all locations -> S3) and handler() for Lambda
  main.py      # FastAPI app: wires routers together
  controllers/
    forecast_controller.py  # ForecastController (logic) + /forecast route (HTTP)
    location_controller.py  # /locations route
  static/      # front end, served by FastAPI: index.html at /, the rest under /static/
    index.html, app.js, style.css  # plain HTML/JS + Chart.js from CDN, no build step
tests/
  test_weather.py   # WeatherClient and Location (requests.get is faked)
  test_main.py      # API routes via TestClient (controller dependency overridden with fake clients)
  test_collector.py # Collector with fake weather client and fake store
  test_storage.py   # S3 snapshot saving, using moto's fake S3
pytest.ini          # pytest settings
requirements.txt  # Python packages: direct dependencies only, pinned
RUNBOOK.md        # running locally, deploying to AWS, health checks, troubleshooting
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
- [x] Stage 3: FastAPI app with `/health`, `/locations`, `/forecast` (404 unknown location, 503 provider down)
- [x] Stage 4: pytest tests that do not call the live weather service
- [x] Stage 5: Front end served by FastAPI (dropdown, now cards, 48-hour chart, Show now button)
- [x] AWS 1: Account (Free plan, locked to eu-north-1 Stockholm), billing alarm, IAM user `paschal-admin` used via CLI profile `forecastbridge`
- [x] AWS 2: Save forecast snapshots to S3; API caches per location per hour
- [x] AWS 3: Collector on Lambda, run hourly by EventBridge Scheduler
- [x] AWS 4: API and front end on Lambda (Mangum + public Function URL)
- [x] AWS 5: CloudWatch log retention (7 days) and an error alarm emailing via SNS
- [ ] Future ideas: see section 6 of `REQUIREMENTS.md` (search any place, plain-language advice,
  compare cities, forecast accuracy, history chart, units toggle, CI)

AWS account notes:
- The Free plan locks this project to **eu-north-1 (Stockholm)**. Create everything there.
- An organization rule (SCP) blocks creating resources (e.g. buckets) from the CLI. Create
  infrastructure in the AWS console; code can then read and write data in it.

Deployed resources, deployment steps and troubleshooting are in `RUNBOOK.md`; keep it up to
date when anything on AWS changes.

## Conventions

- S3 snapshot keys are hourly: `raw/<location>/<YYYY-MM-DD>/<HH>.json` (UTC). The API checks for this hour's key before calling Open-Meteo, and saves on a miss.
- Tidied records use the keys `time`, `temperature_c`, `rain_chance_percent`, `wind_kph`.
- Tests must not depend on the internet; use small hard-coded sample data.
- Tests must also pass without a `.env` file or AWS credentials: GitHub Actions
  (`.github/workflows/tests.yml`) runs them on a clean machine for every push and pull request.
- Pin versions in `requirements.txt`, and add new packages there when they are installed.
- Settings go in `app/config.py`, read with `os.getenv` and a sensible default. Add new ones to `.env.example`.
- Never commit secrets or AWS credentials.
- Update the roadmap in this file and the status in `REQUIREMENTS.md` when work is finished.
