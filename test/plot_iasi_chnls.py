#!/usr/bin/env python3
import argparse
import math
import numpy as np
import xarray as xr
import matplotlib.pyplot as plt
import cartopy.crs as ccrs
import cartopy.feature as cfeature

import bufr

def process_and_plot_iasi_multi(bufr_file: str, target_channels: list[int], output_img: str):
    print(f"Reading IASI BUFR file: {bufr_file}")

    # Build queries matching NC021241 structure
    qs = bufr.QuerySet()
    qs.add("latitude", "*/CLATH")
    qs.add("longitude", "*/CLONH")
    qs.add("channel_num", "*/IASICHN/CHNM")
    qs.add("scaled_radiance", "*/IASICHN/SCRA")

    with bufr.File(bufr_file) as f:
        res = f.execute(qs)
        lat = res.get("latitude")
        lon = res.get("longitude")
        chnm = res.get("channel_num")
        scra = res.get("scaled_radiance")

    # Filter invalid/missing lat/lon
    valid_mask = ~lat.mask & ~lon.mask
    valid_lat = lat[valid_mask]
    valid_lon = lon[valid_mask]
    valid_scra = scra[valid_mask, :]

    num_obs, num_channels = valid_scra.shape
    print(f"Loaded {num_obs} observations with {num_channels} channel radiances.")

    # Convert to Xarray Dataset
    ds = xr.Dataset(
        data_vars={"radiance": (["obs", "channel"], valid_scra)},
        coords={
            "lat": (["obs"], valid_lat),
            "lon": (["obs"], valid_lon),
            "channel": np.arange(num_channels)
        }
    )

    # Grid layout setup for subplots
    n_plots = len(target_channels)
    ncols = 2 if n_plots > 1 else 1
    nrows = math.ceil(n_plots / ncols)

    fig, axes = plt.subplots(
        nrows, ncols, 
        figsize=(8 * ncols, 4 * nrows), 
        subplot_kw={"projection": ccrs.PlateCarree()}
    )

    # Flatten axes array for simple indexing
    axes = np.array(axes).flatten()

    for idx, ch in enumerate(target_channels):
        ax = axes[idx]
        channel_data = ds.sel(channel=ch)

        ax.add_feature(cfeature.COASTLINE, linewidth=0.5)
        ax.add_feature(cfeature.BORDERS, linewidth=0.5, linestyle=":")
        ax.add_feature(cfeature.LAND, facecolor="lightgray")

        sc = ax.scatter(
            channel_data.lon,
            channel_data.lat,
            c=channel_data.radiance,
            cmap="turbo",
            s=8,
            alpha=0.9,
            transform=ccrs.PlateCarree(),
        )

        cbar = plt.colorbar(sc, ax=ax, orientation="vertical", shrink=0.7, pad=0.02)
        cbar.set_label("SCRA Radiance")
        ax.set_title(f"Channel Index {ch}")

    # Hide unused subplots if total plots < grid slots
    for idx in range(n_plots, len(axes)):
        fig.delaxes(axes[idx])

    plt.tight_layout()
    plt.savefig(output_img, dpi=300, bbox_inches="tight")
    print(f"Plot successfully saved to {output_img}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Plot multiple IASI SCRA channels.")
    parser.add_argument("bufr_file", help="Path to BUFR tank")
    parser.add_argument(
        "--channels", 
        nargs="+", 
        type=int, 
        default=[300, 400, 500, 600],    #[10, 50, 100, 200], 
        help="Space-separated list of channel indices to plot (e.g., --channels 10 20 30)"
    )
    parser.add_argument("--output", default="iasi_multi_channel.png", help="Output filename")
    args = parser.parse_args()

    process_and_plot_iasi_multi(args.bufr_file, args.channels, args.output)

