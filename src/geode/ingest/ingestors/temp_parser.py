"""Program Name: temp_parser.py
Author: GEODE contributors
Abstract: Extract WMO TEMP sections and coded groups into an xarray DataTree.
History Log: Initial implementation.
Usage: Called by TempIngestor for ASCII TEMP bulletins.
Input/Output files: ASCII TEMP input / in-memory xarray DataTree.
"""

import re
from dataclasses import dataclass

import numpy as np
import xarray as xr

_SECTION_MARKER = re.compile(r"\b(TTAA|TTBB|TTCC|TTDD)\b", re.IGNORECASE)
_MANDATORY_PRESSURES = {
    "00": 1000.0,
    "92": 925.0,
    "85": 850.0,
    "70": 700.0,
    "50": 500.0,
    "40": 400.0,
    "30": 300.0,
    "25": 250.0,
    "20": 200.0,
    "15": 150.0,
    "10": 100.0,
}
_KNOTS_TO_METERS_PER_SECOND = 0.514444
_CELSIUS_TO_KELVIN = 273.15


@dataclass(frozen=True)
class _TempSection:
    code: str
    time_group: str
    station_id: str
    code_groups: tuple[str, ...]


@dataclass(frozen=True)
class _Observation:
    pressure: float
    temperature: float | None
    dew_point_temperature: float | None
    wind_direction: float | None
    wind_speed: float | None
    level_code: str


class TempParser:
    """Decode supported mandatory-level groups in WMO TEMP reports."""

    def parse(self, report_text: str) -> xr.DataTree:
        """Decode TEMP mandatory-level observations into physical variables.

        Parameters
        ----------
        report_text : str
            ASCII TEMP report or bulletin text.

        Returns
        -------
        xarray.DataTree
            A tree with one child dataset per TEMP section. Each child stores
            decoded observations on a ``level`` dimension and original coded
            groups on a separate ``group`` dimension.

        Raises
        ------
        ValueError
            If no TEMP sections are present or a section lacks its time or
            station header groups.

        Examples
        --------
        ``TempParser().parse("TTAA 80181 72365 99834=")`` extracts one TTAA
        section with station ID ``72365``.
        """
        sections = self._extract_sections(report_text)
        if not sections:
            raise ValueError("No WMO TEMP sections found in TAC input.")

        tree = xr.DataTree(
            dataset=xr.Dataset(
                attrs={"format": "WMO TEMP", "section_count": len(sections)}
            ),
            name="temp",
        )
        for section_index, section in enumerate(sections, start=1):
            child_name = f"section_{section_index:06d}"
            dataset = self._decode_section(section)
            tree[child_name] = xr.DataTree(dataset=dataset, name=child_name)

        return tree

    @classmethod
    def _decode_section(cls, section: _TempSection) -> xr.Dataset:
        """Decode a TEMP section into an xarray dataset.

        Parameters
        ----------
        section : _TempSection
            Parsed TEMP header and coded groups.

        Returns
        -------
        xarray.Dataset
            Dataset containing decoded mandatory-level observations and raw
            groups for traceability.

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

        observations = cls._decode_mandatory_levels(section)
        if not observations:
            raise ValueError(
                f"TEMP section {section.code} has no decodable mandatory levels."
            )

        return xr.Dataset(
            data_vars={
                "pressure": (
                    "level",
                    [observation.pressure for observation in observations],
                    {"units": "hPa", "standard_name": "air_pressure"},
                ),
                "temperature": (
                    "level",
                    [
                        cls._as_float(observation.temperature)
                        for observation in observations
                    ],
                    {"units": "K", "standard_name": "air_temperature"},
                ),
                "dewPointTemperature": (
                    "level",
                    [
                        cls._as_float(observation.dew_point_temperature)
                        for observation in observations
                    ],
                    {"units": "K", "standard_name": "dew_point_temperature"},
                ),
                "windDirection": (
                    "level",
                    [
                        cls._as_float(observation.wind_direction)
                        for observation in observations
                    ],
                    {"units": "degree", "standard_name": "wind_from_direction"},
                ),
                "windSpeed": (
                    "level",
                    [
                        cls._as_float(observation.wind_speed)
                        for observation in observations
                    ],
                    {"units": "m s-1", "standard_name": "wind_speed"},
                ),
                "level_code": (
                    "level",
                    [observation.level_code for observation in observations],
                ),
                "code_group": ("group", list(section.code_groups)),
            },
            coords={
                "level": (
                    "level",
                    [observation.pressure for observation in observations],
                    {"units": "hPa", "standard_name": "air_pressure"},
                ),
                "group": range(len(section.code_groups)),
            },
            attrs={
                "section_code": section.code,
                "time_group": section.time_group,
                "station_id": section.station_id,
                "wind_speed_unit_indicator": section.time_group[-1],
                "decoded_level_count": len(observations),
                "history": "Decoded from raw WMO TEMP TAC groups by GEODE.",
            },
        )

    @classmethod
    def _decode_mandatory_levels(cls, section: _TempSection) -> list[_Observation]:
        """Decode surface and standard-pressure-level groups in TTAA/TTCC.

        Parameters
        ----------
        section : _TempSection
            TTAA TEMP section.

        Returns
        -------
        list[_Observation]
            Decoded levels in report order, from the surface upward.

        Raises
        ------
        ValueError
            If the surface group sequence or a recognized level group is
            malformed.

        Examples
        --------
        A ``70068 03634 23013`` sequence yields the 700 hPa level with
        temperature, dew-point depression, and wind values.
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
            pressure = (1000.0 if pressure_code < 500 else 900.0) + (
                pressure_code / 10.0
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
                    temperature=temperature,
                    dew_point_temperature=dew_point_temperature,
                    wind_direction=wind_direction,
                    wind_speed=wind_speed,
                    level_code=surface_group,
                )
            )
            group_index = 3

        while group_index < len(groups):
            level_code = groups[group_index]
            if level_code in {"31313", "51515", "21212"}:
                break
            if level_code.startswith(("77", "88")):
                break

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
                    temperature=temperature,
                    dew_point_temperature=dew_point_temperature,
                    wind_direction=wind_direction,
                    wind_speed=wind_speed,
                    level_code=level_code,
                )
            )
            group_index += 3

        return observations

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
        temperature_kelvin = temperature_celsius + _CELSIUS_TO_KELVIN

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

        unit_indicator = time_group[-1:]
        if unit_indicator == "0":
            wind_speed = float(speed_code)
        elif unit_indicator == "1":
            wind_speed = speed_code * _KNOTS_TO_METERS_PER_SECOND
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
