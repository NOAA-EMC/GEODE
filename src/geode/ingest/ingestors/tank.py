"""Ingestors for NCEP BUFR tanks (``bAAA/xxBBB``).

The tank reader looks up ingestors by ID in this order:

1. ``tank/bAAA/xxBBB``: a tank-specific ingestor, for subtypes whose mnemonics
   differ from the rest of their dataset.
2. ``tank/<dataset>``: a per-dataset ingestor from table_a_mapping.yaml.

TODO(step 4): register concrete ingestors. Candidates:
  - Reuse the spoc ObsBuilders behind the ``ncep_dump/*`` ingestors (dumps are
    built from tanks, so mnemonics usually match), e.g. ``tank/radiance_atms``.
  - Use ``BufrIngestor``-style YAML mappings in configs/bufr/ for simple types,
    e.g. ``tank/surface_synop``.
TODO(step 5): attach TankInfo metadata (category, subtype, format, restricted)
  to each observation before storing.
"""

import xarray as xr

from geode.configs.table_a_mapping import TankInfo
from geode.ingest.ingestors.base_ingestor import BaseIngestor


class TankIngestor(BaseIngestor):
    """Base class for tank ingestors; stores data under the mapped dataset name."""

    def __init__(self, tank_info: TankInfo):
        super().__init__(tank_info.dataset)
        self.tank_info = tank_info

    def _process(self, file_path: str) -> xr.DataTree | dict[str, xr.DataTree]:
        raise NotImplementedError(
            f"No decoding implemented yet for BUFR tank {self.tank_info.tank_id}"
        )


# Example registration, to be filled in for step 4:
#
# @register("tank/surface_synop")
# class SurfaceSynopTankIngestor(TankIngestor):
#     def _process(self, file_path): ...
