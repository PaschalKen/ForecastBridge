import requests
from fastapi import APIRouter, Depends, HTTPException

from app.geocoding import GeocodingClient, get_geocoding
from app.location import LOCATIONS, Location

# Searches shorter than this return nothing: one letter matches too much to be useful
MIN_QUERY_LENGTH = 2

router = APIRouter()


@router.get("/locations")
def get_locations() -> list[Location]:
    """The featured cities, shown as quick buttons on the page."""
    return list(LOCATIONS.values())


@router.get("/places")
def search_places(query: str, geocoding: GeocodingClient = Depends(get_geocoding)) -> list[Location]:
    """Places matching a name, e.g. /places?query=brighton. Use a result's `name` as `location`
    in /forecast and /advice."""
    if len(query.strip()) < MIN_QUERY_LENGTH:
        return []
    try:
        return geocoding.search(query.strip())
    except requests.RequestException:
        raise HTTPException(status_code=503, detail="Place search is unavailable. Try again later.")
