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
C2 = 1.4387752      # K * cm

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

    lat, lon, qgfq, chnm, scra, scale_start, scale_end, scale_exp = get_raw_bufr_data(
        bufr_file, raw_cache_file=raw_cache_file
    )

    lat_arr = np.ma.asarray(lat)
    lon_arr = np.ma.asarray(lon)
    scra_arr = np.ma.asarray(scra, dtype=np.float64)
    chnm_arr = np.ma.asarray(chnm)

    if scra_arr.ndim != 2 or chnm_arr.ndim != 2:
        raise ValueError("Expected SCRA and CHNM to be 2D arrays with shape (observation, channel).")

    lat_values = np.ma.filled(lat_arr, np.nan).astype(np.float64)
    lon_values = np.ma.filled(lon_arr, np.nan).astype(np.float64)
    scra_values = np.ma.filled(scra_arr, np.nan).astype(np.float64)
    chnm_values = np.ma.filled(chnm_arr, -1).astype(np.int64)

    if qgfq is not None and np.size(qgfq) > 0:
        qgfq_values = np.ma.filled(np.ma.asarray(qgfq), -1)
        qgfq_valid = qgfq_values == 0
    else:
        qgfq_valid = np.ones(lat_values.shape, dtype=bool)

    valid_scra_mask = (
        np.isfinite(scra_values)
        & (scra_values > 0)
        & (scra_values < 30000)
        & (scra_values != 8191)
        & (scra_values != 65535)
    )

    valid_mask = np.isfinite(lat_values) & np.isfinite(lon_values) & qgfq_valid & np.any(valid_scra_mask, axis=1)

    valid_lat = lat_values[valid_mask]
    valid_lon = lon_values[valid_mask]
    valid_scra = scra_values[valid_mask, :]
    valid_chnm = chnm_values[valid_mask, :]

    num_obs, num_channels = valid_scra.shape
    print(f"Loaded {num_obs} valid observations across {num_channels} channels.")

    channel_ids = np.atleast_1d(valid_chnm[0, :]).astype(int)

    # -------------------------------------------------------------------------
    # SCALE FACTOR CALCULATION (Pure BUFR Header logic without overrides)
    # -------------------------------------------------------------------------
    scale_factors = np.zeros((num_obs, num_channels), dtype=np.float64)

    if scale_exp is not None and np.size(scale_exp) > 0:
        scale_start_arr = np.atleast_2d(np.asarray(scale_start))
        scale_end_arr = np.atleast_2d(np.asarray(scale_end))
        scale_exp_arr = np.atleast_2d(np.asarray(scale_exp))

        # Vectorized lookup across observations and channel bounds
        for obs_i in range(num_obs):
            scale_row = obs_i if obs_i < scale_start_arr.shape[0] else 0
            st_vals = scale_start_arr[scale_row, :10]
            en_vals = scale_end_arr[scale_row, :10]
            exp_vals = scale_exp_arr[scale_row, :10]

            matched = np.zeros(num_channels, dtype=bool)

            for group_start, group_end, exponent in zip(st_vals, en_vals, exp_vals):
                if not (
                    np.isfinite(group_start)
                    and np.isfinite(group_end)
                    and np.isfinite(exponent)
                    and group_start > 0
                    and group_end > 0
                    and exponent < 1000
                ):
                    continue

                group_mask = (
                    ~matched
                    & (channel_ids >= int(group_start))
                    & (channel_ids <= int(group_end))
                )
                sf_group = 10.0 ** (-(int(round(exponent)) - 5))
                scale_factors[obs_i, group_mask] = sf_group
                matched[group_mask] = True

    # Scale to physical radiance and calculate Brightness Temperature
    unscaled_radiance = valid_scra * scale_factors
    wavenumbers = iasi_channel_to_wavenumber(channel_ids)
    
    # Broadcast wavenumbers for 2D calculation
    wn_2d = np.tile(wavenumbers, (num_obs, 1))
    bt_data = radiance_to_bt(unscaled_radiance, wn_2d)
    bt_data = np.where((bt_data >= 180.0) & (bt_data <= 320.0), bt_data, np.nan)

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

    axes = np.array(axes).flatten() if n_plots > 1 else np.array([axes])

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

        if len(valid_bt) > 0:
            vmin_val = float(np.percentile(valid_bt, 2))
            vmax_val = float(np.percentile(valid_bt, 98))
        else:
            vmin_val, vmax_val = 200, 310

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
