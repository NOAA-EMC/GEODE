"""Variable mapping from discovered BUFR fields to curated lake names.

Example mapping file::

    unmapped: include        # or "drop"
    dimensions:
      CHNL: Channel          # rename a replication dimension everywhere
    variables:
      - source: CHNL/TMBR    # path-qualified key, or a bare unambiguous mnemonic
        name: ObsValue/brightnessTemperature
        units: K             # optional override
        longName: Brightness Temperature
        dimensions: [Location, Channel]   # optional, must match source rank
"""

import yaml

from geode.ingest.generic_bufr.schema import BufrSchema

UNMAPPED_POLICIES = ("include", "drop")
_ENTRY_KEYS = {"source", "name", "units", "longName", "dimensions"}


class VariableMapError(ValueError):
    """Raised when a variable map is malformed or inconsistent with a schema."""


def load_variable_map(path: str) -> dict:
    """Load and validate a variable map YAML file.

    Parameters
    ----------
    path : str
        Path to the YAML mapping file.

    Returns
    -------
    dict
        Validated mapping with ``unmapped``, ``dimensions`` and ``variables``.

    Raises
    ------
    VariableMapError
        If the file structure or keys are invalid.
    """
    with open(path) as map_file:
        raw = yaml.safe_load(map_file) or {}
    if not isinstance(raw, dict):
        raise VariableMapError(f"FATAL ERROR: '{path}' must contain a mapping")
    unknown = set(raw) - {"unmapped", "dimensions", "variables"}
    if unknown:
        raise VariableMapError(f"FATAL ERROR: Unknown keys {sorted(unknown)}")
    result = {
        "unmapped": raw.get("unmapped", "include"),
        "dimensions": raw.get("dimensions") or {},
        "variables": raw.get("variables") or [],
    }
    if result["unmapped"] not in UNMAPPED_POLICIES:
        raise VariableMapError(f"FATAL ERROR: unmapped must be in {UNMAPPED_POLICIES}")
    if not isinstance(result["dimensions"], dict):
        raise VariableMapError("FATAL ERROR: 'dimensions' must be a mapping")
    for entry in result["variables"]:
        if not isinstance(entry, dict) or not {"source", "name"} <= set(entry):
            raise VariableMapError(
                f"FATAL ERROR: Each variable needs 'source' and 'name': {entry}"
            )
        extra = set(entry) - _ENTRY_KEYS
        if extra:
            raise VariableMapError(f"FATAL ERROR: Unknown keys {sorted(extra)}")
    return result


def apply_variable_map(schema: BufrSchema, variable_map: dict) -> BufrSchema:
    """Apply curated names, dimensions and units to a schema in place.

    Parameters
    ----------
    schema : BufrSchema
        Discovered schema.
    variable_map : dict
        Output of ``load_variable_map``.

    Returns
    -------
    BufrSchema
        The same schema with unmapped fields kept or removed per policy.

    Raises
    ------
    VariableMapError
        If a source matches no field or is ambiguous, a dimension override has
        the wrong rank, or two variables end up with the same lake name.
    """
    by_key = {f.key: f for f in schema.fields}
    by_mnemonic = {}
    for bufr_field in schema.fields:
        by_mnemonic.setdefault(bufr_field.mnemonic, []).append(bufr_field)

    renames = variable_map["dimensions"]
    mapped = set()
    explicit_dims = set()
    for entry in variable_map["variables"]:
        source = entry["source"]
        if source in by_key:
            bufr_field = by_key[source]
        elif len(by_mnemonic.get(source, [])) == 1:
            bufr_field = by_mnemonic[source][0]
        elif source in by_mnemonic:
            raise VariableMapError(
                f"FATAL ERROR: '{source}' is ambiguous; use one of "
                f"{sorted(f.key for f in by_mnemonic[source])}"
            )
        else:
            raise VariableMapError(f"FATAL ERROR: Source '{source}' not in schema")
        if id(bufr_field) in mapped:
            raise VariableMapError(f"FATAL ERROR: '{bufr_field.key}' mapped twice")
        mapped.add(id(bufr_field))
        bufr_field.target = entry["name"]
        bufr_field.long_name = entry.get("longName", "")
        bufr_field.output_units = entry.get("units", "")
        if "dimensions" in entry:
            dims = tuple(entry["dimensions"])
            if len(dims) != len(bufr_field.dimensions) or dims[0] != "Location":
                raise VariableMapError(
                    f"FATAL ERROR: dimensions for '{source}' must have "
                    f"{len(bufr_field.dimensions)} entries starting with Location"
                )
            bufr_field.dimensions = dims
            explicit_dims.add(id(bufr_field))

    for bufr_field in schema.fields:
        if id(bufr_field) not in explicit_dims:
            bufr_field.dimensions = tuple(
                renames.get(d, d) for d in bufr_field.dimensions
            )
    if variable_map["unmapped"] == "drop":
        schema.fields = [f for f in schema.fields if id(f) in mapped]

    names = [f.output_name for f in schema.fields]
    duplicates = sorted({n for n in names if names.count(n) > 1})
    if schema.has_datetime and "MetaData/dateTime" in names:
        duplicates.append("MetaData/dateTime")
    if duplicates:
        raise VariableMapError(f"FATAL ERROR: Duplicate lake names {duplicates}")
    return schema
