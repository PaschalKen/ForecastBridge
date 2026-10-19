from datetime import datetime, timezone

import boto3
import pytest
from moto import mock_aws

from app.storage import SnapshotStore
from tests.test_weather import SAMPLE_DATA

TWO_THIRTY_PM = datetime(2026, 10, 17, 14, 30, 5, tzinfo=timezone.utc)


@pytest.fixture
def s3(monkeypatch):
    """A fake, in-memory S3 with a bucket called test-bucket."""
    # Fake credentials, so these tests can never touch real AWS
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")
    monkeypatch.delenv("AWS_PROFILE", raising=False)

    with mock_aws():
        client = boto3.client("s3")
        client.create_bucket(Bucket="test-bucket")
        yield client


def test_make_key_rounds_to_the_hour():
    key = SnapshotStore.make_key("portsmouth", TWO_THIRTY_PM)

    assert key == "raw/portsmouth/2026-10-17/14.json"


def test_save_then_load_returns_the_same_data(s3):
    store = SnapshotStore("test-bucket", s3)

    key = store.save("portsmouth", SAMPLE_DATA, TWO_THIRTY_PM)

    assert key == "raw/portsmouth/2026-10-17/14.json"
    assert store.load("portsmouth", TWO_THIRTY_PM) == SAMPLE_DATA


def test_load_later_in_the_same_hour_finds_the_snapshot(s3):
    store = SnapshotStore("test-bucket", s3)
    store.save("portsmouth", SAMPLE_DATA, TWO_THIRTY_PM)

    two_fifty_nine = datetime(2026, 10, 17, 14, 59, 0, tzinfo=timezone.utc)

    assert store.load("portsmouth", two_fifty_nine) == SAMPLE_DATA


def test_load_returns_none_when_nothing_saved_this_hour(s3):
    store = SnapshotStore("test-bucket", s3)
    store.save("portsmouth", SAMPLE_DATA, TWO_THIRTY_PM)

    three_pm = datetime(2026, 10, 17, 15, 0, 0, tzinfo=timezone.utc)

    assert store.load("portsmouth", three_pm) is None
    assert store.load("london", TWO_THIRTY_PM) is None
