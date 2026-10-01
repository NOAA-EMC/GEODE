import sys
import icechunk
import numpy as np
import xarray as xr
import zarr

REPO_PATH = "/scratch3/NCEPDEV/da/Hyundeok.Choi/geode_tmp/lake/radiosonde.icechunk"
REPO_PATH = "/scratch3/NCEPDEV/da/Hyundeok.Choi/geode_tmp/lake/iasi_metop-b.icechunk"
def print_zarr_structure(group, depth=0):
    """Recursively print groups and variables/arrays in the Zarr store."""
    indent = "  " * depth
    
    # Check for Zarr v3 .members() method or fall back to dictionary iteration
    if hasattr(group, "members"):
        children = group.members()
    else:
        children = group.items()

    for name, item in children:
        if isinstance(item, zarr.Array):
            print(f"{indent}├── [Array] {name} (shape={item.shape}, dtype={item.dtype})")
        elif isinstance(item, zarr.Group):
            print(f"{indent}└── [Group] {name}/")
            print_zarr_structure(item, depth + 1)

def check_times():
    print(f"=== Opening Icechunk Repository: {REPO_PATH} ===")
    repo = icechunk.Repository.open(
        storage=icechunk.local_filesystem_storage(REPO_PATH)
    )

    # 1. Inspect repository branches
    branches = repo.list_branches()
    print(f"Available Branches : {branches}")

    session = repo.readonly_session(branch="main")

    # 2. Inspect Zarr Group Hierarchy & Variables
    print("\n--- Inspecting Zarr Group Hierarchy & Variables ---")
    zgroup = zarr.open_group(session.store, mode="r")
    print_zarr_structure(zgroup)

    # Locate dateTime path
    dt_path = None
    if "MetaData" in zgroup and "dateTime" in zgroup["MetaData"]:
        dt_path = "MetaData/dateTime"
    elif "dateTime" in zgroup:
        dt_path = "dateTime"

    if dt_path is None:
        print("\n[ERROR] Could not locate dateTime variable in repository!")
        return

    # 3. Load dateTime values into Xarray
    print(f"\nReading timestamps from '{dt_path}'...")
    ds_dt = xr.open_zarr(session.store, group="MetaData", zarr_format=3)["dateTime"]
    dt_values = ds_dt.values

    total_obs = len(dt_values)
    print(f"Total Observations : {total_obs:,}")

    if total_obs == 0:
        print("Dataset contains 0 observations.")
        return

    # Count NaT values
    nat_count = np.isnat(dt_values).sum() if np.issubdtype(dt_values.dtype, np.datetime64) else 0
    if nat_count > 0:
        print(f"Missing (NaT) Timestamps: {nat_count:,} out of {total_obs:,}")

    # 4. Extract Min, Max ignoring NaT
    min_time = np.nanmin(dt_values)
    max_time = np.nanmax(dt_values)

    print("\n==================================================")
    print(f"  MIN Observation Time : {min_time}")
    print(f"  MAX Observation Time : {max_time}")
    print("==================================================")

    # Convert to unique YYYY-MM-DD dates and filter out NaT
    if np.issubdtype(dt_values.dtype, np.datetime64):
        dates = np.unique(dt_values.astype("datetime64[D]"))
    else:
        dates = np.unique(dt_values.astype("datetime64[s]").astype("datetime64[D]"))

    dates = dates[~np.isnat(dates)]

    print(f"\nAvailable Dates ({len(dates)} total days):")
    for d in dates:
        print(f"  - {d}")

if __name__ == "__main__":
    check_times()
