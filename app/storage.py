import json
from datetime import datetime, timezone

import boto3

from app.config import S3_BUCKET


class SnapshotStore:
    """Saves and loads raw forecast snapshots in an S3 bucket, one per location per hour."""

    def __init__(self, bucket: str, s3_client):
        self.bucket = bucket
        self.s3_client = s3_client

    @classmethod
    def from_config(cls) -> "SnapshotStore":
        """Build a store using the bucket from settings and a real S3 client."""
        return cls(S3_BUCKET, boto3.client("s3"))

    @staticmethod
    def make_key(location: str, dt: datetime) -> str:
        """Build the S3 key for the hour, e.g. raw/portsmouth/2026-10-17/14.json"""
        return f"raw/{location}/{dt.strftime('%Y-%m-%d')}/{dt.strftime('%H')}.json"

    def save(self, location: str, data: dict, when: datetime | None = None) -> str:
        """Save raw forecast data to S3 and return the key it was saved under.

        Saving twice in the same hour overwrites the same key, so there are never duplicates.
        """
        key = self.make_key(location, when or datetime.now(timezone.utc))
        self.s3_client.put_object(
            Bucket=self.bucket,
            Key=key,
            Body=json.dumps(data),
            ContentType="application/json",
        )

        return key

    def load(self, location: str, when: datetime | None = None) -> dict | None:
        """Return the snapshot saved for this location and hour, or None if there isn't one."""
        key = self.make_key(location, when or datetime.now(timezone.utc))
        try:
            response = self.s3_client.get_object(Bucket=self.bucket, Key=key)
        except self.s3_client.exceptions.NoSuchKey:
            return None

        with response["Body"] as body:
            return json.loads(body.read())
