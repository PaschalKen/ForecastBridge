import json
from datetime import datetime, timezone

import boto3
from moto import mock_aws

from app.storage import SnapshotStore
from tests.test_weather import SAMPLE_DATA


def test_make_key_uses_location_date_and_time():
    fixed_time = datetime(2026, 10, 17, 14, 30, 5, tzinfo=timezone.utc)

    key = SnapshotStore.make_key("portsmouth", fixed_time)

    assert key == "raw/portsmouth/2026-10-17/14-30-05.json"


def test_save_uploads_json_to_s3(monkeypatch):
    # Fake credentials, so this test can never touch real AWS
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")
    monkeypatch.delenv("AWS_PROFILE", raising=False)

    # Everything inside this block talks to moto's in-memory S3
    with mock_aws():
        s3 = boto3.client("s3")
        s3.create_bucket(Bucket="test-bucket")

        # Dependency injection: hand the store a test bucket and client
        store = SnapshotStore("test-bucket", s3)
        key = store.save("portsmouth", SAMPLE_DATA)

        body = s3.get_object(Bucket="test-bucket", Key=key)["Body"].read()
        assert json.loads(body) == SAMPLE_DATA
        assert key.startswith("raw/portsmouth/")
