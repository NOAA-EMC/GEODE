#!/usr/bin/env python3
import argparse
from pathlib import Path
import matplotlib.pyplot as plt
import cartopy.crs as ccrs
import cartopy.feature as cfeature
import numpy as np

import bufr


def plot_observations(bufr_file: str, output_img: str):
    print(f"Reading BUFR file: {bufr_file}")

    # Query configuration based on NC000101 output from show_queries.x
    qs = bufr.QuerySet()
    qs.add("latitude", "*/CLATH")
    qs.add("longitude", "*/CLONH")
    qs.add("temperature", "*/TMDB")  # TEMPERATURE/DRY BULB TEMPERATURE

    with bufr.File(bufr_file) as f:
        res = f.execute(qs)
        lat = res.get("latitude")
        lon = res.get("longitude")
        temp = res.get("temperature")

    # Filter missing values
    mask = ~lat.mask & ~lon.mask & ~temp.mask
    valid_lat = lat[mask]
    valid_lon = lon[mask]
    valid_temp = temp[mask]

    print(f"Plotting {len(valid_lat)} valid observations...")

    fig = plt.figure(figsize=(12, 6))
    ax = plt.axes(projection=ccrs.PlateCarree())

    # Add map features
    ax.add_feature(cfeature.COASTLINE, linewidth=0.5)
    ax.add_feature(cfeature.BORDERS, linewidth=0.5, linestyle=":")
    ax.add_feature(cfeature.LAND, facecolor="lightgray", alpha=0.5)
    ax.add_feature(cfeature.OCEAN, facecolor="azure", alpha=0.5)
    
    # Plot observations colored by temperature
    sc = ax.scatter(
        valid_lon,
        valid_lat,
        c=valid_temp,
        cmap="jet",
        s=5,
        alpha=0.8,
        transform=ccrs.PlateCarree(),
    )
    
    # Add colorbar on the side
    cbar = plt.colorbar(sc, ax=ax, orientation="vertical", shrink=0.8, pad=0.02)
    cbar.set_label("Temperature / Dry Bulb (K)")
    
    ax.set_title("ADPSFC Observations (TMDB)")
    
    plt.savefig(output_img, dpi=300, bbox_inches="tight")
    print(f"Plot saved to {output_img}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Plot ADPSFC observations from BUFR file.")
    parser.add_argument("bufr_file", help="Path to the BUFR file")
    parser.add_argument("--output", default="adpsfc_plot.png", help="Output image filename")
    args = parser.parse_args()
    
    plot_observations(args.bufr_file, args.output)
