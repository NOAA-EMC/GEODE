import warnings

# Suppress Cartopy feature_artist warnings
warnings.filterwarnings("ignore", category=UserWarning, module="cartopy")

import os
import re
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

file_path = ds_cfg["file_path"]
var_name = ds_cfg["variable_name"]
var_label = ds_cfg.get("variable_label", var_name)
units = ds_cfg.get("units", "")
channel_index = ds_cfg.get("channel_index")
cmap = ds_cfg.get("cmap", "jet")

# Pressure target (optional: set to null/None or leave out for satellite/surface data)
target_pressure_hpa = ds_cfg.get("target_pressure_hpa", None)

# Extract metadata from filename
filename = os.path.basename(file_path)
match = re.match(r"([a-zA-Z0-9]+_[a-zA-Z0-9]+)_obs_(\d{8})_(\d{2})\.nc", filename)

if match:
    sensor_sat = match.group(1).upper()
    date_str = match.group(2)
    cycle_str = match.group(3)
else:
    sensor_sat = os.path.splitext(filename)[0].upper()
    date_str = "UNKNOWN"
    cycle_str = "00"

# Read NetCDF data safely
with nc.Dataset(file_path, "r") as ds:
    meta_group_name = ds_cfg.get("meta_group", "MetaData")
    obs_group_name = ds_cfg.get("obs_group", "ObsValue")

    meta = ds.groups[meta_group_name]
    obs = ds.groups[obs_group_name]

    lats = meta.variables["latitude"][:]
    lons = meta.variables["longitude"][:]

    var_obj = obs.variables[var_name]

    if var_obj.ndim == 2 and channel_index is not None:
        data = var_obj[:, channel_index]
    else:
        data = var_obj[:]

    fill_val = getattr(var_obj, "_FillValue", 3.402823e38)
    lat_fill = getattr(meta.variables["latitude"], "_FillValue", 3.402823e38)

    # Safely check for pressure variable across groups if requested
    pressures = None
    if target_pressure_hpa is not None:
        if "pressure" in meta.variables:
            pressures = meta.variables["pressure"][:]
        elif "pressure" in obs.variables:
            pressures = obs.variables["pressure"][:]
        else:
            print("[INFO] 'target_pressure_hpa' was set, but no 'pressure' variable exists in file. Plotting all points.")

# Convert Longitude range from [0, 360] -> [-180, 180]
lons = np.where(lons > 180, lons - 360, lons)

# Base quality / fill-value mask
mask = (data == fill_val) | (lats == lat_fill) | np.isnan(data)

# Conditional pressure filtering logic
level_title_str = ""
p_filename_str = ""

if pressures is not None and target_pressure_hpa is not None:
    # Auto-detect if pressure is in Pa or hPa
    p_hpa = pressures / 100.0 if np.nanmax(pressures) > 2000 else pressures
    # Filter within tolerance window (+/- 25 hPa)
    p_mask = np.abs(p_hpa - target_pressure_hpa) <= 25.0
    mask = mask | (~p_mask)
    level_title_str = f" ({target_pressure_hpa} hPa)"
    p_filename_str = f"_{target_pressure_hpa}hPa"

lons_clean = lons[~mask]
lats_clean = lats[~mask]
data_clean = data[~mask]

# Create Figure
fig = plt.figure(figsize=(14, 7))

if HAVE_CARTOPY:
    ax = fig.add_subplot(1, 1, 1, projection=ccrs.PlateCarree())
    ax.add_feature(cfeature.COASTLINE, linewidth=0.8, color="black", facecolor="none")
    ax.add_feature(cfeature.BORDERS, linewidth=0.4, linestyle=":", color="gray", facecolor="none")
    ax.gridlines(draw_labels=True, dms=True, x_inline=False, y_inline=False, alpha=0.3)
    
    sc = ax.scatter(
        lons_clean,
        lats_clean,
        c=data_clean,
        cmap=cmap,
        s=4.0,
        transform=ccrs.PlateCarree(),
        rasterized=True
    )
else:
    ax = fig.add_subplot(1, 1, 1)
    sc = ax.scatter(lons_clean, lats_clean, c=data_clean, cmap=cmap, s=4.0, rasterized=True)
    ax.set_xlabel("Longitude")
    ax.set_ylabel("Latitude")
    ax.set_xlim(-180, 180)
    ax.set_ylim(-90, 90)
    ax.grid(True, linestyle="--", alpha=0.5)

ch_str = f"_Ch{channel_index + 1:02d}" if channel_index is not None else ""
title_ch_str = f" - Channel {channel_index + 1}" if channel_index is not None else ""

output_filename = f"{sensor_sat}_{var_name}{ch_str}{p_filename_str}_{date_str}_{cycle_str}z.png"
plot_title = f"{sensor_sat} {var_label}{title_ch_str}{level_title_str}\nDate: {date_str} {cycle_str}Z"
ax.set_title(plot_title, fontsize=12)

cbar_label = f"{var_label} ({units})" if units else var_label
cbar = plt.colorbar(sc, ax=ax, orientation="horizontal", pad=0.08, shrink=0.7)
cbar.set_label(cbar_label)

plt.savefig(output_filename, dpi=300, bbox_inches="tight")
print(f"Plot successfully saved as: {output_filename}")
