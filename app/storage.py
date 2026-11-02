import json
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

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

    def snapshots_between(self, location: str, start: datetime, end: datetime) -> list[tuple[datetime, dict]]:
        """Every snapshot saved from `start` to `end` (UTC hours, inclusive), oldest first,
        as (hour it was saved, raw forecast) pairs."""
        times = self._snapshot_times(location, start, end)

        # Load several at once: each is a separate S3 request, and waiting for them one by one
        # would take seconds. boto3 clients are safe to share between threads.
        with ThreadPoolExecutor(max_workers=8) as pool:
            loaded = list(pool.map(lambda when: (when, self.load(location, when)), times))

        return [(when, raw) for when, raw in loaded if raw is not None]

    def _snapshot_times(self, location: str, start: datetime, end: datetime) -> list[datetime]:
        """The hours (UTC) that have a saved snapshot between start and end, by listing each
        day's "folder" in S3 (e.g. raw/london/2026-11-02/) rather than guessing keys."""
        paginator = self.s3_client.get_paginator("list_objects_v2")
        times = []

        day = start.date()
        while day <= end.date():
            prefix = f"raw/{location}/{day:%Y-%m-%d}/"
            for key in paginator.paginate(Bucket=self.bucket, Prefix=prefix).search("Contents[].Key"):
                hour = (key or "").rsplit("/", 1)[-1].removesuffix(".json")
                if not hour.isdigit():  # empty day, or an old-style key such as 18-11-17.json
                    continue
                when = datetime(day.year, day.month, day.day, int(hour), tzinfo=timezone.utc)
                if start <= when <= end:
                    times.append(when)
            day += timedelta(days=1)

        return sorted(times)
