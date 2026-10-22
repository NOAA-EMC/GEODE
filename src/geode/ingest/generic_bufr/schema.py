"""Schema discovery, naming, hashing and mapping generation for generic BUFR."""

import hashlib
import json
import re
from dataclasses import asdict, dataclass, field

from geode.ingest.generic_bufr.tables import (
    MAX_SEQUENCE_DEPTH,
    BufrTableError,
    BufrTables,
)

DATETIME_MNEMONICS = ("YEAR", "MNTH", "DAYS", "HOUR", "MINU")
DEFAULT_GROUP = "Header"
_INVALID_NAME_CHARS = re.compile(r"[^0-9A-Za-z_]")


class SchemaMismatchError(RuntimeError):
    """Raised when a discovered schema differs from the stored schema."""


@dataclass(frozen=True)
class Replication:
    """One replication level; ``count`` is ``None`` for delayed replication."""

    name: str
    kind: str
    count: int | None = None


@dataclass
class BufrField:
    """A discovered leaf element with its provenance."""

    mnemonic: str
    path: tuple[str, ...]
    group: str
    units: str
    scale: int
    reference: int
    bits: int
    description: str
    replications: tuple[Replication, ...] = ()
    name: str = ""
    dimensions: tuple[str, ...] = ("Location",)
    target: str = ""
    long_name: str = ""
    output_units: str = ""

    @property
    def key(self) -> str:
        """Path-qualified source key, e.g. ``CHNL/TMBR`` or ``CLATH``."""
        return "/".join(self.path + (self.mnemonic,))

    @property
    def output_name(self) -> str:
        """Lake variable path: the mapped target or ``<group>/<name>``."""
        return self.target or f"{self.group}/{self.name}"

    @property
    def query(self) -> str:
        """Query string for this field, e.g. ``*/BRIT/TMBR``."""
        parts = list(self.path)
        if not parts or parts[-1] != self.mnemonic:
            parts.append(self.mnemonic)
        return "*/" + "/".join(parts)

    @property
    def is_string(self) -> bool:
        return "CCITT" in self.units.upper() or self.units.upper().startswith("CHAR")


@dataclass
class BufrSchema:
    """Deterministic description of one BUFR subset."""

    subset: str
    fields: list[BufrField] = field(default_factory=list)
    emit_datetime: bool = False

    @property
    def dimension_sizes(self) -> dict[str, int | None]:
        """Replication dimension names mapped to fixed size (``None`` if delayed)."""
        sizes = {}
        for bufr_field in self.fields:
            for dim, rep in zip(bufr_field.dimensions[1:], bufr_field.replications):
                sizes[dim] = rep.count
        return dict(sorted(sizes.items()))

    @property
    def has_datetime(self) -> bool:
        """True if time elements were scalar at discovery (kept when mapped out)."""
        return self.emit_datetime

    @property
    def schema_hash(self) -> str:
        return schema_hash(self)


def sanitize_name(name: str) -> str:
    """Return ``name`` restricted to ``[0-9A-Za-z_]``."""
    cleaned = _INVALID_NAME_CHARS.sub("_", name)
    return cleaned if cleaned and not cleaned[0].isdigit() else f"_{cleaned}"


def discover_schema(tables: BufrTables, subset: str | None = None) -> BufrSchema:
    """Expand a subset's Table D sequence into a flat, sorted field list.

    Parameters
    ----------
    tables : BufrTables
        Parsed DX tables.
    subset : str, optional
        Table A subset mnemonic. May be omitted only when the tables define
        exactly one subset.

    Returns
    -------
    BufrSchema
        Fields sorted by (group, path, mnemonic) with collision-free names and
        deterministic replication dimension names.

    Raises
    ------
    BufrTableError
        On ambiguous or unknown subsets, unknown mnemonics or recursive
        sequences.
    """
    if subset is None:
        if len(tables.subsets) != 1:
            raise BufrTableError(
                f"FATAL ERROR: Specify a subset; tables define {sorted(tables.subsets)}"
            )
        subset = next(iter(tables.subsets))
    if subset not in tables.sequences:
        raise BufrTableError(f"FATAL ERROR: Subset '{subset}' has no sequence")

    found = {}

    def expand(seq_name, path, group, reps, stack):
        if len(stack) > MAX_SEQUENCE_DEPTH or seq_name in stack:
            raise BufrTableError(f"FATAL ERROR: Recursive sequence at '{seq_name}'")
        for item in tables.sequences[seq_name]:
            item_reps, item_path = reps, path
            if item.replication:
                item_reps = reps + (
                    Replication(item.mnemonic, item.replication, item.count),
                )
                item_path = path + (item.mnemonic,)
            if item.mnemonic in tables.sequences:
                child_group = group
                if group is None:
                    child_group = sanitize_name(item.mnemonic)
                expand(
                    item.mnemonic,
                    item_path,
                    child_group,
                    item_reps,
                    stack + (seq_name,),
                )
            elif item.mnemonic in tables.elements:
                entry = tables.elements[item.mnemonic]
                key = (item_path, item.mnemonic)
                found.setdefault(
                    key,
                    BufrField(
                        mnemonic=item.mnemonic,
                        path=item_path,
                        group=group or DEFAULT_GROUP,
                        units=entry.units,
                        scale=entry.scale,
                        reference=entry.reference,
                        bits=entry.bits,
                        description=entry.description,
                        replications=item_reps,
                    ),
                )
            else:
                raise BufrTableError(
                    f"FATAL ERROR: Mnemonic '{item.mnemonic}' in '{seq_name}' "
                    "is not defined in Table B or D"
                )

    expand(subset, (), None, (), ())
    fields = sorted(found.values(), key=lambda f: (f.group, f.path, f.mnemonic))
    _assign_dimensions(fields)
    _assign_names(fields)
    scalar = {f.mnemonic for f in fields if not f.replications}
    return BufrSchema(
        subset=subset,
        fields=fields,
        emit_datetime=all(m in scalar for m in DATETIME_MNEMONICS),
    )


