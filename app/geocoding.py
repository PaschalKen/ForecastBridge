from functools import lru_cache

import requests

from app.config import GEOCODING_URL
from app.location import PLACE_PREFIX, Location


class GeocodingClient:
    """Talks to Open-Meteo's geocoding API: turns place names into Locations."""

    def __init__(self, url: str = GEOCODING_URL, timeout: int = 10):
        self.url = url
        self.timeout = timeout
        self._places: dict[int, Location | None] = {}  # id -> place, so repeat lookups skip the network

    def search(self, query: str, count: int = 5) -> list[Location]:
        """Places matching a name, most populous first, e.g. "brighton" -> Brighton UK, Brighton US, ..."""
        params = {"name": query, "count": count, "language": "en", "format": "json"}
        response = requests.get(f"{self.url}/search", params=params, timeout=self.timeout)
        response.raise_for_status()
        # With no matches, Open-Meteo leaves the "results" key out entirely
        return [self.to_location(result) for result in response.json().get("results", [])]

    def get(self, place_id: int) -> Location | None:
        """One place by its geocoding id, or None if no place has that id."""
        if place_id not in self._places:
            response = requests.get(f"{self.url}/get", params={"id": place_id}, timeout=self.timeout)
            if response.status_code == 400:  # Open-Meteo's answer for an unknown id
                self._places[place_id] = None
            else:
                response.raise_for_status()
                self._places[place_id] = self.to_location(response.json())
        return self._places[place_id]

    @staticmethod
    def to_location(result: dict) -> Location:
        """One geocoding result -> Location, labelled e.g. "Brighton, England, United Kingdom"."""
        # Some places have no region (admin1), and some have a region with the same name as the place
        parts = [result["name"], result.get("admin1"), result.get("country")]
        label_parts = []
        for part in parts:
            if part and part not in label_parts:
                label_parts.append(part)

        return Location(
            name=f"{PLACE_PREFIX}{result['id']}",
            latitude=result["latitude"],
            longitude=result["longitude"],
            label=", ".join(label_parts),
            timezone=result.get("timezone", "UTC"),
        )


@lru_cache
def get_geocoding() -> GeocodingClient:
    """One client for the whole app, so its place cache is shared between requests."""
    return GeocodingClient()
