"""Program Name: temp_parser.py
Author: GEODE contributors
Abstract: Extract WMO TEMP sections and coded groups into an xarray DataTree.
History Log: Initial implementation.
Usage: Called by TempIngestor for ASCII TEMP bulletins.
Input/Output files: ASCII TEMP input / in-memory xarray DataTree.
"""

import re
from dataclasses import dataclass

import xarray as xr

_SECTION_MARKER = re.compile(r"\b(TTAA|TTBB|TTCC|TTDD)\b", re.IGNORECASE)


@dataclass(frozen=True)
class _TempSection:
    code: str
    time_group: str
    station_id: str
    code_groups: tuple[str, ...]


class TempParser:
    """Extract the section structure of WMO TEMP reports."""

    def parse(self, report_text: str) -> xr.DataTree:
        """Parse TEMP sections while retaining their coded groups verbatim.

        Parameters
        ----------
        report_text : str
            ASCII TEMP report or bulletin text.

        Returns
        -------
        xarray.DataTree
            A tree with one child dataset per TEMP section. Each child stores
            coded groups on a ``group`` dimension and header fields as attrs.

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
            dataset = xr.Dataset(
                data_vars={
                    "code_group": ("group", list(section.code_groups)),
                },
                coords={"group": range(len(section.code_groups))},
                attrs={
                    "section_code": section.code,
                    "time_group": section.time_group,
                    "station_id": section.station_id,
                },
            )
            tree[child_name] = xr.DataTree(dataset=dataset, name=child_name)

        return tree

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
