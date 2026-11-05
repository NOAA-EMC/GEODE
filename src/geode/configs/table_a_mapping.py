"""Lookup from BUFR tank IDs (``bAAA/xxBBB``) to GEODE dataset names.

Legacy NCEP decoders write BUFR tanks to ``bAAA/xxBBB`` where ``AAA`` is the
BUFR Table A data category and ``BBB`` is the NCEP local data subcategory.
``configs/bufr/table_a_mapping.yaml`` maps each pair to a dataset name plus
format and restriction metadata.
"""

import os
import re
from dataclasses import dataclass

import yaml

from geode.configs import PackageConfigDir

_TANK_ID_PATTERN = re.compile(r"^b(\d{3})/xx(\d{3})$")

UnmappedCategoryName = "unmapped"
UnmappedFormat = "unknown"


class UnmappedBufrTankError(KeyError):
    """Raised when a BUFR tank ID is well formed but not in table_a_mapping.yaml."""

    def __str__(self) -> str:
        # KeyError quotes its message by default; keep it readable
        return str(self.args[0]) if self.args else ""


@dataclass(frozen=True)
class BufrTankInfo:
    category: int
    subtype: int
    category_name: str
    dataset: str
    format: str
    restricted: bool

    @property
    def tank_id(self) -> str:
        return format_bufr_tank_id(self.category, self.subtype)


def format_bufr_tank_id(category: int, subtype: int) -> str:
    """Return the ``bAAA/xxBBB`` BUFR tank ID for a category/subtype pair."""
    return f"b{category:03d}/xx{subtype:03d}"


def parse_bufr_tank_id(tank_id: str) -> tuple[int, int]:
    """Parse a ``bAAA/xxBBB`` BUFR tank ID into ``(category, subtype)`` integers."""
    match = _TANK_ID_PATTERN.match(tank_id.strip().strip("/"))
    if match is None:
        raise ValueError(
            f"Invalid BUFR tank ID '{tank_id}': expected the form bAAA/xxBBB "
            "(e.g. b000/xx001)"
        )
    return int(match.group(1)), int(match.group(2))


def unmapped_bufr_tank_info(tank_id: str) -> BufrTankInfo:
    """Build a placeholder entry named ``bAAA_xxBBB`` for a BUFR tank with no mapping."""
    category, subtype = parse_bufr_tank_id(tank_id)
    return BufrTankInfo(
        category=category,
        subtype=subtype,
        category_name=UnmappedCategoryName,
        dataset=format_bufr_tank_id(category, subtype).replace("/", "_"),
        format=UnmappedFormat,
        restricted=False,
    )


class TableAMapping:
    def __init__(self, mapping_path: str):
        self.mapping_path = mapping_path
        with open(mapping_path) as mapping_file:
            raw = yaml.safe_load(mapping_file) or {}

        self._tanks: dict[tuple[int, int], BufrTankInfo] = {}
        for category, category_entry in raw.items():
            local_subtypes = category_entry.get("local subtypes") or {}
            for subtype, entry in local_subtypes.items():
                info = BufrTankInfo(
                    category=int(category),
                    subtype=int(subtype),
                    category_name=category_entry["category"],
                    dataset=entry["dataset"],
                    format=entry["format"],
                    restricted=bool(entry["restricted"]),
                )
                self._tanks[(info.category, info.subtype)] = info

    def get(self, tank_id: str) -> BufrTankInfo:
        """Return the mapping entry for a ``bAAA/xxBBB`` BUFR tank ID."""
        key = parse_bufr_tank_id(tank_id)
        if key not in self._tanks:
            raise UnmappedBufrTankError(
                f"BUFR tank '{tank_id}' is not defined in {self.mapping_path}"
            )
        return self._tanks[key]

    def get_dataset(self, tank_id: str) -> str:
        return self.get(tank_id).dataset

    def bufr_tank_ids(self) -> list[str]:
        return [info.tank_id for _, info in sorted(self._tanks.items())]

    def __contains__(self, tank_id: str) -> bool:
        try:
            return parse_bufr_tank_id(tank_id) in self._tanks
        except ValueError:
            return False


# create singleton instance of TableAMapping on module load
table_a_mapping = TableAMapping(
    os.path.join(PackageConfigDir, "bufr", "table_a_mapping.yaml")
)
