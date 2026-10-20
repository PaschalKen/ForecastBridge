import pytest
import requests

from app.collector import CollectionFailedError, Collector
from app.location import Location
from tests.test_weather import SAMPLE_DATA

PORTSMOUTH = Location("portsmouth", 50.80, -1.09)
LONDON = Location("london", 51.51, -0.13)


class FakeWeatherClient:
    """Records which locations were fetched, returns sample data, fails for names in `broken`."""

    def __init__(self, broken=()):
        self.fetched = []
        self.broken = set(broken)

    def fetch_raw_forecast(self, location):
        self.fetched.append(location.name)
        if location.name in self.broken:
            raise requests.RequestException(f"{location.name} unavailable")
        return SAMPLE_DATA


class FakeStore:
    """Keeps 'saved' snapshots in a list instead of S3."""

    def __init__(self):
        self.saved = []

    def save(self, location_name, data):
        self.saved.append((location_name, data))
        return f"raw/{location_name}/test.json"


def test_collect_fetches_and_saves_every_location():
    weather, store = FakeWeatherClient(), FakeStore()

    result = Collector(weather, store, [PORTSMOUTH, LONDON]).collect()

    assert weather.fetched == ["portsmouth", "london"]
    assert store.saved == [("portsmouth", SAMPLE_DATA), ("london", SAMPLE_DATA)]
    assert result.saved == ["raw/portsmouth/test.json", "raw/london/test.json"]
    assert result.failed == []


def test_one_failing_location_does_not_stop_the_others():
    weather, store = FakeWeatherClient(broken={"portsmouth"}), FakeStore()

    result = Collector(weather, store, [PORTSMOUTH, LONDON]).collect()

    assert weather.fetched == ["portsmouth", "london"]  # London was still tried
    assert result.saved == ["raw/london/test.json"]
    assert result.failed == ["portsmouth"]


def test_every_location_failing_raises():
    weather, store = FakeWeatherClient(broken={"portsmouth", "london"}), FakeStore()

    with pytest.raises(CollectionFailedError):
        Collector(weather, store, [PORTSMOUTH, LONDON]).collect()
