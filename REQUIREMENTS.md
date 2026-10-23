# ForecastBridge requirements

What the project should do when finished. Python packages live in `requirements.txt`;
this file is about features.

Status: ✅ done · 🔨 in progress · ⬜ not started

## 1. Forecast data

| # | Requirement | Status |
|---|-------------|--------|
| 1.1 | Fetch hourly forecasts from Open-Meteo for a given latitude and longitude | ✅ |
| 1.2 | Return temperature (°C), chance of rain (%) and wind speed (km/h) for each hour | ✅ |
| 1.3 | Tidy the provider's data into one record per hour | ✅ |
| 1.4 | Support a fixed list of UK locations by name (Portsmouth, London, Manchester, Edinburgh) | ✅ |
| 1.5 | Fail clearly, not silently, when the weather provider is down or slow (timeout) | ✅ |
| 1.6 | Look up any place by name using Open-Meteo's geocoding API, instead of only the fixed list | ⬜ |

## 2. API

| # | Requirement | Status |
|---|-------------|--------|
| 2.1 | `GET /health` returns `{"status": "ok"}` | ✅ |
| 2.2 | `GET /forecast?location=<name>` returns the tidied hourly records | ✅ |
| 2.3 | Unknown locations return a 404 with a helpful message | ✅ |
| 2.4 | If the weather provider fails, return a 503 error rather than crashing | ✅ |
| 2.5 | Interactive API documentation at `/docs` | ✅ |

## 3. Quality

| # | Requirement | Status |
|---|-------------|--------|
| 3.1 | Automated tests with pytest | ✅ |
| 3.2 | Tests never call the live weather service | ✅ |
| 3.3 | Settings (URLs, bucket names, etc.) come from environment variables, not hard-coded | ✅ |
| 3.4 | No secrets or credentials committed to Git | ✅ |

## 4. Cloud (AWS)

| # | Requirement | Status |
|---|-------------|--------|
| 4.1 | AWS account with billing alarm and a non-root IAM user | ✅ |
| 4.2 | Save raw forecast snapshots to S3, organised by location and date | ✅ |
| 4.3 | Run the API and web page on Lambda, reachable over HTTPS (Function URL) | ✅ |
| 4.4 | Store tidied forecasts in DynamoDB for fast lookups | ⬜ |
| 4.5 | Serve cached forecasts instead of calling the provider on every request (S3, one snapshot per location per hour) | ✅ |
| 4.6 | Fetch forecasts automatically on a schedule (e.g. hourly) | ✅ |
| 4.7 | Logs and alarms in CloudWatch, so failures are noticed | ✅ |

## 5. Front end

| # | Requirement | Status |
|---|-------------|--------|
| 5.1 | Web page served by the API at `/` (no separate server, no build step) | ✅ |
| 5.2 | Location dropdown filled from `GET /locations` | ✅ |
| 5.3 | "Right now" cards: temperature, chance of rain, wind | ✅ |
| 5.4 | 48-hour chart: temperature line, rain chance bars | ✅ |
| 5.5 | Clear loading and error messages (unknown location, provider down) | ✅ |

## 6. Future ideas

Features to make ForecastBridge more interactive and more useful. Each builds on what already
exists.

| # | Idea | What it means | Builds on |
|---|------|---------------|-----------|
| 6.1 | Search any place | A search box instead of the fixed dropdown, using Open-Meteo's free geocoding API to turn a place name into coordinates (see 1.6) | `Location.get_location`, `/locations` |
| 6.2 | Plain-language advice | Turn the numbers into short advice, e.g. "Rain likely from 3pm", "Coldest at 6am", "Take a jacket" | `HourlyForecast` records, the "Right now" cards |
| 6.3 | Compare cities | Show two or three cities on one chart, side by side | `/forecast`, the Chart.js chart |
| 6.4 | Forecast accuracy | Use the hourly history in S3 to compare what was forecast for an hour with what was forecast closer to (or at) that hour, and show how reliable forecasts are | The hourly `raw/` snapshots |
| 6.5 | Forecast history chart | Pick an hour and see how its forecast changed across past snapshots | The hourly `raw/` snapshots, `SnapshotStore.load` |
| 6.6 | Units toggle | Switch between °C/°F and km/h/mph, remembered in the browser (`localStorage`) | `app.js` |
| 6.7 | Automatic tests on GitHub ✅ | GitHub Actions runs `pytest` on every push and pull request (`.github/workflows/tests.yml`) | `tests/` |

## Out of scope (for now)

- User accounts or logins
