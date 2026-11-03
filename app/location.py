from dataclasses import dataclass

# Searched places use "place-<geocoding id>" as their name, e.g. "place-2654710" for Brighton, UK
PLACE_PREFIX = "place-"


@dataclass(frozen=True)
class Location:
    name: str             # unique key used in URLs and S3: "london", or "place-2654710" for a searched place
    latitude: float
    longitude: float
    label: str = ""       # shown to people, e.g. "Brighton, England, United Kingdom"
    timezone: str = "Europe/London"  # the place's own time zone; forecast times are in it

    def __post_init__(self):
        # Featured cities don't need an explicit label: "london" -> "London".
        # (The dataclass is frozen, so set the field through object.__setattr__.)
        if not self.label:
            object.__setattr__(self, "label", self.name.title())

    @staticmethod
    def get_location(name: str) -> "Location | None":
        """Find a featured city by name, ignoring capitals. None if it isn't one."""
        return LOCATIONS.get(name.lower())


def place_id_from(name: str) -> int | None:
    """The geocoding id in "place-2654710" (or just "2654710"), or None if it isn't a place id."""
    value = name.lower().removeprefix(PLACE_PREFIX)
    return int(value) if value.isdigit() else None


# Featured cities: shown as quick buttons and collected every hour.
# To add one, add a line here (coordinates to 2 decimal places).
_ALL_LOCATIONS = [
    Location("portsmouth", 50.80, -1.09),
    Location("london", 51.51, -0.13),
    Location("manchester", 53.48, -2.24),
    Location("edinburgh", 55.95, -3.19),
]

# name -> Location, built from the list above
LOCATIONS = {location.name: location for location in _ALL_LOCATIONS}
