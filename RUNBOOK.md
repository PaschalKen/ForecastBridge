# ForecastBridge runbook

How to run ForecastBridge locally, deploy changes to AWS, and check that it's working.

All AWS resources are in **eu-north-1 (Stockholm)**. This account's Free plan only allows
that region. Before creating or changing anything in the console, check that the address bar
says `eu-north-1`.

---

## 1. First-time setup

```bash
cd ~/Desktop/ForecastBridge
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Fill in `.env`:

```
S3_BUCKET=forecastbridge-snapshots-108248327537
AWS_PROFILE=forecastbridge
```

`AWS_PROFILE` names an AWS CLI profile in `~/.aws/` with access to the bucket. Check it works:

```bash
aws sts get-caller-identity --profile forecastbridge
```

---

## 2. Run locally

Each new terminal first needs:

```bash
cd ~/Desktop/ForecastBridge
source .venv/bin/activate
```

| Task | Command |
|------|---------|
| Start the web app and API | `uvicorn app.main:app --reload` then open http://127.0.0.1:8000 |
| API docs | http://127.0.0.1:8000/docs |
| Open it on your phone (same Wi-Fi) | `uvicorn app.main:app --reload --host 0.0.0.0`, find the Mac's IP with `ipconfig getifaddr en0`, open `http://<ip>:8000` on the phone |
| Stop the server | `Ctrl + C` |
| Print a forecast for one place | `python -m app.weather london` |
| Save a snapshot of every location to S3 | `python -m app.collector` |
| Run the tests | `pytest` (or `pytest -v` to list each test) |

`--host 0.0.0.0` makes the server reachable by anything on your network, so only use it on a
network you trust.

Running the app locally reads and writes the **real** S3 bucket (the tests never do).

---

## 3. Deploy a change to AWS

There is no automatic deployment. A change goes live in four steps.

### Step 1: Test locally

```bash
pytest
```

Don't deploy if anything fails. GitHub also runs the tests on every push and pull request
(the **Actions** tab on GitHub, or the tick/cross next to each commit), so check that's green too.

### Step 2: Build the zips

```bash
./scripts/build_lambda.sh
```

This creates two files:

| File | Upload to | Contains |
|------|-----------|----------|
| `build/api.zip` | Lambda `forecastbridge-api` | `app/` including the web page, plus FastAPI, Mangum, requests, python-dotenv |
| `build/collector.zip` | Lambda `forecastbridge-collector` | `app/` without the web page, plus requests, python-dotenv |

The libraries are downloaded for **Linux ARM64, Python 3.12** to match the functions, so don't
change either function's runtime or architecture without changing the script too.

### Step 3: Upload to the function(s) that changed

| You changed | Upload `api.zip` | Upload `collector.zip` |
|-------------|:---:|:---:|
| `app/static/` (web page) | ✅ | |
| `app/controllers/`, `app/main.py`, `app/lambda_api.py` | ✅ | |
| `app/collector.py` | | ✅ |
| `app/advice.py` | ✅ | |
| `app/weather.py`, `app/storage.py`, `app/location.py`, `app/forecast.py`, `app/config.py` | ✅ | ✅ |
| A library version in `requirements.txt` | ✅ if it's in `api.zip` | ✅ if it's in `collector.zip` |

**From the terminal (recommended).** The account's rules block *creating* resources from the CLI,
but updating a function's code is allowed:

```bash
# API (web page + /forecast, /advice, ...)
aws lambda update-function-code --function-name forecastbridge-api \
  --zip-file fileb://build/api.zip --profile forecastbridge
aws lambda wait function-updated --function-name forecastbridge-api --profile forecastbridge

# Collector (hourly job)
aws lambda update-function-code --function-name forecastbridge-collector \
  --zip-file fileb://build/collector.zip --profile forecastbridge
aws lambda wait function-updated --function-name forecastbridge-collector --profile forecastbridge
```

The `wait` command returns once the new code is live.

**Or from the console:** open the function (Stockholm), then **Code**, **Update**, **.zip file**,
choose the zip, and click **Save** in the upload dialog. Wait for the green "Successfully updated"
banner; closing the dialog without saving leaves the old code running.

