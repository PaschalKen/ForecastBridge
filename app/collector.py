from app.location import LOCATIONS, Location
from app.storage import SnapshotStore
from app.weather import WeatherClient


class Collector:
    """Fetches every location's raw forecast and saves each snapshot to S3."""

    def __init__(self, weather: WeatherClient, store: SnapshotStore, locations: list[Location]):
        self.weather = weather
        self.store = store
        self.locations = locations

    def collect(self) -> list[str]:
        """Save a snapshot for every location, return the saved keys."""
        saved_keys = []

        for location in self.locations:
            data = self.weather.fetch_raw_forecast(location)
            key = self.store.save(location.name, data)
            saved_keys.append(key)

        return saved_keys


def handler(event, context):
    """Entry point AWS Lambda calls on each scheduled run."""
    collector = Collector(WeatherClient(), SnapshotStore.from_config(), list(LOCATIONS.values()))
    keys = collector.collect()
    return {"saved": len(keys), "keys": keys}


if __name__ == "__main__":
    print(handler(None, None))
