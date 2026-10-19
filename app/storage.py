import json
from datetime import datetime, timezone

import boto3

from app.config import S3_BUCKET


class SnapshotStore:
    """Saves raw forecast snapshots to an S3 bucket."""

    def __init__(self, bucket: str, s3_client):
        self.bucket = bucket
        self.s3_client = s3_client

    @classmethod
    def from_config(cls) -> "SnapshotStore":
        """Build a store using the bucket from settings and a real S3 client."""
        return cls(S3_BUCKET, boto3.client("s3"))

    @staticmethod
    def make_key(location: str, dt: datetime) -> str:
        """Build the S3 key, e.g. raw/portsmouth/2026-10-17/14-30-05.json"""
        return f"raw/{location}/{dt.strftime('%Y-%m-%d')}/{dt.strftime('%H-%M-%S')}.json"

    def save(self, location: str, data: dict) -> str:
        """Save raw forecast data to S3 and return the key it was saved under."""
        key = self.make_key(location, datetime.now(timezone.utc))
        self.s3_client.put_object(
            Bucket=self.bucket,
            Key=key,
            Body=json.dumps(data),
            ContentType="application/json",
        )
        
        return key
