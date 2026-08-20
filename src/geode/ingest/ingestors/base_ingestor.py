import os

import xarray as xr

from geode.data.data_manager import data_manager


class BaseIngestor:
    def __init__(self):
        self.data_type = None

    def process(self, file_path: str) -> None:
        data_tree = self._process(file_path)
        self._store(data_tree)
        os.remove(file_path)  # Clean up the file after processing

    def _process(self, file_path: str) -> xr.DataTree:
        raise NotImplementedError("Subclasses should implement this method.")

    def _store(self, data_tree: xr.DataTree) -> None:
        data_manager.put(self.data_type, data_tree)
