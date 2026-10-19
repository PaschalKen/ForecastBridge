from fastapi import APIRouter

from app.location import LOCATIONS

router = APIRouter()
class LocationController:

    @router.get("/locations")
    def get_locations() -> list[str]:
        """Return a list of all supported locations."""
        return [location.name for location in LOCATIONS.values()]
