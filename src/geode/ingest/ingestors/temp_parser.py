import re
from dataclasses import dataclass
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path
from sysconfig import get_path

import numpy as np
import xarray as xr

from geode.utils.conversion_units import (
    ASSUMED_ASCENT_RATE_METERS_PER_SECOND,
    CELSIUS_TO_KELVIN,
    EARTH_RADIUS_METERS,
    KNOTS_TO_METERS_PER_SECOND,
)

_SECTION_MARKER = re.compile(r"\b(TTAA|TTBB|TTCC|TTDD)\b", re.IGNORECASE)
_SOURCE_STATION_TABLE_PATH = (
    Path(__file__).resolve().parents[4] / "parm" / "sonde.land.tbl"
)
_INSTALLED_STATION_TABLE_PATH = (
    Path(get_path("data")) / "share" / "geode" / "parm" / "sonde.land.tbl"
)
_MANDATORY_PRESSURES = {
    "00": 100000.0,
    "92": 92500.0,
    "85": 85000.0,
    "70": 70000.0,
    "50": 50000.0,
    "40": 40000.0,
    "30": 30000.0,
    "25": 25000.0,
    "20": 20000.0,
    "15": 15000.0,
    "10": 10000.0,
}
_MANDATORY_HEIGHT_OFFSETS = {
    "00": 0,
    "92": 0,
    "85": 1000,
    "70": 3000,
    "50": 5000,
    "40": 7000,
    "30": 9000,
    "25": 10000,
    "20": 12000,
    "15": 15000,
    "10": 20000,
}


