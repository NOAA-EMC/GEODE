#!/usr/bin/env python3
import argparse
import math
import os
import numpy as np
import xarray as xr
import matplotlib.pyplot as plt
import cartopy.crs as ccrs
import cartopy.feature as cfeature

import bufr

# Physical constants for Planck's Function
C1 = 1.1910427e-5  # mW / (m^2 * sr * cm^-4)
C2 = 1.4387752     # K * cm

def iasi_channel_to_wavenumber(channel_num: np.ndarray) -> np.ndarray:
    return 645.0 + (channel_num - 1) * 0.25

def radiance_to_bt(radiance: np.ndarray, wavenumber: np.ndarray) -> np.ndarray:
    rad_safe = np.where((radiance > 0) & np.isfinite(radiance), radiance, np.nan)
    with np.errstate(invalid="ignore", divide="ignore"):
        factor = (C1 * (wavenumber ** 3)) / rad_safe
        bt = (C2 * wavenumber) / np.log1p(factor)
    return bt

def get_raw_bufr_data(bufr_file: str, raw_cache_file: str = "iasi_raw_bufr.npz"):
    """Reads raw BUFR variables and caches them directly to an .npz archive."""
    
    # 1. FAST PATH: Load raw BUFR variables from disk
    if os.path.exists(raw_cache_file):
        print(f"Loading raw BUFR variables from cache: {raw_cache_file} (FAST)")
        data = np.load(raw_cache_file, allow_pickle=True)
        return (
            data["lat"],
            data["lon"],
            data["qgfq"],
            data["chnm"],
            data["scra"],
            data["scale_start"],
            data["scale_end"],
            data["scale_exp"],
        )

    # 2. SLOW PATH: Decode raw BUFR file
    print(f"Cache not found. Reading BUFR file: {bufr_file} (SLOW - saving to raw cache)...")

    qs = bufr.QuerySet()
    qs.add("latitude", "*/CLATH")
    qs.add("longitude", "*/CLONH")
    qs.add("quality_flag", "*/QGFQ")
    qs.add("channel_num", "*/IASICHN/CHNM")
    qs.add("scaled_radiance", "*/IASICHN/SCRA")
    qs.add("scale_start", "*/IASIL1CB/STCH")
    qs.add("scale_end", "*/IASIL1CB/ENCH")
    qs.add("scale_exp", "*/IASIL1CB/CHSF")

    with bufr.File(bufr_file) as f:
        res = f.execute(qs)
        lat = res.get("latitude")
        lon = res.get("longitude")
        qgfq = res.get("quality_flag")
        chnm = res.get("channel_num")
        scra = res.get("scaled_radiance")

        scale_start = res.get("scale_start")
        scale_end = res.get("scale_end")
        scale_exp = res.get("scale_exp")

    # Save exact raw variables to .npz file
    print(f"Saving raw arrays to {raw_cache_file}...")
    np.savez_compressed(
        raw_cache_file,
        lat=np.asarray(lat),
        lon=np.asarray(lon),
        qgfq=np.asarray(qgfq) if qgfq is not None else np.array([]),
        chnm=np.asarray(chnm),
        scra=np.asarray(scra),
        scale_start=np.asarray(scale_start) if scale_start is not None else np.array([]),
        scale_end=np.asarray(scale_end) if scale_end is not None else np.array([]),
        scale_exp=np.asarray(scale_exp) if scale_exp is not None else np.array([]),
    )
    print("Raw cache saved successfully!")

    return lat, lon, qgfq, chnm, scra, scale_start, scale_end, scale_exp

