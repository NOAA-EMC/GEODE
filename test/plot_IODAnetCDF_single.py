import os
import re
import matplotlib.pyplot as plt
import netCDF4 as nc
import numpy as np

# File path
#file_path = "/scratch3/NCEPDEV/da/Hyundeok.Choi/geode_tmp/icechunk2ioda/20260801/atms_npp_obs_20260801_18.nc"
file_path = "/scratch3/NCEPDEV/da/Hyundeok.Choi/geode_tmp/icechunk2ioda/20260913/prepbufr_adpupa_obs_20260913_00.nc"

# Channel index (0-indexed: 0 = Channel 1)
channel_index = 0
channel_num = channel_index + 1

# Extract metadata from filename (e.g., atms_n21_obs_20260801_06.nc)
filename = os.path.basename(file_path)

# Regex pattern matching: <sensor_sat>_obs_<date>_<cycle>.nc
match = re.match(r"([a-zA-Z0-0]+_[a-zA-Z0-9]+)_obs_(\d{8})_(\d{2})\.nc", filename)

if match:
    sensor_sat = match.group(1).upper()  # e.g., ATMS_N21
    date_str = match.group(2)            # e.g., 20260801
    cycle_str = match.group(3)           # e.g., 06
    
    # Generic output filename: e.g., ATMS_N21_Ch01_20260801_06z.png
    output_filename = f"{sensor_sat}_Ch{channel_num:02d}_{date_str}_{cycle_str}z.png"
    plot_title = f"{sensor_sat} Brightness Temperature - Channel {channel_num}\nDate: {date_str} {cycle_str}Z"
else:
    # Fallback name if pattern matching fails
    clean_name = os.path.splitext(filename)[0]
    output_filename = f"{clean_name}_Ch{channel_num:02d}.png"
    plot_title = f"Brightness Temperature - Channel {channel_num}\n{filename}"

# Read NetCDF data
with nc.Dataset(file_path, "r") as ds:
    meta = ds.groups["MetaData"]
    obs = ds.groups["ObsValue"]

    lats = meta.variables["latitude"][:]
    lons = meta.variables["longitude"][:]

    tb_var = obs.variables["brightnessTemperature"]
    tb = tb_var[:, channel_index]

    tb_fill = getattr(tb_var, "_FillValue", 3.402823e38)
    lat_fill = getattr(meta.variables["latitude"], "_FillValue", 3.402823e38)

# Mask missing / fill values
mask = (tb == tb_fill) | (lats == lat_fill) | np.isnan(tb)
lons_clean = lons[~mask]
lats_clean = lats[~mask]
tb_clean = tb[~mask]

# Plot
fig, ax = plt.subplots(figsize=(12, 6))

sc = ax.scatter(
    lons_clean,
    lats_clean,
    c=tb_clean,
    cmap="jet",
    s=0.5,
    rasterized=True
)

cbar = plt.colorbar(sc, ax=ax, orientation="horizontal", pad=0.1, shrink=0.7)
cbar.set_label("Brightness Temperature (K)")

ax.set_xlabel("Longitude")
ax.set_ylabel("Latitude")
ax.set_xlim(-180, 180)
ax.set_ylim(-90, 90)
ax.set_title(plot_title)
ax.grid(True, linestyle="--", alpha=0.5)

# Save figure using generic filename
plt.savefig(output_filename, dpi=300, bbox_inches="tight")
print(f"Plot successfully saved as: {output_filename}")
