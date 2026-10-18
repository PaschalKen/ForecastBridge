import json
from datetime import datetime, timezone

import boto3

from app.config import S3_BUCKET

def build_key(location: str, dt: datetime) -> str:
    """Build the S3 key, e.g. raw/portsmouth/2026-10-17/14-30-05.json"""
    return f"raw/{location}/{dt.strftime('%Y-%m-%d')}/{dt.strftime('%H-%M-%S')}.json"

def save_snapshot_to_s3(location: str, data: dict) -> str:
    """Save raw forecast data to S3 and return the key it was saved under."""
    s3 = boto3.client("s3")
    key = build_key(location, datetime.now(timezone.utc))
    s3.put_object(Bucket=S3_BUCKET, Key=key, Body=json.dumps(data), ContentType="application/json")

    return key
