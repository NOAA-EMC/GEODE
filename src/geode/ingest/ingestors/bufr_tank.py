"""Ingestors for NCEP BUFR tanks (``bAAA/xxBBB``).

The BUFR tank reader looks up ingestors by ID in this order:

1. ``bufr_tank/bAAA/xxBBB``: a tank-specific ingestor, for subtypes whose mnemonics
   differ from the rest of their dataset.
2. ``bufr_tank/<dataset>``: a per-dataset ingestor from table_a_mapping.yaml.

TODO(step 4): register concrete ingestors. Candidates:
  - Reuse the spoc ObsBuilders behind the ``ncep_dump/*`` ingestors (dumps are
    built from BUFR tanks, so mnemonics usually match), e.g. ``bufr_tank/radiance_atms``.
  - Use ``BufrIngestor``-style YAML mappings in configs/bufr/ for simple types,
    e.g. ``bufr_tank/surface_synop``.
TODO(step 5): attach BufrTankInfo metadata (category, subtype, format, restricted)
  to each observation before storing.
"""

import xarray as xr

from geode.configs.table_a_mapping import BufrTankInfo
from geode.ingest.ingestors.base_ingestor import BaseIngestor


class BufrTankIngestor(BaseIngestor):
    """Base class for BUFR tank ingestors; stores data under the mapped dataset name."""

    def __init__(self, tank_info: BufrTankInfo):
        super().__init__(tank_info.dataset)
        self.tank_info = tank_info

    def _process(self, file_path: str) -> xr.DataTree | dict[str, xr.DataTree]:
        raise NotImplementedError(
            f"No decoding implemented yet for BUFR tank {self.tank_info.tank_id}"
        )


# Example registration, to be filled in for step 4:
#
# @register("bufr_tank/surface_synop")
# class SurfaceSynopBufrTankIngestor(BufrTankIngestor):
#     def _process(self, file_path): ...