**Confirm the upload happened** (CodeSize should match the zip's size, LastModified should be now):

```bash
aws lambda get-function-configuration --function-name forecastbridge-api \
  --query '{LastModified:LastModified,CodeSize:CodeSize}' --profile forecastbridge
ls -l build/api.zip
```

Browsers may keep an old copy of `app.js`: after a front-end change, hard refresh the live site
(Cmd + Shift + R).

### Step 4: Check it

**API:** use the console's **Test** tab with the saved `health` and `forecast-london` events
(below), then open the live site:

```bash
URL=https://4hgo4skmrmq4avm52lrgj23lzu0gatfn.lambda-url.eu-north-1.on.aws
curl -s $URL/health
curl -s "$URL/forecast?location=london" | head -c 200
```

**Collector:** **Test** tab with any event (the collector ignores it). Expect
`"failed": []` and `Run finished: 4 saved, 0 failed` in the log output.

Test event for the API (`health`). For `forecast-london`, change both paths to `/forecast`
and `rawQueryString` to `location=london`:

```json
{
  "version": "2.0",
  "routeKey": "$default",
  "rawPath": "/health",
  "rawQueryString": "",
  "headers": { "host": "test.lambda-url.eu-north-1.on.aws" },
  "requestContext": {
    "http": { "method": "GET", "path": "/health", "protocol": "HTTP/1.1", "sourceIp": "127.0.0.1", "userAgent": "console-test" },
    "domainName": "test.lambda-url.eu-north-1.on.aws",
    "stage": "$default"
  },
  "isBase64Encoded": false
}
```

### Then commit

```bash
git add -A
git commit -m "Describe the change"
git push
```

---

## 4. Check everything is healthy

**Is the collector running every hour?** Each hour should have 4 files, one per location:

```bash
aws s3 ls s3://forecastbridge-snapshots-108248327537/raw/ --recursive --profile forecastbridge | tail -8
```

**Has anything failed?** The alarm `forecastbridge-collector-errors` emails you if a collector
run fails for every location. To see its state:

```bash
aws cloudwatch describe-alarms --alarm-names forecastbridge-collector-errors \
  --query 'MetricAlarms[0].StateValue' --output text --profile forecastbridge
```

**Logs:** CloudWatch, then **Log groups**, then `/aws/lambda/forecastbridge-collector` or
`/aws/lambda/forecastbridge-api`. The collector's logs are kept for 7 days.

**Pause the hourly collector:** EventBridge, then **Scheduler**, then `forecastbridge-hourly`,
then **Disable**.

---

## 5. What's deployed

All in eu-north-1, account `108248327537`.

| Resource | Details |
|----------|---------|
| S3 bucket `forecastbridge-snapshots-108248327537` | Raw Open-Meteo responses at `raw/<location>/<YYYY-MM-DD>/<HH>.json` (UTC hour). Public access blocked |
| Lambda `forecastbridge-api` | Python 3.12, arm64, 512 MB, 15 s timeout. Handler `app.lambda_api.handler`. Env `S3_BUCKET` |
| Function URL | https://4hgo4skmrmq4avm52lrgj23lzu0gatfn.lambda-url.eu-north-1.on.aws/ (public, auth NONE) |
| IAM role `forecastbridge-api-role` | `AWSLambdaBasicExecutionRole` + inline `forecastbridge-api-s3-readwrite`: Get/PutObject on `raw/*`, ListBucket on prefix `raw/*` |
| Lambda `forecastbridge-collector` | Python 3.12, arm64, 256 MB, 1 min timeout. Handler `app.collector.handler`. Env `S3_BUCKET` |
| IAM role `forecastbridge-collector-role` | `AWSLambdaBasicExecutionRole` + inline `forecastbridge-collector-s3-write`: PutObject on `raw/*` only |
| EventBridge Scheduler `forecastbridge-hourly` | `cron(5 * * * ? *)`, UTC, 3 retries, max event age 1 hour |
| CloudWatch alarm `forecastbridge-collector-errors` | Collector `Errors` > 0 in an hour, emails via SNS topic `forecastbridge-alerts` |
| CloudWatch log retention | 7 days on `/aws/lambda/forecastbridge-collector` |

---

## 6. Common problems

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| "Region unavailable" in the console | You're outside Stockholm | Switch to eu-north-1 (check the address bar) |
| `AccessDenied ... service control policy` from the CLI | The account's organization rule blocks creating resources from the CLI | Create resources in the console; the CLI can still read and write files in the bucket |
| Lambda error `Unable to import module 'app...'` | Wrong handler, or zip built incorrectly | Check the handler setting, rebuild with the script, re-upload |
| Lambda error about `pydantic_core` or another compiled library | Function isn't Python 3.12 on arm64 | Match the function's runtime and architecture to the build script |
| API logs "Could not read cached forecast" | The API role can't read the bucket | Check the inline policy on `forecastbridge-api-role` |
| Collector reports a location in `failed` | Open-Meteo or S3 problem for that location | Read the traceback in the collector's CloudWatch logs |
| Local app works but nothing appears in S3 | `.env` missing `S3_BUCKET` or `AWS_PROFILE`, or the profile has no access | Check `.env` and `aws sts get-caller-identity --profile forecastbridge` |