@lru_cache(maxsize=1)
def _load_station_coordinates() -> dict[str, tuple[float, float, float]]:
    """Load WMO station coordinates from the local GEMPAK station table.

    Parameters
    ----------
    None

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
    ``_load_station_coordinates()["72365"]`` returns
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

    station_coordinates = {}
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


@dataclass(frozen=True)
class _TempSection:
    code: str
    time_group: str
    station_id: str
    code_groups: tuple[str, ...]


@dataclass(frozen=True)
class _Observation:
    pressure: float
    height: float | None
    temperature: float | None
    dew_point_temperature: float | None
    wind_direction: float | None
    wind_speed: float | None
    raw_code: str


def _wind_components(
    wind_direction: float | None, wind_speed: float | None
) -> tuple[float | None, float | None]:
    """Convert meteorological wind direction and speed to east/north components.

    Parameters
    ----------
    wind_direction : float | None
        Direction the wind comes from, in degrees clockwise from north.
    wind_speed : float | None
        Wind speed in metres per second.

    Returns
    -------
    tuple[float | None, float | None]
        Eastward U and northward V components in metres per second.

    Examples
    --------
    A 10 m/s wind from west returns ``(10.0, 0.0)``.
    """
    if wind_speed is None:
        return None, None
    if wind_direction is None:
        if wind_speed == 0.0:
            return 0.0, 0.0
        return None, None

    direction_radians = np.deg2rad(wind_direction)
    eastward_wind = -wind_speed * np.sin(direction_radians)
    northward_wind = -wind_speed * np.cos(direction_radians)
    return float(eastward_wind), float(northward_wind)


def _estimate_drift_positions(
    observations: list[_Observation],
    launch_latitude: float,
    launch_longitude: float,
    launch_elevation: float,
) -> tuple[np.ndarray, np.ndarray]:
    """Estimate observation positions from winds and a fixed ascent rate.

    Parameters
    ----------
    observations : list[_Observation]
        TEMP observations in report order.
    launch_latitude : float
        Launch latitude in decimal degrees.
    launch_longitude : float
        Launch longitude in decimal degrees.
    launch_elevation : float
        Launch elevation in metres above mean sea level.

    Returns
    -------
    tuple[numpy.ndarray, numpy.ndarray]
        Estimated latitude and longitude arrays in decimal degrees. Positions
        for levels without usable heights remain NaN.

    Examples
    --------
    Wind components are linearly interpolated between levels and held at the
    nearest level outside the profile. Integration uses
    ``delta_time = delta_height / 5 m s-1``.
    """
    estimated_latitudes = np.full(len(observations), np.nan)
    estimated_longitudes = np.full(len(observations), np.nan)
    if not np.isfinite([launch_latitude, launch_longitude, launch_elevation]).all():
        return estimated_latitudes, estimated_longitudes

    target_heights = {}
    wind_levels = []
    for index, observation in enumerate(observations):
        is_surface_observation = observation.raw_code.startswith("99")
        if is_surface_observation:
            height_above_launch = 0.0
        elif observation.height is not None:
            height_above_launch = observation.height - launch_elevation
            if height_above_launch < 0.0:
                target_heights[index] = 0.0
                continue
        else:
            continue

        target_heights[index] = height_above_launch
        eastward_wind, northward_wind = _wind_components(
            observation.wind_direction, observation.wind_speed
        )
        if eastward_wind is None or northward_wind is None:
            continue

        wind_levels.append((height_above_launch, eastward_wind, northward_wind))

    if not wind_levels:
        for index, height in target_heights.items():
            if height == 0.0:
                estimated_latitudes[index] = launch_latitude
                estimated_longitudes[index] = launch_longitude
        return estimated_latitudes, estimated_longitudes

    wind_levels.sort(key=lambda level: level[0])
    wind_heights = np.asarray([level[0] for level in wind_levels])
    unique_heights, inverse_indices = np.unique(wind_heights, return_inverse=True)
    eastward_winds = np.asarray([level[1] for level in wind_levels])
    northward_winds = np.asarray([level[2] for level in wind_levels])
    level_counts = np.bincount(inverse_indices)
    mean_eastward_winds = (
        np.bincount(inverse_indices, weights=eastward_winds) / level_counts
    )
    mean_northward_winds = (
        np.bincount(inverse_indices, weights=northward_winds) / level_counts
    )

    integration_heights = np.unique(
        np.concatenate(
            ([0.0], unique_heights, np.asarray(list(target_heights.values())))
        )
    )
    integration_eastward_winds = np.interp(
        integration_heights, unique_heights, mean_eastward_winds
    )
    integration_northward_winds = np.interp(
        integration_heights, unique_heights, mean_northward_winds
    )
    height_increments = np.diff(integration_heights)
    eastward_displacement = np.concatenate(
        (
            [0.0],
            np.cumsum(
                (integration_eastward_winds[:-1] + integration_eastward_winds[1:])
                * 0.5
                * height_increments
                / ASSUMED_ASCENT_RATE_METERS_PER_SECOND
            ),
        )
    )
    northward_displacement = np.concatenate(
        (
            [0.0],
            np.cumsum(
                (integration_northward_winds[:-1] + integration_northward_winds[1:])
                * 0.5
                * height_increments
                / ASSUMED_ASCENT_RATE_METERS_PER_SECOND
            ),
        )
    )

    launch_latitude_radians = np.deg2rad(launch_latitude)
    for index, height in target_heights.items():
        node_index = np.searchsorted(integration_heights, height)
        eastward = eastward_displacement[node_index]
        northward = northward_displacement[node_index]
        angular_distance = np.hypot(eastward, northward) / EARTH_RADIUS_METERS
        bearing = np.arctan2(eastward, northward)
        latitude_radians = np.arcsin(
            np.sin(launch_latitude_radians) * np.cos(angular_distance)
            + np.cos(launch_latitude_radians)
            * np.sin(angular_distance)
            * np.cos(bearing)
        )
        longitude_radians = np.deg2rad(launch_longitude) + np.arctan2(
            np.sin(bearing)
            * np.sin(angular_distance)
            * np.cos(launch_latitude_radians),
            np.cos(angular_distance)
            - np.sin(launch_latitude_radians) * np.sin(latitude_radians),
        )
        estimated_latitudes[index] = np.rad2deg(latitude_radians)
        estimated_longitudes[index] = (
            np.rad2deg(longitude_radians) + 180.0
        ) % 360.0 - 180.0

    return estimated_latitudes, estimated_longitudes


class TempParser:
    """Decode supported TTAA levels in WMO TEMP reports."""

    def parse(
        self,
        report_text: str,
        reference_datetime: datetime | None = None,
        include_raw_code: bool = False,
    ) -> dict[str, xr.DataTree]:
        """Decode TEMP observations into separate surface and upper-air trees.

        Parameters
        ----------
        report_text : str
            ASCII TEMP report or bulletin text.
        reference_datetime : datetime | None
            Timezone-aware receipt/acquisition timestamp used to resolve the
            section's day and hour to the nearest valid calendar date.
        include_raw_code : bool, default=False
            Include original code groups as a single ``MetaData/rawCode``
            string per observation.

        Returns
        -------
        dict[str, xarray.DataTree]
            Trees keyed by ``surface`` and/or ``upper_air``, each containing
            ``MetaData`` and ``ObsValue`` child datasets. Station coordinates
            are looked up from ``parm/sonde.land.tbl``; unmatched IDs have NaN
            coordinates.

        Raises
        ------
        ValueError
            If the reference timestamp is missing or invalid, no TEMP
            sections are present, or a section header is malformed.

        Examples
        --------
        ``parse(text, datetime(2026, 1, 8, 18, tzinfo=UTC))`` returns
        flat ``MetaData`` and ``ObsValue`` groups.
        """
        if reference_datetime is None:
            raise ValueError(
                "A timezone-aware reference_datetime is required to resolve "
                "TEMP day/hour groups."
            )
        if reference_datetime.tzinfo is None or reference_datetime.utcoffset() is None:
            raise ValueError("reference_datetime must be timezone-aware.")
        reference_datetime = reference_datetime.astimezone(UTC)
        receipt_datetime = datetime.now(UTC)

        sections = self._extract_sections(report_text)
        if not sections:
            raise ValueError("No WMO TEMP sections found in TAC input.")

        section_datasets = {"surface": [], "upper_air": []}
        location_start = 0
        for section in sections:
            category_datasets = self._decode_section(
                section,
                reference_datetime,
                receipt_datetime,
                location_start,
                include_raw_code,
            )
            for category, dataset in category_datasets.items():
                section_datasets[category].append(dataset)
            location_start += sum(
                dataset.sizes["Location"] for dataset in category_datasets.values()
            )

        metadata_variables = [
            "dateTime",
            "receiptTime",
            "stationIdentification",
            "latitude",
            "longitude",
            "estimatedLatitude",
            "estimatedLongitude",
            "pressure",
            "height",
            "reportType",
        ]
        if include_raw_code:
            metadata_variables.append("rawCode")
        observation_variables = [
            "temperature",
            "dewPointTemperature",
            "windEastward",
            "windNorthward",
        ]
        category_trees = {}
        for category, datasets in section_datasets.items():
            if not datasets:
                continue

            combined = xr.concat(
                datasets,
                dim="Location",
                data_vars="all",
                coords="minimal",
                compat="override",
                combine_attrs="override",
            ).assign_coords(
                Location=np.arange(sum(ds.sizes["Location"] for ds in datasets))
            )
            tree = xr.DataTree(
                dataset=xr.Dataset(
                    attrs={
                        "format": "WMO TEMP",
                        "category": category,
                        "section_count": len(datasets),
                        "observation_count": combined.sizes["Location"],
                        "reference_datetime": reference_datetime.isoformat(),
                        "history": "Decoded from raw WMO TEMP TAC groups by GEODE.",
                        "assumed_ascent_rate_m_s": ASSUMED_ASCENT_RATE_METERS_PER_SECOND,
                        "position_estimation_method": "Trapezoidal integration of layer winds.",
                    }
                ),
                name=category,
            )
            tree["MetaData"] = xr.DataTree(
                dataset=combined[metadata_variables], name="MetaData"
            )
            tree["ObsValue"] = xr.DataTree(
                dataset=combined[observation_variables], name="ObsValue"
            )
            category_trees[category] = tree

        return category_trees

    @classmethod
    def _decode_section(
        cls,
        section: _TempSection,
        reference_datetime: datetime,
        receipt_datetime: datetime,
        location_start: int,
        include_raw_code: bool,
    ) -> dict[str, xr.Dataset]:
        """Decode a TEMP section into an xarray dataset.

        Parameters
        ----------
        section : _TempSection
            Parsed TEMP header and coded groups.
        reference_datetime : datetime
            Timezone-aware UTC reference timestamp.
        receipt_datetime : datetime
            UTC timestamp captured when parsing began.
        location_start : int
            First ``Location`` index assigned to this section.
        include_raw_code : bool
            Whether original code groups should be emitted as ``rawCode``.

        Returns
        -------
        dict[str, xarray.Dataset]
            Datasets keyed by ``surface`` and/or ``upper_air``.

        Raises
        ------
        NotImplementedError
            If the section uses a TEMP form not yet decoded here.
        ValueError
            If a supported section contains malformed mandatory-level groups.

        Examples
        --------
        TTAA sections are decoded through their surface and standard pressure
        levels. TTCC and significant-level sections are not decoded yet.
        """
        if section.code != "TTAA":
            raise NotImplementedError(
                f"Decoding {section.code} sections is not yet supported; only TTAA is decoded."
            )
        if len(section.time_group) != 5 or not section.time_group.isdigit():
            raise ValueError(f"Malformed TEMP YYGGi time group: {section.time_group}")
        if section.time_group[-1] not in {"0", "1"}:
            raise ValueError(
                f"Unsupported TEMP wind-speed unit indicator: {section.time_group[-1]}"
            )

        observations = cls._decode_ttaa_levels(section)
        if not observations:
            raise ValueError(
                f"TEMP section {section.code} has no decodable mandatory levels."
            )

        observation_count = len(observations)
        latitude, longitude, station_elevation = _load_station_coordinates().get(
            section.station_id, (np.nan, np.nan, np.nan)
        )
        estimated_latitudes, estimated_longitudes = _estimate_drift_positions(
            observations, latitude, longitude, station_elevation
        )
        observation_datetime = cls._resolve_datetime(
            section.time_group, reference_datetime
        )
        timestamp = np.datetime64(observation_datetime.replace(tzinfo=None), "ns")
        receipt_timestamp = np.datetime64(receipt_datetime.replace(tzinfo=None), "ns")
        wind_components = [
            _wind_components(observation.wind_direction, observation.wind_speed)
            for observation in observations
        ]
        data_vars = {
            "dateTime": (
                "Location",
                np.full(observation_count, timestamp, dtype="datetime64[ns]"),
                {
                    "standard_name": "time",
                    "timezone": "UTC",
                    "units": "seconds since 1970-01-01T00:00:00Z",
                },
            ),
            "receiptTime": (
                "Location",
                np.full(observation_count, receipt_timestamp, dtype="datetime64[ns]"),
                {
                    "standard_name": "time",
                    "timezone": "UTC",
                    "units": "seconds since 1970-01-01T00:00:00Z",
                },
            ),
            "stationIdentification": (
                "Location",
                [section.station_id] * observation_count,
            ),
            "latitude": (
                "Location",
                np.full(observation_count, latitude),
                {"units": "degrees_north", "standard_name": "latitude"},
            ),
            "longitude": (
                "Location",
                np.full(observation_count, longitude),
                {"units": "degrees_east", "standard_name": "longitude"},
            ),
            "estimatedLatitude": (
                "Location",
                estimated_latitudes,
                {
                    "units": "degrees_north",
                    "standard_name": "latitude",
                    "long_name": "Estimated balloon latitude",
                    "comment": "Wind-profile estimate assuming 5 m s-1 ascent.",
                },
            ),
            "estimatedLongitude": (
                "Location",
                estimated_longitudes,
                {
                    "units": "degrees_east",
                    "standard_name": "longitude",
                    "long_name": "Estimated balloon longitude",
                    "comment": "Wind-profile estimate assuming 5 m s-1 ascent.",
                },
            ),
            "pressure": (
                "Location",
                [observation.pressure for observation in observations],
                {"units": "Pa", "standard_name": "air_pressure"},
            ),
            "height": (
                "Location",
                [cls._as_float(observation.height) for observation in observations],
                {"units": "m", "standard_name": "geopotential_height"},
            ),
            "reportType": ("Location", [section.code] * observation_count),
            "temperature": (
                "Location",
                [
                    cls._as_float(observation.temperature)
                    for observation in observations
                ],
                {"units": "K", "standard_name": "air_temperature"},
            ),
            "dewPointTemperature": (
                "Location",
                [
                    cls._as_float(observation.dew_point_temperature)
                    for observation in observations
                ],
                {"units": "K", "standard_name": "dew_point_temperature"},
            ),
            "windEastward": (
                "Location",
                [cls._as_float(components[0]) for components in wind_components],
                {"units": "m s-1", "standard_name": "eastward_wind"},
            ),
            "windNorthward": (
                "Location",
                [cls._as_float(components[1]) for components in wind_components],
                {"units": "m s-1", "standard_name": "northward_wind"},
            ),
        }
        if include_raw_code:
            data_vars["rawCode"] = (
                "Location",
                [observation.raw_code for observation in observations],
            )

        section_dataset = xr.Dataset(
            data_vars=data_vars,
            coords={
                "Location": range(location_start, location_start + observation_count)
            },
        )
        surface_mask = np.asarray(
            [observation.raw_code.startswith("99") for observation in observations]
        )
        category_datasets = {}
        for category, mask in (
            ("surface", surface_mask),
            ("upper_air", ~surface_mask),
        ):
            if mask.any():
                category_datasets[category] = section_dataset.isel(
                    Location=np.flatnonzero(mask)
                )

        return category_datasets

    @staticmethod
    def _resolve_datetime(time_group: str, reference_datetime: datetime) -> datetime:
        """Resolve TEMP's day/hour to the nearest valid adjacent-month date.

        Parameters
        ----------
        time_group : str
            Five-digit TEMP YYGGi group. When YY exceeds 50, subtract 50 to
            obtain the day of month; this encoding indicates knot units.
        reference_datetime : datetime
            Timezone-aware timestamp used as the month/year anchor.

        Returns
        -------
        datetime
            Resolved UTC observation time at the start of the indicated hour.

        Raises
        ------
        ValueError
            If the day/hour is invalid or no adjacent month has that day.

        Examples
        --------
        An ``80181`` group represents day 30 at 18 UTC. A day 31 observation
        anchored near 1 March resolves to the closest valid adjacent-month date.
        """
        if len(time_group) != 5 or not time_group.isdigit():
            raise ValueError(f"Malformed TEMP YYGGi time group: {time_group}")
        encoded_day = int(time_group[:2])
        day = encoded_day - 50 if encoded_day > 50 else encoded_day
        hour = int(time_group[2:4])
        if not 1 <= day <= 31 or not 0 <= hour <= 23:
            raise ValueError(f"Invalid TEMP day/hour group: {time_group}")
        if reference_datetime.tzinfo is None or reference_datetime.utcoffset() is None:
            raise ValueError("reference_datetime must be timezone-aware.")

        reference_utc = reference_datetime.astimezone(UTC)
        reference_month = reference_utc.year * 12 + reference_utc.month - 1
        candidates = []
        for month_offset in (-1, 0, 1):
            year, month_zero_based = divmod(reference_month + month_offset, 12)
            try:
                candidates.append(
                    datetime(
                        year,
                        month_zero_based + 1,
                        day,
                        hour,
                        tzinfo=UTC,
                    )
                )
            except ValueError:
                continue
        if not candidates:
            raise ValueError(
                f"TEMP day {day} is invalid in the reference month and adjacent months."
            )

        return min(candidates, key=lambda candidate: abs(candidate - reference_utc))

    @staticmethod
    def _wind_speed_unit_indicator(time_group: str) -> str:
        """Determine the TEMP wind speed units from its time group.

        Parameters
        ----------
        time_group : str
            Five-digit TEMP YYGGi group.

        Returns
        -------
        str
            ``"1"`` for knots or ``"0"`` for metres per second.

        Raises
        ------
        ValueError
            If the time group is malformed or its unit indicator is unsupported.

        Examples
        --------
        A day code of ``80`` signals day 30 and wind speed in knots.
        """
        if len(time_group) != 5 or not time_group.isdigit():
            raise ValueError(f"Malformed TEMP YYGGi time group: {time_group}")
        if time_group[-1] not in {"0", "1"}:
            raise ValueError(
                f"Unsupported TEMP wind-speed unit indicator: {time_group[-1]}"
            )
        if int(time_group[:2]) > 50:
            return "1"
        return time_group[-1]

    @classmethod
    def _decode_ttaa_levels(cls, section: _TempSection) -> list[_Observation]:
        """Decode surface, mandatory, tropopause, and maximum-wind groups.

        Parameters
        ----------
        section : _TempSection
            TTAA TEMP section.

        Returns
        -------
        list[_Observation]
            Decoded levels in report order, with all values on the same schema.

        Raises
        ------
        ValueError
            If the surface group sequence or a recognized level group is
            malformed.

        Examples
        --------
        A ``70068 03634 23013`` sequence yields the 70,000 Pa level with
        temperature, dew-point depression, and wind values. Valid 88PPP and
        77PPP groups append tropopause and maximum-wind observations.
        """
        groups = section.code_groups
        observations = []
        group_index = 0

        if groups and groups[0].startswith("99"):
            surface_group = groups[0]
            if len(surface_group) != 5 or not surface_group.isdigit():
                raise ValueError(
                    f"Malformed TEMP surface pressure group: {surface_group}"
                )
            pressure_code = int(surface_group[2:])
            pressure = (100000.0 if pressure_code < 500 else 90000.0) + (
                pressure_code * 10.0
            )
            temperature_group = groups[1] if len(groups) > 1 else "/////"
            wind_group = groups[2] if len(groups) > 2 else "/////"
            temperature, dew_point_temperature = cls._decode_temperature_group(
                temperature_group
            )
            wind_direction, wind_speed = cls._decode_wind_group(
                wind_group, section.time_group
            )
            observations.append(
                _Observation(
                    pressure=pressure,
                    height=None,
                    temperature=temperature,
                    dew_point_temperature=dew_point_temperature,
                    wind_direction=wind_direction,
                    wind_speed=wind_speed,
                    raw_code=f"{surface_group} {temperature_group} {wind_group}",
                )
            )
            group_index = 3

        while group_index < len(groups):
            level_code = groups[group_index]
            if level_code in {"31313", "51515", "21212"}:
                break

            if level_code.startswith("88"):
                pressure = cls._decode_extra_layer_pressure(level_code)
                if pressure is None:
                    group_index += 1
                    continue
                if group_index + 2 >= len(groups):
                    raise ValueError(
                        f"TEMP tropopause level {level_code} is missing its "
                        "temperature or wind group."
                    )
                temperature_code = groups[group_index + 1]
                wind_code = groups[group_index + 2]
                temperature, dew_point_temperature = cls._decode_temperature_group(
                    temperature_code
                )
                wind_direction, wind_speed = cls._decode_wind_group(
                    wind_code, section.time_group
                )
                observations.append(
                    _Observation(
                        pressure=pressure,
                        height=None,
                        temperature=temperature,
                        dew_point_temperature=dew_point_temperature,
                        wind_direction=wind_direction,
                        wind_speed=wind_speed,
                        raw_code=f"{level_code} {temperature_code} {wind_code}",
                    )
                )
                group_index += 3
                continue

            if level_code.startswith("77"):
                pressure = cls._decode_extra_layer_pressure(level_code)
                if pressure is None:
                    group_index += 1
                    continue
                if group_index + 1 >= len(groups):
                    raise ValueError(
                        f"TEMP maximum-wind level {level_code} is missing its "
                        "wind group."
                    )
                wind_code = groups[group_index + 1]
                wind_direction, wind_speed = cls._decode_wind_group(
                    wind_code, section.time_group
                )
                observations.append(
                    _Observation(
                        pressure=pressure,
                        height=None,
                        temperature=None,
                        dew_point_temperature=None,
                        wind_direction=wind_direction,
                        wind_speed=wind_speed,
                        raw_code=f"{level_code} {wind_code}",
                    )
                )
                group_index += 2
                continue

            pressure = _MANDATORY_PRESSURES.get(level_code[:2])
            if pressure is None:
                group_index += 1
                continue
            if len(level_code) != 5 or not level_code.isdigit():
                raise ValueError(f"Malformed TEMP mandatory-level group: {level_code}")
            if group_index + 2 >= len(groups):
                raise ValueError(
                    f"TEMP level {level_code} is missing its temperature or wind group."
                )

            temperature, dew_point_temperature = cls._decode_temperature_group(
                groups[group_index + 1]
            )
            wind_direction, wind_speed = cls._decode_wind_group(
                groups[group_index + 2], section.time_group
            )
            observations.append(
                _Observation(
                    pressure=pressure,
                    height=cls._decode_mandatory_level_height(level_code),
                    temperature=temperature,
                    dew_point_temperature=dew_point_temperature,
                    wind_direction=wind_direction,
                    wind_speed=wind_speed,
                    raw_code=(
                        f"{level_code} {groups[group_index + 1]} "
                        f"{groups[group_index + 2]}"
                    ),
                )
            )
            group_index += 3

        return observations

    @staticmethod
    def _decode_mandatory_level_height(group: str) -> float | None:
        """Decode geopotential height from a mandatory pressure-level group.

        Parameters
        ----------
        group : str
            Five-digit mandatory-level group, such as ``70068``.

        Returns
        -------
        float | None
            Geopotential height in metres, or ``None`` for a missing/unknown
            height code.

        Raises
        ------
        ValueError
            If the group is malformed.

        Examples
        --------
        ``70068`` decodes to 3068 m.
        """
        if len(group) != 5 or not group.isdigit():
            raise ValueError(f"Malformed TEMP mandatory-level group: {group}")

        pressure_code = group[:2]
        height_offset = _MANDATORY_HEIGHT_OFFSETS.get(pressure_code)
        if height_offset is None:
            return None
        encoded_height = int(group[2:])
        if encoded_height == 999:
            return None
        return float(height_offset + encoded_height)

    @staticmethod
    def _decode_extra_layer_pressure(group: str) -> float | None:
        """Decode the pressure in a tropopause or maximum-wind group.

        Parameters
        ----------
        group : str
            Five-digit 88PPP or 77PPP group.

        Returns
        -------
        float | None
            Pressure in Pa, or ``None`` when PPP is the missing marker 999.

        Raises
        ------
        ValueError
            If the group is malformed or contains an invalid pressure.

        Examples
        --------
        ``77233`` decodes to 23,300 Pa, while ``88999`` is missing.
        """
        if len(group) != 5 or not group.isdigit() or not group.startswith(("77", "88")):
            raise ValueError(f"Malformed TEMP tropopause/maximum-wind group: {group}")

        pressure_code = int(group[2:])
        if pressure_code == 999:
            return None
        if not 1 <= pressure_code <= 1100:
            raise ValueError(f"Invalid pressure in TEMP layer group: {group}")
        return float(pressure_code * 100)

    @staticmethod
    def _decode_temperature_group(
        group: str,
    ) -> tuple[float | None, float | None]:
        """Decode TEMP temperature and dew-point-depression digits.

        Parameters
        ----------
        group : str
            Five-character TTTDD group, or ``/////`` for missing data.

        Returns
        -------
        tuple[float | None, float | None]
            Temperature and dew-point temperature in kelvin.

        Raises
        ------
        ValueError
            If the group is neither a valid coded value nor a missing marker.

        Examples
        --------
        ``03634`` decodes to 276.75 K and a dew point of 273.35 K.
        """
        if group == "/////":
            return None, None
        if len(group) != 5 or not group[:3].isdigit():
            raise ValueError(f"Malformed TEMP temperature group: {group}")

        temperature_code = int(group[:3])
        if temperature_code >= 500:
            temperature_celsius = -(temperature_code - 500) / 10.0
        else:
            temperature_celsius = temperature_code / 10.0
        temperature_kelvin = temperature_celsius + CELSIUS_TO_KELVIN

        depression_code = group[3:]
        if depression_code == "//":
            dew_point_kelvin = None
        elif depression_code.isdigit():
            depression_value = int(depression_code)
            if depression_value <= 50:
                depression_celsius = depression_value / 10.0
            elif depression_value >= 56:
                depression_celsius = float(depression_value - 50)
            else:
                raise ValueError(
                    f"Reserved TEMP dew-point-depression code: {depression_code}"
                )
            dew_point_kelvin = temperature_kelvin - depression_celsius
        else:
            raise ValueError(f"Malformed TEMP dew-point-depression group: {group}")

        return temperature_kelvin, dew_point_kelvin

    @staticmethod
    def _decode_wind_group(
        group: str, time_group: str
    ) -> tuple[float | None, float | None]:
        """Decode a TEMP wind group to degrees and metres per second.

        Parameters
        ----------
        group : str
            Five-character dddff wind group, or ``/////`` for missing data.
        time_group : str
            TEMP YYGGi time group; its final digit selects wind-speed units.

        Returns
        -------
        tuple[float | None, float | None]
            Wind direction in degrees and wind speed in metres per second.

        Raises
        ------
        ValueError
            If the group or wind-speed unit indicator is unsupported.

        Examples
        --------
        ``23013`` with unit indicator ``1`` decodes to 230 degrees and
        approximately 6.69 m/s.
        """
        if group == "/////":
            return None, None
        if len(group) != 5 or not group.isdigit():
            raise ValueError(f"Malformed TEMP wind group: {group}")

        direction_code = int(group[:3])
        speed_code = int(group[3:])
        if direction_code >= 500:
            direction_code -= 500
            speed_code += 100
        if direction_code > 360:
            raise ValueError(f"TEMP wind direction is out of range: {group}")

        if direction_code == 0 and speed_code == 0:
            return None, 0.0

        unit_indicator = TempParser._wind_speed_unit_indicator(time_group)
        if unit_indicator == "0":
            wind_speed = float(speed_code)
        elif unit_indicator == "1":
            wind_speed = speed_code * KNOTS_TO_METERS_PER_SECOND
        else:
            raise ValueError(
                f"Unsupported TEMP wind-speed unit indicator: {unit_indicator}"
            )

        return float(direction_code), wind_speed

    @staticmethod
    def _as_float(value: float | None) -> float:
        """Convert an optional observation to an xarray-compatible float.

        Parameters
        ----------
        value : float | None
            Decoded value or ``None`` for a missing observation.

        Returns
        -------
        float
            Numeric value or NaN when missing.

        Examples
        --------
        ``_as_float(None)`` returns ``numpy.nan``.
        """
        return np.nan if value is None else value

    @staticmethod
    def _extract_sections(report_text: str) -> list[_TempSection]:
        """Extract TEMP section headers and groups from bulletin text.

        Parameters
        ----------
        report_text : str
            ASCII TEMP report or bulletin text.

        Returns
        -------
        list[_TempSection]
            Sections in their original bulletin order.

        Raises
        ------
        ValueError
            If a section does not contain both a time group and station ID.

        Examples
        --------
        The text between a section marker and the next marker or ``=`` is
        tokenized into the section header and coded groups.
        """
        markers = list(_SECTION_MARKER.finditer(report_text))
        sections = []
        for marker_index, marker in enumerate(markers):
            end_index = report_text.find("=", marker.end())
            if end_index < 0:
                end_index = len(report_text)

            if marker_index + 1 < len(markers):
                next_marker_index = markers[marker_index + 1].start()
                end_index = min(end_index, next_marker_index)

            tokens = report_text[marker.end() : end_index].split()
            if len(tokens) < 2:
                section_code = marker.group(1).upper()
                raise ValueError(
                    f"TEMP section {section_code} is missing its time or station group."
                )

            sections.append(
                _TempSection(
                    code=marker.group(1).upper(),
                    time_group=tokens[0],
                    station_id=tokens[1],
                    code_groups=tuple(tokens[2:]),
                )
            )

        return sections