def _assign_dimensions(fields: list[BufrField]) -> None:
    """Name replication dimensions; qualify by path if a name is reused."""
    owners = {}
    for bufr_field in fields:
        for depth, rep in enumerate(bufr_field.replications):
            owners.setdefault(rep.name, set()).add(
                (bufr_field.path[: depth + 1], rep.kind, rep.count)
            )
    for bufr_field in fields:
        dims = ["Location"]
        for depth, rep in enumerate(bufr_field.replications):
            if len(owners[rep.name]) > 1:
                dims.append(sanitize_name("_".join(bufr_field.path[: depth + 1])))
            else:
                dims.append(sanitize_name(rep.name))
        bufr_field.dimensions = tuple(dims)


def _assign_names(fields: list[BufrField]) -> None:
    """Use bare mnemonics; path-qualify every member of a colliding set."""
    counts = {}
    for bufr_field in fields:
        key = (bufr_field.group, sanitize_name(bufr_field.mnemonic))
        counts[key] = counts.get(key, 0) + 1
    for bufr_field in fields:
        base = sanitize_name(bufr_field.mnemonic)
        if counts[(bufr_field.group, base)] > 1 and bufr_field.path:
            base = sanitize_name("_".join(bufr_field.path + (bufr_field.mnemonic,)))
        bufr_field.name = base


def schema_hash(schema: BufrSchema) -> str:
    """SHA-256 of the canonical schema (order and content sensitive)."""
    payload = {
        "subset": schema.subset,
        "emit_datetime": schema.emit_datetime,
        "fields": [asdict(f) for f in schema.fields],
    }
    encoded = json.dumps(payload, sort_keys=True, default=list).encode()
    return hashlib.sha256(encoded).hexdigest()


def check_schema_hash(stored: str | None, discovered: str) -> bool:
    """Return True if appending is allowed (nothing stored or hashes equal)."""
    return stored is None or stored == discovered


def build_mapping(schema: BufrSchema) -> dict:
    """Build a bufr-query mapping (parser + encoder) from a schema.

    Parameters
    ----------
    schema : BufrSchema
        Discovered schema.

    Returns
    -------
    dict
        Mapping suitable for ``yaml.safe_dump`` and ``bufr.Parser`` /
        ``bufr.encoders.Description``. Variables are written as
        ``<group>/<name>`` with provenance in ``longName``/``units``.
    """
    variables = {}
    encoder_vars = []
    for bufr_field in schema.fields:
        key = sanitize_name(bufr_field.output_name)
        variables[key] = {"query": bufr_field.query}
        entry = {
            "name": bufr_field.output_name,
            "source": f"variables/{key}",
            "longName": bufr_field.long_name
            or bufr_field.description
            or bufr_field.mnemonic,
            "units": bufr_field.output_units or bufr_field.units,
        }
        if len(bufr_field.dimensions) > 1:
            entry["dimensions"] = list(bufr_field.dimensions)
            entry["path"] = bufr_field.query
        encoder_vars.append(entry)

    if schema.has_datetime:
        variables["timestamp"] = {
            "datetime": {
                "year": "*/YEAR",
                "month": "*/MNTH",
                "day": "*/DAYS",
                "hour": "*/HOUR",
                "minute": "*/MINU",
            }
        }
        encoder_vars.insert(
            0,
            {
                "name": "MetaData/dateTime",
                "source": "variables/timestamp",
                "longName": "Datetime",
                "units": "seconds since 1970-01-01T00:00:00Z",
            },
        )

    return {"bufr": {"variables": variables}, "encoder": {"variables": encoder_vars}}


def provenance(schema: BufrSchema) -> dict[str, dict]:
    """Per-variable provenance keyed by ``<group>/<name>``."""
    return {
        f.output_name: {
            "bufr_mnemonic": f.mnemonic,
            "bufr_path": f.query,
            "bufr_units": f.units,
            "bufr_scale": f.scale,
            "bufr_reference": f.reference,
            "bufr_bits": f.bits,
        }
        for f in schema.fields
    }
