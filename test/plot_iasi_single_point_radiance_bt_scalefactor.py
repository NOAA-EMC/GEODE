#!/usr/bin/env python3

"""
python3 plot_iasi_single_point_radiance_bt_scalefactor.py /path/to/bufr --idx 624518 --output iasi_single_point_radiance_bt_scalefactor.png
python3 plot_iasi_single_point_radiance_bt_scalefactor.py /path/to/bufr --lat 25.0 --lon 45.0 --output iasi_single_point_radiance_bt_scalefactor.png
"""
import argparse
import os
import numpy as np
import matplotlib.pyplot as plt

import bufr

# Physical constants for Planck's Function
C1 = 1.1910427e-5  # mW / (m^2 * sr * cm^-4)
C2 = 1.4387752      # K * cm


def iasi_channel_to_wavenumber(channel_num: np.ndarray) -> np.ndarray:
    """Converts IASI channel IDs (1-8461) to wavenumber in cm^-1."""
    return 645.0 + (channel_num - 1) * 0.25


def radiance_to_bt(radiance: np.ndarray, wavenumber: np.ndarray) -> np.ndarray:
    """Converts physical radiance to Brightness Temperature in Kelvin."""
    rad_safe = np.where((radiance > 0) & np.isfinite(radiance), radiance, np.nan)
    with np.errstate(invalid="ignore", divide="ignore"):
        factor = (C1 * (wavenumber**3)) / rad_safe
        bt = (C2 * wavenumber) / np.log1p(factor)
    return bt


def get_raw_bufr_data(bufr_file: str, raw_cache_file: str = "iasi_raw_bufr.npz"):
    """Reads raw BUFR variables or loads from disk cache."""
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

    print(f"Reading BUFR file: {bufr_file} (SLOW - saving to raw cache)...")
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
    return lat, lon, qgfq, chnm, scra, scale_start, scale_end, scale_exp