def process_and_plot_iasi_bt(bufr_file: str, target_channels: list[int], output_img: str, force_reprocess: bool = False):
    raw_cache_file = "iasi_raw_bufr.npz"

    if force_reprocess and os.path.exists(raw_cache_file):
        os.remove(raw_cache_file)

    # Load raw BUFR variables (either from .npz cache or BUFR execution)
    lat, lon, qgfq, chnm, scra, scale_start, scale_end, scale_exp = get_raw_bufr_data(
        bufr_file, raw_cache_file=raw_cache_file
    )

    # Convert to standard arrays & apply masks/filters
    lat_arr = np.asarray(lat)
    lon_arr = np.asarray(lon)
    scra_arr = np.asarray(scra, dtype=np.float64)
    chnm_arr = np.asarray(chnm)

    lat_mask = getattr(lat, "mask", np.zeros(lat_arr.shape, dtype=bool))
    lon_mask = getattr(lon, "mask", np.zeros(lon_arr.shape, dtype=bool))

    if qgfq is not None and getattr(qgfq, "size", 0) > 0:
        qgfq_valid = (np.asarray(qgfq) == 0)
    else:
        qgfq_valid = np.ones(lat_arr.shape, dtype=bool)

    scra_all_missing = np.all(scra_arr == 65535, axis=1) if scra_arr.ndim > 1 else np.zeros(lat_arr.shape, dtype=bool)
    valid_mask = ~lat_mask & ~lon_mask & ~scra_all_missing & qgfq_valid & np.isfinite(lat_arr) & np.isfinite(lon_arr)

    valid_lat = lat_arr[valid_mask]
    valid_lon = lon_arr[valid_mask]
    valid_scra = scra_arr[valid_mask, :]
    valid_chnm = chnm_arr[valid_mask, :]

    # Filter BUFR fill values
    valid_scra = np.where(
            (valid_scra > 0) & (valid_scra < 7500) & (valid_scra != 8191) & (valid_scra != 65535) & np.isfinite(valid_scra), 
            valid_scra, np.nan
    )

    num_obs, num_channels = valid_scra.shape
    print(f"Loaded {num_obs} valid observations across {num_channels} channels.")

    channel_ids = np.atleast_1d(valid_chnm[0, :]).astype(int)
    print("Extracted channel IDs sample:", channel_ids[:10], "Max channel ID:", np.max(channel_ids))

    # -------------------------------------------------------------------------
    # SCALE FACTOR CALCULATION 
    # -------------------------------------------------------------------------
    scale_factors = np.ones(num_channels, dtype=np.float64)

    # Flag to track if we successfully parsed from header
    parsed_from_header = False

    # 1. Parse from BUFR header bounds if present
    if scale_exp is not None and getattr(scale_exp, "size", 0) > 0:
        st_vals = np.ravel(np.asarray(scale_start))[0:10]
        en_vals = np.ravel(np.asarray(scale_end))[0:10]
        exp_vals = np.ravel(np.asarray(scale_exp))[0:10]

        matches = 0
        for i in range(num_channels):
            ch_num = int(channel_ids[i])
            for st, en, ex in zip(st_vals, en_vals, exp_vals):
                if st > 0 and en > 0 and st <= ch_num <= en:
                    scale_factors[i] = 10.0 ** (-(float(ex) - 5.0))
                    matches += 1
                    break

        if matches > 0:
            parsed_from_header = True

    # 2. Fallback to Strict Band Enforcement IF header bounds were missing or invalid
    if not parsed_from_header:
        print("Warning: Scale factors missing in BUFR header. Applying hardcoded band defaults.")
        for i in range(num_channels):
            ch_num = int(channel_ids[i])
            if ch_num <= 2261:
                scale_factors[i] = 0.01      # 10^-2 for Band 1 & 2 (1 to 2000)
            elif ch_num <= 5421:
                scale_factors[i] = 0.001     # 10^-3 for Band 3 Water Vapor (2001 to 4000)
            else:
                scale_factors[i] = 0.000001  # 10^-6 for Band 4 Shortwave (> 4000)

    # -------------------------------------------------------------------------
    # DEBUG PRINT: Verify what channel_ids and scale_factors actually contain
    # -------------------------------------------------------------------------
    print("Channel IDs sample (first 10):", channel_ids[:10])
    print("Max Channel ID in dataset:", np.max(channel_ids))
    for target in target_channels:
        if target in channel_ids:
            idx = np.where(channel_ids == target)[0][0]
            print(f"Target Channel {target}: Found at index {idx} -> Scale Factor = {scale_factors[idx]}")
        else:
            print(f"Target Channel {target}: NOT FOUND in channel_ids array!")

    # Scale to physical radiance and calculate Brightness Temperature
    unscaled_radiance = valid_scra * scale_factors
    wavenumbers = iasi_channel_to_wavenumber(channel_ids)
    bt_data = radiance_to_bt(unscaled_radiance, wavenumbers)
    bt_data = np.where((bt_data >= 180.0) & (bt_data <= 320.0), bt_data, np.nan)

    # Polar Inversion Mask - Removes Antarctic ice reflection anomalies
    for i in range(num_channels):
        polar_mask = (valid_lat < -60.0) & (bt_data[:, i] > 255.0)
        bt_data[polar_mask, i] = np.nan

    # Build Xarray Dataset
    ds = xr.Dataset(
        data_vars={
            "bt": (["obs", "channel"], bt_data),
            "radiance": (["obs", "channel"], unscaled_radiance),
        },
        coords={
            "lat": (["obs"], valid_lat),
            "lon": (["obs"], valid_lon),
            "channel": channel_ids,
            "wavenumber": (["channel"], wavenumbers),
        },
    )

    n_plots = len(target_channels)
    ncols = 2 if n_plots > 1 else 1
    nrows = math.ceil(n_plots / ncols)

    fig, axes = plt.subplots(
        nrows,
        ncols,
        figsize=(8 * ncols, 4 * nrows),
        subplot_kw={"projection": ccrs.PlateCarree()},
    )

    axes = np.array(axes).flatten()
    for idx, ch in enumerate(target_channels):
        ax = axes[idx]

        if ch in ds.channel.values:
            channel_ds = ds.sel(channel=ch)
            wn_val = float(channel_ds.wavenumber.values)
        else:
            print(f"Warning: Channel {ch} is not present in this file! Skipping subplot.")
            if ax in fig.axes:
                fig.delaxes(ax)
            continue

        # Extract finite Brightness Temperature values for statistics
        bt_vals = channel_ds.bt.values
        valid_bt = bt_vals[np.isfinite(bt_vals)]

        if len(valid_bt) > 0:
            ch_mean = np.mean(valid_bt)
            ch_min = np.min(valid_bt)
            ch_max = np.max(valid_bt)
            ch_median = np.median(valid_bt)
            print(f"--- Channel {ch} ({wn_val:.2f} cm⁻¹) Statistics ---")
            print(f"  Min:    {ch_min:.2f} K")
            print(f"  Max:    {ch_max:.2f} K")
            print(f"  Mean:   {ch_mean:.2f} K")
            print(f"  Median: {ch_median:.2f} K\n")
        else:
            print(f"--- Channel {ch} ({wn_val:.2f} cm⁻¹) Statistics: ALL VALUES ARE NAN ---\n")

        ax.add_feature(cfeature.COASTLINE, linewidth=0.5)
        ax.add_feature(cfeature.BORDERS, linewidth=0.5, linestyle=":")
        ax.add_feature(cfeature.LAND, facecolor="lightgray")

        # Dynamically adjust colorbar range for all channels
        if len(valid_bt) > 0:
            # Dynamic 2nd & 98th percentile stretch for water vapor channels
            vmin_val = float(np.percentile(valid_bt, 2))
            vmax_val = float(np.percentile(valid_bt, 98))
        else:
            vmin_val, vmax_val = 200, 310   # Standard range for Window / Ozone / CO2

        sc = ax.scatter(
            channel_ds.lon,
            channel_ds.lat,
            c=channel_ds.bt,
            cmap="turbo",
            s=8,
            alpha=0.9,
            vmin=vmin_val,
            vmax=vmax_val,
            transform=ccrs.PlateCarree(),
        )

        cbar = plt.colorbar(sc, ax=ax, orientation="vertical", shrink=0.7, pad=0.02)
        cbar.set_label("Brightness Temperature (K)")
        ax.set_title(f"Channel {ch} ({wn_val:.2f} cm⁻¹)")

    for ax in axes:
        if ax in fig.axes and len(ax.collections) == 0:
            fig.delaxes(ax)

    plt.tight_layout()
    plt.savefig(output_img, dpi=300, bbox_inches="tight")
    print(f"Plot successfully saved to {output_img}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Plot multiple IASI Brightness Temperature channels.")
    parser.add_argument("bufr_file", help="Path to BUFR tank")
    parser.add_argument(
        "--channels",
        nargs="+",
        type=int,
        default=[300, 371, 404, 509],
        help="List of IASI channel numbers to plot",
    )
    parser.add_argument("--output", default="iasi_multi_channel_bt.png", help="Output filename")
    parser.add_argument("--force", action="store_true", help="Force reprocessing of BUFR file (ignore raw cache)")
    args = parser.parse_args()

    process_and_plot_iasi_bt(args.bufr_file, args.channels, args.output, force_reprocess=args.force)
