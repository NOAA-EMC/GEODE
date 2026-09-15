import xarray as xr

from geode.data.data_manager import data_manager


class BaseIngestor:
    def __init__(self, data_type: str):
        self.data_type = data_type

    def process(self, file_path: str) -> None:
        data_tree = self._process(file_path)
        self._store(data_tree)

    def _process(self, file_path: str) -> xr.DataTree | dict[str, xr.DataTree]:
        raise NotImplementedError("Subclasses should implement this method.")

    def _store(self, data_tree: xr.DataTree | dict[str, xr.DataTree]) -> None:
        if not data_tree:
            return

        # Normalize single DataTree into a dict to apply validation universally
        if isinstance(data_tree, xr.DataTree):
            trees = {None: data_tree}
        elif isinstance(data_tree, dict):
            trees = data_tree
        else:
            return
        
        for category, tree in trees.items():
            # Check if any node in the subtree has fallback 'dim_' dimension names
            has_missing_dims = any(
                str(dim).startswith("dim_")
                for node in tree.subtree
                for var in node.to_dataset(inherit=False).variables.values()
                for dim in var.dims
            )

            if has_missing_dims:
                cat_label = (
                    category if category is not None else self.data_type
                )
                print(
                    f"[SKIP] Skipping category '{cat_label}' - missing dimension data."
                )
                continue

            target_key = (
                f"{self.data_type}_{category}" if category else self.data_type
            )

            data_manager.put(target_key, tree)
