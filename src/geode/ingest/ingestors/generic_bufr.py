import logging
import os
import subprocess
import tempfile

import bufr
import xarray as xr
import yaml

from geode.configs.geode_config import geode_config
from geode.data.data_manager import data_manager
from geode.ingest.generic_bufr.normalize import normalize_dataset
from geode.ingest.generic_bufr.schema import (
    BufrSchema,
    SchemaMismatchError,
    build_mapping,
    check_schema_hash,
    discover_schema,
    provenance,
)
from geode.ingest.generic_bufr.tables import BufrTableError, parse_dx_table
from geode.ingest.ingestors import register
from geode.ingest.ingestors.base_ingestor import BaseIngestor
from geode.ingest.ingestors.bufr_ingestor import container_to_xarray

logger = logging.getLogger(__name__)

MISMATCH_POLICIES = ("error", "version", "skip")
SCHEMA_HASH_ATTR = "bufr_schema_hash"


def read_embedded_dx_table(file_path: str) -> str:
    """Extract the text DX table embedded in a BUFR file using ``gettab``."""
    try:
        result = subprocess.run(
            ["gettab", file_path],
            capture_output=True,
            text=True,
            check=True,
            timeout=300,
        )
    except (OSError, subprocess.SubprocessError) as err:
        raise BufrTableError(
            f"FATAL ERROR: Could not extract DX table from '{file_path}' with "
            f"gettab; pass dx_table explicitly ({err})"
        ) from err
    return result.stdout


@register("ncep_dump/generic_bufr")
class GenericBufrIngestor(BaseIngestor):
    """Ingest every element of a BUFR subset without a curated ObsBuilder.

    Parameters
    ----------
    data_type : str
        Lake name for the output.
    dx_table : str, optional
        Text DX table file; if omitted the table embedded in the BUFR file is
        extracted with ``gettab``.
    subset : str, optional
        Table A subset mnemonic; required when the table defines several.
    on_schema_mismatch : {"error", "version", "skip"}
        Behavior when the discovered schema differs from the stored one.
    max_replication_length : int, optional
        Pad delayed replication dimensions to this size (append-safe).
    """

    def __init__(
        self,
        data_type: str = "generic_bufr",
        dx_table: str | None = None,
        subset: str | None = None,
        on_schema_mismatch: str = "error",
        max_replication_length: int | None = None,
    ):
        super().__init__(data_type)
        if on_schema_mismatch not in MISMATCH_POLICIES:
            raise ValueError(
                f"on_schema_mismatch must be one of {MISMATCH_POLICIES}, "
                f"got '{on_schema_mismatch}'"
            )
        self.dx_table = dx_table
        self.subset = subset
        self.on_schema_mismatch = on_schema_mismatch
        self.max_replication_length = max_replication_length
        self.table_path = geode_config.bufr.table_path

    def discover(self, file_path: str) -> BufrSchema:
        if not os.path.isfile(file_path):
            raise FileNotFoundError(f"FATAL ERROR: BUFR file not found: {file_path}")
        if self.dx_table:
            with open(self.dx_table) as table_file:
                text = table_file.read()
        else:
            text = read_embedded_dx_table(file_path)
        return discover_schema(parse_dx_table(text), self.subset)

    def _process(self, file_path: str) -> xr.DataTree | None:
        schema = self.discover(file_path)
        mapping = build_mapping(schema)

        comm = bufr.mpi.Comm("world")
        with tempfile.TemporaryDirectory() as temp_dir:
            mapping_path = os.path.join(temp_dir, "generic_bufr.yaml")
            with open(mapping_path, "w") as mapping_file:
                yaml.safe_dump(mapping, mapping_file, sort_keys=False)
            container = bufr.Parser(file_path, mapping_path, self.table_path).parse(
                comm
            )
            container.gather(comm)

            if comm.rank() != 0:
                return None
            datatree = container_to_xarray(
                container, bufr.encoders.Description(mapping_path)
            )

        return self._finalize_tree(datatree, schema, file_path)

    def _finalize_tree(
        self, datatree: xr.DataTree, schema: BufrSchema, file_path: str
    ) -> xr.DataTree:
        sizes = schema.dimension_sizes
        notes = provenance(schema)
        for node in datatree.subtree:
            if "Location" not in node.dims:
                continue
            dataset = normalize_dataset(
                node.to_dataset(inherit=False), sizes, self.max_replication_length
            )
            for name in dataset.data_vars:
                dataset[name].attrs.update(
                    notes.get(f"{node.path.lstrip('/')}/{name}", {})
                )
            dataset.attrs[SCHEMA_HASH_ATTR] = schema.schema_hash
            node.dataset = dataset
        datatree.attrs.update(
            {
                SCHEMA_HASH_ATTR: schema.schema_hash,
                "bufr_subset": schema.subset,
                "ingestor": "generic_bufr",
                "source_file": os.path.basename(file_path),
            }
        )
        return datatree

    def _stored_hash(self, data_type: str) -> str | None:
        import icechunk as ic

        path = data_manager.get_file_path(data_type)
        storage = ic.local_filesystem_storage(path)
        if not ic.Repository.exists(storage):
            return None
        session = ic.Repository.open(storage).readonly_session("main")
        tree = xr.open_datatree(session.store, engine="zarr", consolidated=False)
        for node in tree.subtree:
            stored = node.attrs.get(SCHEMA_HASH_ATTR)
            if stored is not None:
                return stored
        return None

    def _store(self, data_tree) -> None:
        if not isinstance(data_tree, xr.DataTree):
            return
        discovered = data_tree.attrs[SCHEMA_HASH_ATTR]
        if check_schema_hash(self._stored_hash(self.data_type), discovered):
            super()._store(data_tree)
            return

        message = f"BUFR schema for '{self.data_type}' changed (new hash {discovered})"
        if self.on_schema_mismatch == "error":
            raise SchemaMismatchError(f"FATAL ERROR: {message}")
        if self.on_schema_mismatch == "skip":
            logger.warning("%s; skipping append", message)
            return
        logger.warning("%s; writing to versioned store", message)
        data_manager.put(f"{self.data_type}_schema_{discovered[:12]}", data_tree)
