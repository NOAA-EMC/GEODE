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
        if not data_tree:
            return

        if isinstance(data_tree, xr.DataTree):
            data_manager.put(self.data_type, data_tree)
        elif isinstance(data_tree, dict):
            for category, tree in data_tree.items():
                # Convert node to dataset to inspect dimensions
                ds = tree.to_dataset() if hasattr(tree, "to_dataset") else tree
            
                # Check if any variable has fallback 'dim_' names
                has_missing_dims = any(
                    str(dim).startswith("dim_")
                    for var in ds.variables.values()
                    for dim in var.dims
                )
             
                if has_missing_dims:
                    print(f"[SKIP] Skipping category '{category}' - missing dimension data.")
                    continue

                data_manager.put(f"{self.data_type}_{category}", tree)

