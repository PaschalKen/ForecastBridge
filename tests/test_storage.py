import json
from datetime import datetime, timezone

import boto3
from moto import mock_aws

from app import storage
from tests.test_weather import SAMPLE_DATA


def test_build_key_uses_location_date_and_time():
    fixed_time = datetime(2026, 10, 17, 14, 30, 5, tzinfo=timezone.utc)

    key = storage.build_key("portsmouth", fixed_time)

    assert key == "raw/portsmouth/2026-10-17/14-30-05.json"


def test_save_snapshot_uploads_json_to_s3(monkeypatch):
    # Fake credentials, so this test can never touch real AWS
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")

    # storage.py read S3_BUCKET when it was imported, so replace it there
    monkeypatch.setattr(storage, "S3_BUCKET", "test-bucket")

    # Everything inside this block talks to moto's in-memory S3
    with mock_aws():
        s3 = boto3.client("s3")
        s3.create_bucket(Bucket="test-bucket")

        key = storage.save_snapshot_to_s3("portsmouth", SAMPLE_DATA)

        body = s3.get_object(Bucket="test-bucket", Key=key)["Body"].read()
        assert json.loads(body) == SAMPLE_DATA
        assert key.startswith("raw/portsmouth/")
