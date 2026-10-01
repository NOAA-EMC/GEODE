import os
import re
import warnings
import glob
from datetime import datetime, timezone

# 1. Suppress Cartopy UserWarning for feature facecolors
warnings.filterwarnings("ignore", category=UserWarning, module="cartopy")

import matplotlib.pyplot as plt
import netCDF4 as nc
import numpy as np
import yaml

# Check for Cartopy availability
try:
    import cartopy.crs as ccrs
    import cartopy.feature as cfeature
    HAVE_CARTOPY = True
except ImportError:
    HAVE_CARTOPY = False
    print("[WARNING] Cartopy not installed. Plotting without map coastlines.")

# Load YAML configuration
CONFIG_PATH = "config_plot.yaml"
with open(CONFIG_PATH, "r") as f:
    config = yaml.safe_load(f)

dataset_key = config["active_dataset"]
ds_cfg = config["datasets"][dataset_key]

# Get target directory path
dir_path = ds_cfg.get("dir_path") or ds_cfg.get("file_path")
if os.path.isfile(dir_path):
    dir_path = os.path.dirname(dir_path)

var_name = ds_cfg["variable_name"]
var_label = ds_cfg.get("variable_label", var_name)
units = ds_cfg.get("units", "")
channel_index = ds_cfg.get("channel_index")
cmap = ds_cfg.get("cmap", "coolwarm")
target_pressure_hpa = ds_cfg.get("target_pressure_hpa", None)

# Extract Date from Folder Path First
dir_path_clean = os.path.normpath(dir_path)
folder_name = os.path.basename(dir_path_clean)
match_folder = re.search(r"(\d{8})", folder_name)
extracted_date = match_folder.group(1) if match_folder else None

cycles = ["00", "06", "12", "18"]
cycle_data = {}

# Step 1: Read all 4 cycles into memory
for cyc in cycles:
    pattern = os.path.join(dir_path, f"gdas.t{cyc}z.*.nc")
    matching_files = glob.glob(pattern)

    if not matching_files:
        print(f"[WARNING] No file found for cycle {cyc}Z in {dir_path}")
        continue

    file_path = matching_files[0]
    fname = os.path.basename(file_path)

    if extracted_date is None:
        match_file = re.search(r"(\d{8})", fname)
        if match_file:
            extracted_date = match_file.group(1)

    with nc.Dataset(file_path, "r") as ds:
        # Prevent netCDF4 from automatically masking arrays into masked_arrays
        ds.set_auto_maskandscale(False)

        meta = ds.groups[ds_cfg.get("meta_group", "MetaData")]
        obs_grp_name = ds_cfg.get("obs_group", "ObsValue")
        obs = ds.groups[obs_grp_name]

        lats = meta.variables["latitude"][:]
        lons = meta.variables["longitude"][:]

        var_obj = obs.variables[var_name]
        data = var_obj[:, channel_index] if (var_obj.ndim == 2 and channel_index is not None) else var_obj[:]

        fill_val = getattr(var_obj, "_FillValue", 3.402823e38)
        lat_fill = getattr(meta.variables["latitude"], "_FillValue", 3.402823e38)

        # Retrieve timestamps from MetaData
        timestamps = meta.variables["dateTime"][:] if "dateTime" in meta.variables else None

        # Retrieve pressure from MetaData group
        pressures = None
        if target_pressure_hpa is not None and "pressure" in meta.variables:
            pressures = meta.variables["pressure"][:]

        # Retrieve Quality Markers if present
        qm_data = None
        if "QualityMarker" in ds.groups and var_name in ds.groups["QualityMarker"].variables:
            qm_data = ds.groups["QualityMarker"].variables[var_name][:]

    # Convert Longitude range [0, 360] -> [-180, 180]
    lons = np.where(lons > 180, lons - 360, lons)

    # Boolean mask checking for fill values, NaNs, and large invalid numbers
    mask = (
        (data == fill_val) |
        (data >= 1e9) |
        (data == 2147483647) |
        (lats == lat_fill) |
        (lats >= 1e9) |
        np.isnan(data)
    )

    if qm_data is not None:
        mask = mask | (qm_data > 3)

    if pressures is not None and target_pressure_hpa is not None:
        p_hpa = pressures / 100.0  # Pa -> hPa
        p_mask = np.abs(p_hpa - target_pressure_hpa) <= 25.0
        mask = mask | (~p_mask)

    valid_lons = lons[~mask]
    valid_lats = lats[~mask]
    valid_vals = data[~mask]

    # Process dateTime metadata
    min_time_str, max_time_str = "N/A", "N/A"
    if timestamps is not None:
        valid_times = timestamps[~mask]
        # Filter out invalid epoch markers
        time_mask = (valid_times > 0) & (valid_times < 9000000000000000000)
        valid_times = valid_times[time_mask]

        if len(valid_times) > 0:
            min_ts = np.min(valid_times)
            max_ts = np.max(valid_times)
            min_dt = datetime.fromtimestamp(min_ts, timezone.utc)
            max_dt = datetime.fromtimestamp(max_ts, timezone.utc)
            min_time_str = min_dt.strftime("%Y-%m-%d %H:%M:%S UTC")
            max_time_str = max_dt.strftime("%Y-%m-%d %H:%M:%S UTC")

    # Print summary information for the NetCDF file
    print(f"Loading {cyc}Z: {fname}")
    print(f"  └─ Valid Obs Count : {len(valid_vals):,}")
    print(f"  └─ Min Date/Time   : {min_time_str}")
    print(f"  └─ Max Date/Time   : {max_time_str}")

    # Deduplicate locations if target_pressure_hpa is None
    if target_pressure_hpa is None and len(valid_vals) > 0:
        coords = np.column_stack((valid_lats, valid_lons))
        _, unique_idx = np.unique(coords, axis=0, return_index=True)
        valid_lons = valid_lons[unique_idx]
        valid_lats = valid_lats[unique_idx]
        valid_vals = valid_vals[unique_idx]

    cycle_data[cyc] = {
        "lons": valid_lons,
        "lats": valid_lats,
        "values": valid_vals,
        "filename": fname,
        "min_time": min_time_str,
        "max_time": max_time_str
    }

