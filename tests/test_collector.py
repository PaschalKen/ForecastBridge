from app.collector import Collector
from app.location import Location
from tests.test_weather import SAMPLE_DATA


class FakeWeatherClient:
    """Records which locations were fetched, returns sample data."""

    def __init__(self):
        self.fetched = []

    def fetch_raw_forecast(self, location):
        self.fetched.append(location.name)
        return SAMPLE_DATA


class FakeStore:
    """Keeps 'saved' snapshots in a list instead of S3."""

    def __init__(self):
        self.saved = []

    def save(self, location_name, data):
        self.saved.append((location_name, data))
        return f"raw/{location_name}/test.json"


def test_collect_fetches_and_saves_every_location():
    locations = [Location("portsmouth", 50.80, -1.09), Location("london", 51.51, -0.13)]
    weather, store = FakeWeatherClient(), FakeStore()

    keys = Collector(weather, store, locations).collect()

    assert weather.fetched == ["portsmouth", "london"]
    assert store.saved == [("portsmouth", SAMPLE_DATA), ("london", SAMPLE_DATA)]
    assert keys == ["raw/portsmouth/test.json", "raw/london/test.json"]
