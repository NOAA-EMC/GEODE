import bufr
import xarray as xr
from bufr.obs_builder import ObsBuilder

from geode.ingest.ingestors.base_ingestor import BaseIngestor
from geode.ingest.ingestors.bufr_ingestor import container_to_xarray


class ObsBuilderIngestor(BaseIngestor):
    def __init__(self, data_type: str, obs_builder: ObsBuilder):
        super().__init__(data_type)
        self.obs_builder = obs_builder

    def _process(self, file_path: str) -> xr.DataTree | dict[str, xr.DataTree]:
        comm = bufr.mpi.Comm("world")
        container = self.obs_builder.make_obs(comm, file_path)
        container.gather(comm)

        if comm.rank() == 0:
            self.obs_builder.finalize_container(container)
            datatree = container_to_xarray(container, self.obs_builder.description)
            d = self._remap_locations(datatree)
            print("*****", d)
            return d

        return None

    def _remap_locations(
        self, 
        datatree: xr.DataTree | dict[str, xr.DataTree]
        original: list[str] = ["Location", "Channel"]
        loc_mapping: dict[str, str] = {
            "MetaData/dateTime": "time",
            "MetaData/latitude": "latitude",
            "MetaData/longitude": "longitude",
        }
    ) -> xr.DataTree | dict[str, xr.DataTree]:

        if isinstance(datatree, dict):
            return {
                category: self._remap_location(tree, original, loc_mapping)
                for category, tree in datatree.items()
            }
        return self._remap_location(datatree, original, loc_mapping)

    def _remap_location(
        self, 
        datatree: xr.DataTree,
        original: list[str],
        loc_mapping: dict[str, str],
    ) -> xr.DataTree:

        if MetaDataGroup not in datatree.children:
            raise ValueError(
                f"FATAL ERROR: '{MetaDataGroup}' group not found in ObsBuilder data."
            )

        metadata = datatree[MetaDataGroup].to_dataset(inherit=False)
        for name in LocationCoords:
            if name not in metadata.variables:
                raise ValueError(
                    f"FATAL ERROR: '{MetaDataGroup}/{name}' not found in "
                    "ObsBuilder data."
                )
            if metadata[name].dims != (LocationDim,):
                raise ValueError(
                    f"FATAL ERROR: '{MetaDataGroup}/{name}' has dims "
                    f"{metadata[name].dims}, expected ({LocationDim!r},)."
                )

        location_coords = {name: metadata[name].variable for name in LocationCoords}

        root = datatree.to_dataset(inherit=False)
        root = root.drop_vars(LocationDim, errors="ignore")
        root = root.assign_coords(location_coords)
        for name in LocationCoords:
            root = root.set_xindex(name)

        nodes = {"/": root}
        for node in datatree.subtree:
            if node is datatree:
                continue
            dataset = node.to_dataset(inherit=False)
            if node.path == f"/{MetaDataGroup}":
                dataset = dataset.drop_vars(list(LocationCoords))
            nodes[node.path] = dataset

        return xr.DataTree.from_dict(nodes, name=datatree.name)