def plot_single_point_radiance(
    bufr_file: str,
    target_lat: float = None,
    target_lon: float = None,
    obs_index: int = None,
    output_img: str = "iasi_single_point_spectrum.png",
    force_reprocess: bool = False,
):
    raw_cache_file = "iasi_raw_bufr.npz"
    if force_reprocess and os.path.exists(raw_cache_file):
        os.remove(raw_cache_file)

    # 1. Load BUFR data
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

    # Quality Control Filter
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

    # 2. Select Observation Point
    if obs_index is not None:
        selected_idx = obs_index
    elif target_lat is not None and target_lon is not None:
        valid_locs = np.isfinite(lat_values) & np.isfinite(lon_values) & qgfq_valid
        candidate_indices = np.flatnonzero(valid_locs)
        distances = (lat_values[candidate_indices] - target_lat)**2 + (lon_values[candidate_indices] - target_lon)**2
        selected_idx = candidate_indices[int(np.argmin(distances))]
    else:
        location_mask = (
            np.isfinite(lat_values)
            & np.isfinite(lon_values)
            & (np.abs(lat_values) < 50.0)
            & qgfq_valid
            & np.any(valid_scra_mask, axis=1)
        )
        candidate_indices = np.flatnonzero(location_mask)
        if candidate_indices.size == 0:
            raise RuntimeError("No valid IASI observations found.")
        valid_channel_counts = np.sum(valid_scra_mask[candidate_indices], axis=1)
        selected_idx = candidate_indices[np.argmax(valid_channel_counts)]

    selected_lat = float(lat_values[selected_idx])
    selected_lon = float(lon_values[selected_idx])
    selected_scra = scra_values[selected_idx].copy()
    channel_ids = chnm_values[selected_idx].copy()

    # Filter out invalid channels for selected report
    ch_mask = valid_scra_mask[selected_idx] & (channel_ids > 0)
    selected_scra = selected_scra[ch_mask]
    channel_ids = channel_ids[ch_mask]

    print(f"\n--- Selected Observation Point ---")
    print(f"Observation Index: {selected_idx}")
    print(f"Latitude:          {selected_lat:.4f}°")
    print(f"Longitude:         {selected_lon:.4f}°")
    print(f"Total Channels:    {channel_ids.size}\n")

    # 3. Pure BUFR Header Scale Factor Calculation (No physical override safeguards)
    scale_factors = np.zeros(channel_ids.size, dtype=np.float64)
    matched = np.zeros(channel_ids.size, dtype=bool)

    if scale_exp is not None and np.size(scale_exp) > 0:
        scale_start_arr = np.atleast_2d(np.asarray(scale_start))
        scale_end_arr = np.atleast_2d(np.asarray(scale_end))
        scale_exp_arr = np.atleast_2d(np.asarray(scale_exp))

        scale_row = selected_idx if selected_idx < scale_start_arr.shape[0] else 0
        st_vals = scale_start_arr[scale_row, :10]
        en_vals = scale_end_arr[scale_row, :10]
        exp_vals = scale_exp_arr[scale_row, :10]

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

            scale_factors[group_mask] = sf_group
            matched[group_mask] = True

    # 4. Compute Radiance and Brightness Temperature
    radiance = selected_scra * scale_factors
    wavenumbers = iasi_channel_to_wavenumber(channel_ids)
    brightness_temp = radiance_to_bt(radiance, wavenumbers)
    brightness_temp = np.where((brightness_temp >= 180.0) & (brightness_temp <= 320.0), brightness_temp, np.nan)

    # Sort channels by wavenumber for continuous plotting
    order = np.argsort(wavenumbers)
    wn_sorted = wavenumbers[order]
    rad_sorted = radiance[order]
    bt_sorted = brightness_temp[order]
    sf_sorted = scale_factors[order]

    # 5. Plot Vertical 3-Panel Figure (Portrait Layout)
    fig, axes = plt.subplots(3, 1, figsize=(10, 14), sharex=True)

    # --- TOP PANEL: RADIANCE ---
    axes[0].plot(
        wn_sorted,
        rad_sorted,
        color="navy",
        linestyle="",
        marker="o",
        markersize=1.8,
        label="Observed Channels",
    )
    axes[0].set_title(
        f"IASI Spectrum @ Lat: {selected_lat:.2f}°, Lon: {selected_lon:.2f}° (Obs #{selected_idx})",
        fontsize=13,
        pad=10,
    )
    axes[0].set_ylabel(
        r"Radiance" "\n" r"($\mathrm{mW} \cdot \mathrm{m}^{-2} \cdot \mathrm{sr}^{-1} \cdot \mathrm{cm}$)",
        fontsize=11,
    )
    axes[0].grid(True, linestyle="--", alpha=0.5)
    axes[0].set_ylim(bottom=0)

    # Spectral Band Overlays
    axes[0].axvspan(645, 780, color="red", alpha=0.08, label=r"$\mathrm{CO}_2$ Temp Band")
    axes[0].axvspan(780, 980, color="green", alpha=0.08, label="Surface Window")
    axes[0].axvspan(980, 1070, color="orange", alpha=0.08, label=r"$\mathrm{O}_3$ Ozone Band")
    axes[0].axvspan(1070, 1200, color="green", alpha=0.05)
    axes[0].axvspan(1200, 2000, color="blue", alpha=0.08, label=r"$\mathrm{H}_2\mathrm{O}$ Band")
    axes[0].legend(loc="upper right", frameon=True, fontsize=9)

    # --- MIDDLE PANEL: BRIGHTNESS TEMPERATURE ---
    axes[1].plot(
        wn_sorted,
        bt_sorted,
        color="crimson",
        linestyle="-",
        linewidth=0.7,
        alpha=0.9,
    )
    axes[1].set_ylabel("Brightness Temp\n(K)", fontsize=11)
    axes[1].grid(True, linestyle="--", alpha=0.5)

    # --- BOTTOM PANEL: SCALE FACTOR ---
    axes[2].plot(
        wn_sorted,
        sf_sorted,
        color="teal",
        linestyle="-",
        linewidth=1.0,
    )
    axes[2].set_xlabel(r"Wavenumber ($\mathrm{cm}^{-1}$)", fontsize=12)
    axes[2].set_ylabel("Scale Factor", fontsize=11)
    axes[2].set_yscale("log")
    axes[2].set_xlim(640, 2050)
    axes[2].grid(True, linestyle="--", alpha=0.5)

    plt.tight_layout()
    plt.savefig(output_img, dpi=300, bbox_inches="tight")
    plt.close(fig)
    print(f"Vertical PNG successfully saved to: {output_img}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Plot single point IASI spectrum across all channels.")
    parser.add_argument("bufr_file", help="Path to BUFR tank file")
    parser.add_argument("--lat", type=float, help="Target Latitude")
    parser.add_argument("--lon", type=float, help="Target Longitude")
    parser.add_argument("--idx", type=int, help="Exact Observation Index (0 to N-1)")
    parser.add_argument("--output", default="iasi_single_point_spectrum.png", help="Output filename")
    parser.add_argument("--force", action="store_true", help="Force reprocessing of raw BUFR cache")

    args = parser.parse_args()
    plot_single_point_radiance(
        args.bufr_file,
        target_lat=args.lat,
        target_lon=args.lon,
        obs_index=args.idx,
        output_img=args.output,
        force_reprocess=args.force,
    )
