"""Utilities for loading station metadata."""

from functools import lru_cache
from pathlib import Path
from sysconfig import get_path

_SOURCE_STATION_TABLE_PATH = (
    Path(__file__).resolve().parents[3] / "parm" / "sonde.land.tbl"
)
_INSTALLED_STATION_TABLE_PATH = (
    Path(get_path("data")) / "share" / "geode" / "parm" / "sonde.land.tbl"
)


@lru_cache(maxsize=1)
def load_station_coordinates() -> dict[str, tuple[float, float, float]]:
    """Load WMO station coordinates from the local GEMPAK station table.

    Returns
    -------
    dict[str, tuple[float, float, float]]
        Mapping from WMO station ID to latitude, longitude, and elevation in
        decimal degrees and metres above mean sea level.

    Raises
    ------
    FileNotFoundError
        If the station table is not present in the source tree or installed data path.
    ValueError
        If a station row is malformed, has invalid coordinates, or repeats an ID.

    Examples
    --------
    ``load_station_coordinates()["72365"]`` returns
    ``(35.04, -106.62, 1619.0)``.
    """
    station_table_path = next(
        (
            path
            for path in (
                _SOURCE_STATION_TABLE_PATH,
                _INSTALLED_STATION_TABLE_PATH,
            )
            if path.is_file()
        ),
        None,
    )
    if station_table_path is None:
        raise FileNotFoundError(
            "FATAL ERROR: sonde.land.tbl was not found in the source tree or "
            f"installed data path {_INSTALLED_STATION_TABLE_PATH}."
        )

    station_coordinates: dict[str, tuple[float, float, float]] = {}
    with station_table_path.open(encoding="ascii") as station_table:
        for line_number, line in enumerate(station_table, start=1):
            if not line.strip() or line.lstrip().startswith("!"):
                continue
            if len(line.rstrip("\r\n")) < 67:
                raise ValueError(
                    f"Malformed station table row {line_number}: expected coordinate fields."
                )

            station_id = line[10:15].strip()
            try:
                latitude = int(line[55:60]) / 100.0
                longitude = int(line[61:67]) / 100.0
                elevation = float(int(line[68:73]))
            except ValueError as error:
                raise ValueError(
                    f"Invalid station position on table row {line_number}."
                ) from error

            if len(station_id) != 5 or not station_id.isdigit():
                raise ValueError(
                    f"Invalid WMO station ID on table row {line_number}: {station_id!r}."
                )
            if not -90 <= latitude <= 90 or not -180 <= longitude <= 180:
                raise ValueError(
                    f"Out-of-range station coordinates on table row {line_number}."
                )
            if not -500 <= elevation <= 9000:
                raise ValueError(
                    f"Out-of-range station elevation on table row {line_number}."
                )
            if station_id in station_coordinates:
                raise ValueError(f"Duplicate WMO station ID in table: {station_id}.")

            station_coordinates[station_id] = (latitude, longitude, elevation)

    return station_coordinates
