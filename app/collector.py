import logging
from dataclasses import dataclass, field

from app.location import LOCATIONS, Location
from app.storage import SnapshotStore
from app.weather import WeatherClient

logger = logging.getLogger(__name__)


@dataclass
class CollectionResult:
    """What one collection run managed to do."""
    saved: list[str] = field(default_factory=list)   # S3 keys written
    failed: list[str] = field(default_factory=list)  # location names that failed


class CollectionFailedError(Exception):
    """Raised when every location failed, so Lambda marks the run as failed."""


class Collector:
    """Fetches every location's raw forecast and saves each snapshot to S3."""

    def __init__(self, weather: WeatherClient, store: SnapshotStore, locations: list[Location]):
        self.weather = weather
        self.store = store
        self.locations = locations

    def collect(self) -> CollectionResult:
        """Save a snapshot for every location; one failing location doesn't stop the rest."""
        result = CollectionResult()

        for location in self.locations:
            try:
                data = self.weather.fetch_raw_forecast(location)
                key = self.store.save(location.name, data)
            # Catch everything here on purpose: an unexpected error for one city must not
            # stop the others. logger.exception records the full traceback for debugging.
            except Exception:
                logger.exception("Failed to collect %s", location.name)
                result.failed.append(location.name)
            else:
                logger.info("Saved %s to %s", location.name, key)
                result.saved.append(key)

        if result.failed and not result.saved:
            raise CollectionFailedError(f"Every location failed: {', '.join(result.failed)}")

        return result


def handler(event, context):
    """Entry point AWS Lambda calls on each scheduled run."""
    logging.getLogger().setLevel(logging.INFO)  # Lambda's default level hides INFO messages

    collector = Collector(WeatherClient(), SnapshotStore.from_config(), list(LOCATIONS.values()))
    result = collector.collect()

    logger.info("Run finished: %d saved, %d failed", len(result.saved), len(result.failed))
    return {"saved": result.saved, "failed": result.failed}


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    print(handler(None, None))
