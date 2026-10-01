import xarray as xr
import pandas as pd
import numpy as np

def inspect_bt_differences(file_obsforge, file_geode, max_rows_to_show=30, diff_threshold=0.01):
    """
    Aligns Obsforge and Geode ATMS files spatial-temporally and exports
    a row-by-row table of BT differences for each channel.
    """
    print("Loading datasets...")
    meta_obs = xr.open_dataset(file_obsforge, group='MetaData')
    obs_obs  = xr.open_dataset(file_obsforge, group='ObsValue')
    
    meta_geo = xr.open_dataset(file_geode, group='MetaData')
    obs_geo  = xr.open_dataset(file_geode, group='ObsValue')

    # 1. Clean Lat/Lon
    lat_obs = meta_obs['latitude'].values
    lon_obs = meta_obs['longitude'].values
    scan_obs = meta_obs['sensorScanPosition'].values

    lat_geo = meta_geo['latitude'].values
    lon_geo = meta_geo['longitude'].values
    scan_geo = meta_geo['sensorScanPosition'].values

    # 2. Extract Brightness Temperatures
    tb_obs = obs_obs['brightnessTemperature'].values  # Shape: (Location, Channel)
    tb_geo = obs_geo['brightnessTemperature'].values

    # 3. Mask Fill / Invalid Outlier Values (> 1000 K)
    tb_obs = np.where(tb_obs > 1000.0, np.nan, tb_obs)
    tb_geo = np.where(tb_geo > 1000.0, np.nan, tb_geo)

    # 4. Construct Row-by-Row Comparison DataFrame
    # Flattening location and channel dimensions into long format
    n_locs, n_chans = tb_obs.shape

    print("Building long-format comparison table...")
    
    # Repeat spatial coordinates for each channel
    lat_flat = np.repeat(lat_obs, n_chans)
    lon_flat = np.repeat(lon_obs, n_chans)
    scan_flat = np.repeat(scan_obs, n_chans)
    chan_flat = np.tile(np.arange(1, n_chans + 1), n_locs)

    bt_obs_flat = tb_obs.flatten()
    bt_geo_flat = tb_geo.flatten()

    # Calculate absolute delta
    diff_flat = np.abs(bt_obs_flat - bt_geo_flat)

    df_all = pd.DataFrame({
        'lat': lat_flat,
        'lon': lon_flat,
        'scan_pos': scan_flat,
        'channel': chan_flat,
        'BT_obsforge': bt_obs_flat,
        'BT_geode': bt_geo_flat,
        'diff_abs': diff_flat
    })

    # Filter out rows where both are NaN or difference is below threshold
    df_diff = df_all.dropna(subset=['BT_obsforge', 'BT_geode']).copy()
    df_diff = df_diff[df_diff['diff_abs'] >= diff_threshold]

    # Sort by largest difference
    df_diff = df_diff.sort_values(by='diff_abs', ascending=False)

    print("\n" + "=" * 90)
    print(f" TOP {max_rows_to_show} LARGEST BRIGHTNESS TEMPERATURE DIFFERENCES (|BT_obs - BT_geo| >= {diff_threshold} K)")
    print("=" * 90)

    # Format printing layout
    pd.set_option('display.max_columns', None)
    pd.set_option('display.width', 1000)
    pd.set_option('display.float_format', lambda x: f'{x:.4f}')

    out_cols = ['lat', 'lon', 'scan_pos', 'channel', 'BT_obsforge', 'BT_geode', 'diff_abs']
    print(df_diff[out_cols].head(max_rows_to_show).to_string(index=False))

    # Summary Stats on Differences
    print("\n" + "=" * 90)
    print(" DIFFERENCE SUMMARY Across All Valid Observations:")
    print("=" * 90)
    print(f" Total matched location-channel pairs : {len(df_all):,}")
    print(f" Pairs with |diff| >= {diff_threshold} K        : {len(df_diff):,} ({len(df_diff)/len(df_all)*100:.2f}%)")
    print(f" Maximum BT Difference                : {df_all['diff_abs'].max():.4f} K")
    print(f" Mean Absolute BT Difference          : {df_all['diff_abs'].mean():.4f} K")
    print(f" Median Absolute BT Difference        : {df_all['diff_abs'].median():.4f} K")

    # Optionally Save to CSV
    df_diff[out_cols].to_csv("atms_bt_differences.csv", index=False)
    print("\n[+] Full table of differences exported to 'atms_bt_differences.csv'")

    meta_obs.close(); obs_obs.close()
    meta_geo.close(); obs_geo.close()

if __name__ == "__main__":
    file_obsforge = "/scratch3/NCEPDEV/da/Hyundeok.Choi/geode_tmp/obsforge/20260915/gdas.t00z.radiance_atms_n20.nc"
    file_geode = "/scratch3/NCEPDEV/da/Hyundeok.Choi/geode_tmp/icechunk2ioda/20260915/gdas.t00z.radiance_atms_n20.nc"
    
    inspect_bt_differences(file_obsforge, file_geode, max_rows_to_show=30, diff_threshold=0.01)
