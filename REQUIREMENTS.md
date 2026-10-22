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
| 6.7 | Automatic tests on GitHub | GitHub Actions runs `pytest` on every push | `tests/` |
| 6.8 | AI weather summary | A short, friendly summary of the next 24 hours written by an AI model (Claude), e.g. "A dry, bright morning in London, with showers likely after 3pm. Take an umbrella if you're out this evening." See the details below | 6.2, `HourlyForecast` records, the hourly collector, `SnapshotStore` |

### 6.8 AI weather summary: details

**Why:** the chart shows the numbers, but most people just want to know what the day will be
like. A language model can turn 24 hourly records into two or three sentences of plain
English, which simple rules (6.2) would find hard to make sound natural.

| # | Requirement | Status |
|---|-------------|--------|
| 6.8.1 | Send the tidied hourly records for the next 24 hours (not the raw Open-Meteo data) to the Claude API and ask for a summary of at most three sentences | ⬜ |
| 6.8.2 | Generate summaries in the hourly collector, once per city per hour, so page visits never trigger an AI call. This keeps costs small and predictable (4 cities × 24 hours = 96 calls a day) | ⬜ |
| 6.8.3 | Save each summary in S3 next to its snapshot, e.g. `summaries/<city>/<date>/<hour>.json`, and include the model name and time it was written | ⬜ |
| 6.8.4 | New endpoint `GET /summary?location=<name>` returns this hour's summary, and the web page shows it above the "Right now" cards | ⬜ |
| 6.8.5 | The feature is optional: if no API key is set, or the AI call fails or times out, the page still works and simply hides the summary (or falls back to the rule based advice from 6.2) | ⬜ |
| 6.8.6 | The API key lives in an environment variable on the collector Lambda only, is added to `.env.example` without a value, and is never sent to the browser or committed to Git | ⬜ |
| 6.8.7 | Use a small, fast model, keep the prompt short, and cap the length of the reply to keep each call cheap | ⬜ |
| 6.8.8 | Tests use a fake summariser class (injected like `WeatherClient`), so they never call the real AI service | ⬜ |
| 6.8.9 | The summary must only describe what is in the forecast data: no invented warnings, and a note on the page that it is AI generated | ⬜ |

**Stretch ideas:** ask a question about the weather ("Is Saturday good for a bike ride in
Manchester?") answered from the stored forecast; or explain the forecast accuracy results from
6.4 in plain language.

## Out of scope (for now)

- User accounts or logins
