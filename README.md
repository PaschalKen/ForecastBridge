# ForecastBridge

[![Tests](https://github.com/PaschalKen/ForecastBridge/actions/workflows/tests.yml/badge.svg)](https://github.com/PaschalKen/ForecastBridge/actions/workflows/tests.yml)

**[Live demo](https://4hgo4skmrmq4avm52lrgj23lzu0gatfn.lambda-url.eu-north-1.on.aws/)**

ForecastBridge is a small weather data platform on AWS. Every hour it collects forecasts for
UK cities from [Open-Meteo](https://open-meteo.com/), stores the raw data in Amazon S3, and
serves it through a FastAPI web API and a web page with a 48-hour chart.

I built it to learn Python and AWS, by putting together the parts of a real data service:
an API, tests, a scheduled data pipeline, cloud storage, permissions and monitoring.

## Features

- **Search any place:** type a place name to get suggestions from Open-Meteo's geocoding,
  with four featured UK cities as quick buttons. The page remembers the last place you viewed.
- **Web page:** choose a place to see the current hour's temperature, chance of rain and wind,
  and a 48-hour chart of temperature and rain. A "Show now" button highlights the current
  hour, and on phones the chart scrolls sideways.
- **How accurate? page** (`/how-accurate`): saved forecasts compared with what actually happened
  (Open-Meteo's historical weather), by how far ahead they were made: typical error, bias, how
  often they were within 2°, and how often "rain likely" and "dry" forecasts were right.
- **Forecast history:** click any hour on the chart to see how its forecast changed across the
  hourly snapshots in S3, e.g. "36h before it said 11.4°C, 0% rain; during that hour 10.9°C, 14%".
- **Feels like** under the temperature, a **UV index** card, and a **units** switch (°C and km/h, or °F and mph) that
  the page remembers.
- **Plain-language advice** for the next 12 hours, such as "Rain likely from 3pm (80%)",
  "Coldest at 6am: 4°C", "Take a jacket" and "High UV around 1pm: wear sunscreen", worked out
  from the forecast with tested rules.
- **REST API** with interactive docs at `/docs`.
- **Hourly collection:** a scheduled AWS Lambda job saves every city's forecast to S3 at 5 past
  each hour, building up a history.
- **Caching:** the API serves this hour's forecast from S3 when it has one, and only calls
  Open-Meteo when it doesn't. If Open-Meteo is down, cached forecasts are still served.
- **Resilience:** a failing city doesn't stop the others, and a storage problem never breaks
  an API request.
- **Monitoring:** an email alert if the hourly job fails.

## Architecture

```
Every hour at :05 UTC
  EventBridge Scheduler ──> Lambda: collector ──> Open-Meteo
                                     │
                                     └──> S3  raw/<city>/<date>/<hour>.json
                                                          ▲
Browser or phone                                          │ this hour's forecast
  ──> Lambda Function URL (HTTPS) ──> Lambda: API ────────┘ (on a miss: fetch from Open-Meteo, then save)
                                      FastAPI via Mangum, also serves the web page

CloudWatch: logs, plus an alarm that emails (SNS) if a collector run fails
```

| Part | Technology |
|------|------------|
| Language | Python 3.12 |
| API | FastAPI, run on Lambda with Mangum |
| Web page | HTML, CSS, JavaScript, Chart.js (no build step) |
| Storage | Amazon S3 |
| Compute and scheduling | AWS Lambda (arm64), EventBridge Scheduler |
| Monitoring | CloudWatch Logs and Alarms, SNS email |
| Tests | pytest, with moto for a fake S3 |

## API

| Endpoint | Returns |
|----------|---------|
| `GET /forecast?location=london` | 48 hourly records for today and tomorrow. 404 for an unknown city, 503 if Open-Meteo is unavailable |
| `GET /advice?location=london&units=metric` | Plain-language advice for the next 12 hours, e.g. `{"kind": "rain", "message": "Rain likely from 3pm (80%)"}` |
| `GET /history?location=london&time=2026-11-03T15:00` | What each saved hourly snapshot (up to 48 hours before) forecast for that hour, oldest first |
| `GET /accuracy?location=london&days=7` | How accurate the saved forecasts were over the last 1 to 14 days, by how far ahead they were made, plus an hourly forecast vs actual series |
| `GET /places?query=brighton` | Places matching a name, each with a `name` to use as `location`, a `label` and a `timezone` |
| `GET /locations` | The featured cities, in the same format |
| `GET /health` | `{"status": "ok"}` |
| `GET /docs` | Interactive API documentation |

Each record is one hour, in UK local time:

```json
{"time": "2026-10-21T09:00", "temperature_c": 12.4, "rain_chance_percent": 20, "wind_kph": 15.2}
```

`location` is a featured city (`portsmouth`, `london`, `manchester`, `edinburgh`) or a searched place,
such as `place-2654710` for Brighton, UK. Times are in the place's own time zone.

## Design decisions

- **Store raw, format on the way out.** S3 keeps Open-Meteo's response exactly as received.
  If the output format changes, all past data comes out in the new format too.
- **One file per city per hour,** keyed by the UTC hour. Saving twice in the same hour
  overwrites the same file, so there are no duplicates, and UTC avoids gaps when the clocks
  change.
- **Least-privilege permissions.** Each Lambda function has its own IAM role. The collector
  can only upload to `raw/`. The API can read and write `raw/`. The scheduler can only invoke
  the collector. GitHub's deploy user can only update the two functions' code.
- **Automatic deploys.** Merging to `master` runs the tests, then deploys both functions through
  GitHub Actions, using an encrypted, deploy-only AWS key.
- **Classes with injected dependencies.** `WeatherClient`, `SnapshotStore`, `Collector` and
  `ForecastController` receive what they depend on, so tests can pass in fakes instead of
  patching.
- **Tests never touch the internet or AWS.** They use hand-made sample data, fake classes,
  and moto's in-memory S3. GitHub Actions runs them on every push and pull request.

## Running it locally

Requires Python 3.12+. Open-Meteo needs no API key.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env              # set S3_BUCKET and AWS_PROFILE to enable caching
uvicorn app.main:app --reload     # http://127.0.0.1:8000
pytest                            # 118 tests
```

Without AWS credentials the app still works; it just doesn't cache.

See **[RUNBOOK.md](RUNBOOK.md)** for all commands, how to deploy changes to AWS, health checks
and troubleshooting.

## Project structure

```
app/
  main.py            FastAPI app: routes and the web page
  lambda_api.py      Lambda entry point for the API (Mangum)
  controllers/       /forecast and /advice (with S3 caching), /locations and /places
  weather.py         WeatherClient: fetches from Open-Meteo, formats hourly records
  geocoding.py       GeocodingClient: searches places and looks them up by id
  advice.py          Rules that turn hourly records into plain-language advice
  history.py         How the forecast for one hour changed across saved snapshots
  accuracy.py        Saved forecasts scored against recorded weather
  storage.py         SnapshotStore: saves and loads snapshots in S3
  collector.py       Collector and its Lambda entry point (hourly job)
  location.py        Location and the featured cities
  forecast.py        HourlyForecast record
  config.py          Settings from environment variables
  static/            Web pages: index.html + app.js, accuracy.html + accuracy.js, style.css
tests/               pytest tests
scripts/
  build_lambda.sh    Builds the Lambda deployment zips
.github/workflows/
  tests.yml          Runs the tests on GitHub on every push and pull request
  deploy.yml         On every change to master: tests, build, deploy both Lambda functions, check the live site
RUNBOOK.md           Running, deploying and troubleshooting
REQUIREMENTS.md      Feature list and status
```

## Possible next steps

- Compare several cities on one chart

The full list is in [REQUIREMENTS.md](REQUIREMENTS.md#6-future-ideas).

Weather data by [Open-Meteo](https://open-meteo.com/) (CC BY 4.0).