if not cycle_data:
    raise ValueError(f"No valid cycle files were loaded from {dir_path}")

formatted_date_str = f"{extracted_date[:4]}-{extracted_date[4:6]}-{extracted_date[6:]}" if (extracted_date and len(extracted_date) == 8) else (extracted_date or "UNKNOWN_DATE")

# Step 2: Global min/max range calculation
all_vals = np.concatenate([v["values"] for v in cycle_data.values() if len(v["values"]) > 0])
if len(all_vals) == 0:
    raise ValueError("All data points were masked. Check variable names or pressure level criteria.")

vmin, vmax = np.min(all_vals), np.max(all_vals)

# Step 3: Plot 2x2 Subplots
fig, axes = plt.subplots(
    2, 2, figsize=(16, 9),
    subplot_kw={'projection': ccrs.PlateCarree()} if HAVE_CARTOPY else {}
)
axes = axes.flatten()

for idx, cyc in enumerate(cycles):
    ax = axes[idx]

    if HAVE_CARTOPY:
        ax.set_global()
        ax.add_feature(cfeature.COASTLINE, linewidth=0.7, edgecolor="black", facecolor="none")
        ax.add_feature(cfeature.BORDERS, linewidth=0.3, linestyle=":", edgecolor="gray", facecolor="none")
        gl = ax.gridlines(draw_labels=True, dms=True, x_inline=False, y_inline=False, alpha=0.2)
        gl.xlabel_style = {'size': 8}
        gl.ylabel_style = {'size': 8}
        gl.xlocator = plt.FixedLocator([-120, -60, 0, 60, 120])
        gl.ylocator = plt.FixedLocator([-60, -30, 0, 30, 60])
    else:
        ax.set_xlim(-180, 180)
        ax.set_ylim(-90, 90)

    if cyc not in cycle_data or len(cycle_data[cyc]["values"]) == 0:
        ax.set_title(f"Cycle {cyc}Z (0 obs)", fontsize=11)
        continue

    c_info = cycle_data[cyc]

    sc = ax.scatter(
        c_info["lons"],
        c_info["lats"],
        c=c_info["values"],
        cmap=cmap,
        vmin=vmin,
        vmax=vmax,
        s=5.0,
        transform=ccrs.PlateCarree() if HAVE_CARTOPY else None,
        rasterized=True
    )

    ax.set_title(f"Cycle {cyc}Z ({len(c_info['values']):,} obs)", fontsize=11)

    # --- Add Min/Max Date/Time text box at bottom-left corner of subplot ---
    time_text = f"Min: {c_info['min_time']}\nMax: {c_info['max_time']}"
    ax.text(
        0.02, 0.05, time_text,
        transform=ax.transAxes,
        fontsize=11,
        verticalalignment='bottom',
        horizontalalignment='left',
        bbox=dict(boxstyle='round,pad=0.3', facecolor='white', alpha=0.8, edgecolor='gray')
    )

# Step 4: Formatting and Export
ch_str = f" Ch{channel_index + 1}" if channel_index is not None else ""
p_str = f" ({target_pressure_hpa} hPa)" if target_pressure_hpa else ""

fig.suptitle(
    f"{dataset_key.upper()} - {var_label}{ch_str}{p_str} [Date: {formatted_date_str}]",
    fontsize=15,
    y=0.98
)

plt.subplots_adjust(left=0.10, right=0.90, top=0.90, bottom=0.14, hspace=0.20, wspace=0.20)
cbar_ax = fig.add_axes([0.2, 0.06, 0.6, 0.025])
cbar_label = f"{var_label} ({units})" if units else var_label
cbar = fig.colorbar(sc, cax=cbar_ax, orientation="horizontal")
cbar.set_label(cbar_label, fontsize=11)

p_file_str = f"_{target_pressure_hpa}hPa" if target_pressure_hpa else ""
date_file_tag = extracted_date if extracted_date else "unknown"
output_filename = f"{dataset_key.upper()}_{var_name}{p_file_str}_{date_file_tag}_4cycles.png"

plt.savefig(output_filename, dpi=300, bbox_inches="tight")
print(f"\nSuccessfully generated plot: {output_filename}")
