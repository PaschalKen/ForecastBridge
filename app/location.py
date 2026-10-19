from dataclasses import dataclass

@dataclass(frozen=True)
class Location:
    name: str
    latitude: float
    longitude: float

    @staticmethod
    def get_location(name: str) -> "Location | None":
        """Find a supported location by name, ignoring capitals. None if unknown."""
        return LOCATIONS.get(name.lower())

# Supported locations. To add one, add a line here (coordinates to 2 decimal places).
_ALL_LOCATIONS = [
    Location("portsmouth", 50.80, -1.09),
    Location("london", 51.51, -0.13),
    Location("manchester", 53.48, -2.24),
    Location("edinburgh", 55.95, -3.19),
]

# name -> Location, built from the list above
LOCATIONS = {location.name: location for location in _ALL_LOCATIONS}
