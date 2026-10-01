import os
import re
import warnings
import glob

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

# Get target directory path (support both dir_path and file_path keys in YAML)
dir_path = ds_cfg.get("dir_path")
if not dir_path:
    dir_path = ds_cfg.get("file_path")

if os.path.isfile(dir_path):
    dir_path = os.path.dirname(dir_path)

var_name = ds_cfg["variable_name"]
var_label = ds_cfg.get("variable_label", var_name)
units = ds_cfg.get("units", "")
channel_index = ds_cfg.get("channel_index")
cmap = ds_cfg.get("cmap", "coolwarm")
target_pressure_hpa = ds_cfg.get("target_pressure_hpa", None)

# --- Extract Date from Folder Path First ---
dir_path_clean = os.path.normpath(dir_path)
folder_name = os.path.basename(dir_path_clean)
match_folder = re.search(r"(\d{8})", folder_name)
extracted_date = match_folder.group(1) if match_folder else None

cycles = ["00", "06", "12", "18"]
cycle_data = {}

# Step 1: Read all 4 cycles into memory from dir_path
for cyc in cycles:
    # Strictly search inside dir_path (no recursive globbing)
    pattern = os.path.join(dir_path, f"*_{cyc}.nc")
    matching_files = glob.glob(pattern)

    if not matching_files:
        print(f"[WARNING] No file found for cycle {cyc}z in {dir_path}")
        continue
        
    file_path = matching_files[0]
    fname = os.path.basename(file_path)
    print(f"Loading {cyc}Z: {fname}")

    # Fallback to file name date matching if folder path didn't contain an 8-digit date
    if extracted_date is None:
        match_file = re.search(r"(\d{8})", fname)
        if match_file:
            extracted_date = match_file.group(1)

    with nc.Dataset(file_path, "r") as ds:
        meta = ds.groups[ds_cfg.get("meta_group", "MetaData")]
        obs = ds.groups[ds_cfg.get("obs_group", "ObsValue")]

        lats = meta.variables["latitude"][:]
        lons = meta.variables["longitude"][:]

        var_obj = obs.variables[var_name]
        data = var_obj[:, channel_index] if (var_obj.ndim == 2 and channel_index is not None) else var_obj[:]

        fill_val = getattr(var_obj, "_FillValue", 3.402823e38)
        lat_fill = getattr(meta.variables["latitude"], "_FillValue", 3.402823e38)

        # Handle optional pressure
        pressures = None
        if target_pressure_hpa is not None:
            if "pressure" in meta.variables:
                pressures = meta.variables["pressure"][:]
            elif "pressure" in obs.variables:
                pressures = obs.variables["pressure"][:]

    # Convert Longitude range [0, 360] -> [-180, 180]
    lons = np.where(lons > 180, lons - 360, lons)

    # Clean mask
    mask = (data == fill_val) | (lats == lat_fill) | np.isnan(data)
    
    if pressures is not None and target_pressure_hpa is not None:
        p_hpa = pressures / 100.0 if np.nanmax(pressures) > 2000 else pressures
        p_mask = np.abs(p_hpa - target_pressure_hpa) <= 25.0
        mask = mask | (~p_mask)

    cycle_data[cyc] = {
        "lons": lons[~mask],
        "lats": lats[~mask],
        "values": data[~mask],
        "filename": fname
    }

if not cycle_data:
    raise ValueError(f"No valid cycle files were loaded from {dir_path}")

# Format date string for title (e.g. 20260917 -> 2026-09-17)
if extracted_date and len(extracted_date) == 8 and extracted_date.isdigit():
    formatted_date_str = f"{extracted_date[:4]}-{extracted_date[4:6]}-{extracted_date[6:]}"
else:
    formatted_date_str = extracted_date or "UNKNOWN_DATE"

# Step 2: Compute global min and max for uniform colorbar scaling
all_vals = np.concatenate([v["values"] for v in cycle_data.values() if len(v["values"]) > 0])
vmin, vmax = np.min(all_vals), np.max(all_vals)

# Step 3: Create 2x2 Subplot Figure
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
        s=4.0,
        transform=ccrs.PlateCarree() if HAVE_CARTOPY else None,
        rasterized=True
    )
    
    ax.set_title(f"Cycle {cyc}Z ({len(c_info['values']):,} obs)", fontsize=11)

# Step 4: Title & Colorbar Formatting
ch_str = f" Ch{channel_index + 1}" if channel_index is not None else ""
p_str = f" ({target_pressure_hpa} hPa)" if target_pressure_hpa else ""

fig.suptitle(
    f"{dataset_key.upper()} - {var_label}{ch_str}{p_str} [Date: {formatted_date_str}]",
    fontsize=15,
    y=0.98
)

plt.subplots_adjust(
    left=0.10,     # Pushes left column slightly outward
    right=0.90,    # Pushes right column slightly outward
    top=0.90,      # Keeps plots lower (away from title)
    bottom=0.14,   # Positions plots right above the colorbar
    hspace=0.20,   # Vertical gap between top and bottom rows
    wspace=0.20    # INCREASED: Widens gap between left and right columns
)

cbar_ax = fig.add_axes([0.2, 0.06, 0.6, 0.025])
cbar_label = f"{var_label} ({units})" if units else var_label
cbar = fig.colorbar(sc, cax=cbar_ax, orientation="horizontal")
cbar.set_label(cbar_label, fontsize=11)

# Include Date in Output Filename (e.g. PREPBUFR_airTemperature_500hPa_20260917_4cycles.png)
p_file_str = f"_{target_pressure_hpa}hPa" if target_pressure_hpa else ""
date_file_tag = extracted_date if extracted_date else "unknown"
output_filename = f"{dataset_key.upper()}_{var_name}{p_file_str}_{date_file_tag}_4cycles.png"

plt.savefig(output_filename, dpi=300, bbox_inches="tight")
print(f"\nSuccessfully generated plot: {output_filename}")
