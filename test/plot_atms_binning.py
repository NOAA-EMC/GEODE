import datetime
import matplotlib
matplotlib.use("Agg")

import matplotlib.pyplot as plt
import cartopy.crs as ccrs
import geode
import numpy as np


def format_filter_info(filters):
    """Return (title_summary, filename_tag) from query_filters."""
    if not filters:
        return "Unfiltered", "unfiltered"

    title_parts = []
    file_parts = []

    for f in filters:
        if "region" in f:
            reg = str(f["region"])
            title_parts.append(f"Region: {reg.upper()}")
            file_parts.append(reg.lower())

        for mode in ("superobbing", "thinning"):
            if mode in f:
                cfg = f[mode]
                if "distance" in cfg:
                    val = cfg["distance"]
                    res_title = f"{val:g} km"
                    res_file = f"{val:g}km"
                elif "grid" in cfg:
                    g = cfg["grid"]
                    if isinstance(g, (list, tuple)):
                        res_title = f"{g[0]:g}°×{g[1]:g}°"
                        res_file = f"{g[0]:g}x{g[1]:g}deg"
                    else:
                        res_title = f"{g:g}°"
                        res_file = f"{g:g}deg"
                else:
                    res_title = "N/A"
                    res_file = "na"

                method = str(cfg.get("aggregation") or cfg.get("strategy") or "na")
                title_parts.append(f"{mode.capitalize()} | Res: {res_title} | Method: {method}")
                file_parts.append(f"{mode}_{res_file}_{method.lower()}")

    if not title_parts:
        return "Custom Filter", "custom"

    return " | ".join(title_parts), "_".join(file_parts)


# ---------------------------------------------------------
# 1. Query GEODE with Filter
# ---------------------------------------------------------
start_time = datetime.datetime(2026, 9, 13, 9, 0, tzinfo=datetime.UTC)
end_time = datetime.datetime(2026, 9, 13, 15, 0, tzinfo=datetime.UTC)
dataset_name = "atms_n20"

query_filters = [
    #{"region": "conus"},
    #{"thinning": {"distance": 120.0, "strategy": "center"}},
    #{"thinning": {"grid": [2.0, 2.5], "strategy": "center"}},
    {"thinning": {"grid": [2.0, 2.5], "strategy": "random"}},
    #{"superobbing": {"grid": [1.0, 1.25], "aggregation": "median", "min_obs": 2}},
    #{"superobbing": {"distance": 100, "aggregation": "mean", "min_obs": 2}},
]

filter_title, filter_tag = format_filter_info(query_filters)
time_title = f"{start_time:%Y-%m-%d %H}z to {end_time:%Y-%m-%d %H}z UTC"
time_tag = f"{start_time:%Y%m%d%H}_{end_time:%Y%m%d%H}"

print(f"Fetching {dataset_name} ({filter_title})...")
result = geode.get(dataset_name, start_time, end_time, filters=query_filters)
print("Query complete.")

# ---------------------------------------------------------
# 2. Extract Data
# ---------------------------------------------------------
meta_ds = result["MetaData"].to_dataset()
obs_ds = result["ObsValue"].to_dataset()

latitude = meta_ds["latitude"].values
longitude = meta_ds["longitude"].values

channel_idx = 0
bt = obs_ds["brightnessTemperature"].isel(Channel=channel_idx).values

valid = (
    np.isfinite(latitude)
    & np.isfinite(longitude)
    & np.isfinite(bt)
    & (bt > 50.0)
    & (bt < 350.0)
)

n_valid = np.count_nonzero(valid)
print(f"Plotting {n_valid:,} points ({time_title})...")

# ---------------------------------------------------------
# 3. Plotting
# ---------------------------------------------------------
fig, ax = plt.subplots(figsize=(10, 5), subplot_kw={"projection": ccrs.PlateCarree()})
sc = ax.scatter(
    longitude[valid],
    latitude[valid],
    c=bt[valid],
    s=3,
    cmap="turbo",
    transform=ccrs.PlateCarree(),
    rasterized=True,
)
ax.coastlines(resolution="110m", linewidth=0.7)
ax.set_global()
ax.set_title(
    f"NOAA-20 ATMS Ch {channel_idx + 1} — {filter_title} (N={n_valid:,})\n"
    f"Obs Time: {time_title}",
    fontsize=10,
)
fig.colorbar(sc, ax=ax, label="Brightness Temperature (K)", pad=0.02, shrink=0.72)

out_filename = f"{dataset_name}_ch{channel_idx + 1}_{filter_tag}_{time_tag}.png"
plt.tight_layout()
plt.savefig(out_filename, dpi=150, bbox_inches="tight")
plt.close(fig)
print(f"Saved: {out_filename}")
