import xarray as xr

from geode.data.data_manager import data_manager


class BaseIngestor:
    def __init__(self, data_type: str):
        self.data_type = data_type

    def process(self, file_path: str) -> None:
        data_tree = self._process(file_path)
        self._store(data_tree)

    def _process(self, file_path: str) -> xr.DataTree | dict[xr.DataTree]:
        raise NotImplementedError("Subclasses should implement this method.")

    def _store(self, data_tree: xr.DataTree | dict[xr.DataTree]) -> None:
        if isinstance(data_tree, dict) and not data_tree:
            return
        if data_tree is None:
            return

        if isinstance(data_tree, xr.DataTree):
            data_manager.put(self.data_type, data_tree)
        elif isinstance(data_tree, dict):
            for category, tree in data_tree.items():
                data_manager.put(f"{self.data_type}_{category}", tree)
