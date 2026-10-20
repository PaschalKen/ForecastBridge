# ForecastBridge

ForecastBridge fetches hourly weather forecasts for UK locations from
[Open-Meteo](https://open-meteo.com/), stores them in Amazon S3, and serves them through
a FastAPI web API and a small web page with a 48-hour chart.

It is a learning project for Python and AWS.

## What it does

- **Web page** at `/`: pick a location to see the current hour's temperature, chance of rain
  and wind, plus a 48-hour chart (temperature line, rain bars). A "Show now" button
  highlights the current hour.
- **API**:

  | Endpoint | Returns |
  |----------|---------|
  | `GET /forecast?location=london` | 48 hourly records (404 for unknown locations, 503 if Open-Meteo is down) |
  | `GET /locations` | Supported location names |
  | `GET /health` | `{"status": "ok"}` |
  | `GET /docs` | Interactive API documentation |

  Each hourly record looks like this (times are UK local time):

  ```json
  {"time": "2026-10-19T09:00", "temperature_c": 12.4, "rain_chance_percent": 20, "wind_kph": 15.2}
  ```

- **Caching in S3**: the first request for a location in each hour fetches from Open-Meteo
  and saves the raw response to S3 as `raw/<location>/<YYYY-MM-DD>/<HH>.json` (UTC). Later
  requests that hour are served from S3. If S3 is unavailable, requests still work.
- **Collector**: saves a snapshot of every location in one go. It runs on AWS Lambda at 5 past
  every hour (EventBridge Scheduler), so the bucket builds up an hourly history on its own.
  One location failing doesn't stop the others.

Supported locations: Portsmouth, London, Manchester and Edinburgh (add more in
`app/location.py`).

## Setup

Requires Python 3.12+. Open-Meteo needs no API key.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env    # then fill in S3_BUCKET and AWS_PROFILE
```

Saving to S3 needs AWS credentials for an AWS CLI profile (named in `AWS_PROFILE`) that can
read and write the bucket. Without them, the app still works but nothing is cached.

## Usage

```bash
uvicorn app.main:app --reload       # web page at http://127.0.0.1:8000, API docs at /docs
python -m app.weather london        # print the next few hours for one location
python -m app.collector             # save a snapshot of every location to S3
pytest                              # run the tests (no internet or AWS needed)
./scripts/build_lambda.sh           # build build/collector.zip for the Lambda function
```

## Configuration

Settings are read from environment variables, or from `.env` locally.

| Variable | Purpose | Default |
|----------|---------|---------|
| `OPEN_METEO_URL` | Open-Meteo forecast endpoint | `https://api.open-meteo.com/v1/forecast` |
| `S3_BUCKET` | Bucket for forecast snapshots | none |
| `AWS_PROFILE` | AWS CLI profile to use locally (not set on Lambda) | none |

## Project structure

```
app/
  main.py          # FastAPI app: routers and the web page
  controllers/     # /forecast (with S3 caching) and /locations
  location.py      # Location and the list of supported places
  weather.py       # WeatherClient: talks to Open-Meteo
  forecast.py      # HourlyForecast record
  storage.py       # SnapshotStore: saves and loads snapshots in S3
  collector.py     # Collector and the Lambda handler
  static/          # web page: index.html, app.js, style.css (Chart.js)
tests/             # pytest, using fakes and moto instead of real services
```

## Roadmap

Next: put the API and web page online on AWS Lambda, then add CloudWatch alarms.
See [REQUIREMENTS.md](REQUIREMENTS.md) for all planned features and progress.

Weather data by [Open-Meteo](https://open-meteo.com/) (CC BY 4.0).
