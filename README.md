# ForecastBridge

ForecastBridge fetches hourly weather forecasts for UK locations from
[Open-Meteo](https://open-meteo.com/) and turns them into simple, consistent records.
The goal is to serve that data through an API hosted on AWS.

It is a learning project for Python and AWS.

## What it does

Open-Meteo returns each measurement as a separate list. ForecastBridge reshapes that into
one record per hour:

```json
{"time": "2026-10-16T09:00", "temperature_c": 12.4, "rain_chance_percent": 20, "wind_kph": 15.2}
```

Times are UK local time.

## Setup

Requires Python 3.12+. Open-Meteo needs no API key.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

## Usage

Print the next few hours of the Portsmouth forecast:

```bash
python -m app.weather
```

## Configuration

Settings are read from environment variables, or from `.env` locally.

| Variable | Default |
|----------|---------|
| `OPEN_METEO_URL` | `https://api.open-meteo.com/v1/forecast` |

## Roadmap

See [REQUIREMENTS.md](REQUIREMENTS.md) for planned features and progress.

Weather data by [Open-Meteo](https://open-meteo.com/) (CC BY 4.0).
