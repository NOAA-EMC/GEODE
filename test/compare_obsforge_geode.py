import xarray as xr
import pandas as pd
import numpy as np

def compare_jedi_atms_files(file_obsforge, file_geode):
    print("=" * 80)
    print(" ATMS JEDI NETCDF COMPARISON REPORT")
    print("=" * 80)

    # 1. Load MetaData and ObsValue groups separately
    meta_obs = xr.open_dataset(file_obsforge, group='MetaData')
    obs_obs  = xr.open_dataset(file_obsforge, group='ObsValue')
    
    meta_geo = xr.open_dataset(file_geode, group='MetaData')
    obs_geo  = xr.open_dataset(file_geode, group='ObsValue')

    # 2. Count Total Locations
    n_obs = meta_obs.sizes['Location']
    n_geo = meta_geo.sizes['Location']

    print(f"\n[1] Observation Counts (Location Dimension):")
    print(f"  - Obsforge Location Count : {n_obs:,}")
    print(f"  - Geode Location Count    : {n_geo:,}")
    print(f"  - Difference (Obs - Geo)  : {n_obs - n_geo:,}")

    # 3. Build Unique Observation Signatures
    # Creating a unique tuple (lat, lon, dateTime, scan_pos) per Location
    def get_obs_keys(ds_meta):
        lats = np.round(ds_meta['latitude'].values, 4)
        lons = np.round(ds_meta['longitude'].values, 4)
        times = ds_meta['dateTime'].values
        scan_pos = ds_meta['sensorScanPosition'].values
        
        return [f"{lat}_{lon}_{time}_{scan}" for lat, lon, time, scan in zip(lats, lons, times, scan_pos)]

    print("\nCreating observation keys for set comparison...")
    keys_obs = get_obs_keys(meta_obs)
    keys_geo = get_obs_keys(meta_geo)

    set_obs = set(keys_obs)
    set_geo = set(keys_geo)

    only_obs = set_obs - set_geo
    only_geo = set_geo - set_obs
    common_obs = set_obs.intersection(set_geo)

    print(f"\n[2] Missing Observation Analysis:")
    print(f"  - Common observations in both          : {len(common_obs):,}")
    print(f"  - Unique to Obsforge (Missing in Geode) : {len(only_obs):,}")
    print(f"  - Unique to Geode (Missing in Obsforge) : {len(only_geo):,}")

    if only_obs:
        print("\n  Sample missing keys in Geode (Lat_Lon_DateTime_ScanPos):")
        for k in list(only_obs)[:3]:
            print(f"    - {k}")
            
    if only_geo:
        print("\n  Sample missing keys in Obsforge (Lat_Lon_DateTime_ScanPos):")
        for k in list(only_geo)[:3]:
            print(f"    - {k}")

    # 4. Comparative Statistics for MetaData
    print("\n[3] MetaData Statistics Comparison:")
    meta_stats = []
    
    for var in meta_obs.data_vars:
        if np.issubdtype(meta_obs[var].dtype, np.number):
            v_obs = meta_obs[var].values
            v_geo = meta_geo[var].values
            
            # Mask fill values if present
            fill_val = meta_obs[var].attrs.get('_FillValue', None)
            if fill_val is not None:
                v_obs = np.where(v_obs == fill_val, np.nan, v_obs)
                v_geo = np.where(v_geo == fill_val, np.nan, v_geo)

            meta_stats.append({
                'Variable': var,
                'Source': 'Obsforge',
                'Min': np.nanmin(v_obs),
                'Max': np.nanmax(v_obs),
                'Mean': np.nanmean(v_obs),
                'Median': np.nanmedian(v_obs)
            })
            meta_stats.append({
                'Variable': var,
                'Source': 'Geode',
                'Min': np.nanmin(v_geo),
                'Max': np.nanmax(v_geo),
                'Mean': np.nanmean(v_geo),
                'Median': np.nanmedian(v_geo)
            })

    df_meta = pd.DataFrame(meta_stats)
    pd.set_option('display.max_columns', None)
    pd.set_option('display.width', 1000)
    print(df_meta.to_string(index=False))

    # 5. Brightness Temperature Channel-by-Channel Statistics
    print("\n[4] ObsValue / brightnessTemperature Statistics (Channel-by-Channel):")
    tb_obs = obs_obs['brightnessTemperature'].values  # Shape: (Location, Channel)
    tb_geo = obs_geo['brightnessTemperature'].values

    # Handle fill value
    fill_val_tb = obs_obs['brightnessTemperature'].attrs.get('_FillValue', 3.402823e+38)
    tb_obs = np.where(tb_obs >= fill_val_tb * 0.9, np.nan, tb_obs)
    tb_geo = np.where(tb_geo >= fill_val_tb * 0.9, np.nan, tb_geo)

    tb_stats = []
    n_channels = tb_obs.shape[1] if tb_obs.ndim > 1 else 1
    
    for ch in range(n_channels):
        ch_obs = tb_obs[:, ch]
        ch_geo = tb_geo[:, ch]
        
        tb_stats.append({
            'Channel': ch + 1,
            'Obs_Min': np.nanmin(ch_obs),
            'Geo_Min': np.nanmin(ch_geo),
            'Obs_Max': np.nanmax(ch_obs),
            'Geo_Max': np.nanmax(ch_geo),
            'Obs_Mean': np.nanmean(ch_obs),
            'Geo_Mean': np.nanmean(ch_geo),
            'Obs_Median': np.nanmedian(ch_obs),
            'Geo_Median': np.nanmedian(ch_geo),
        })

    df_tb = pd.DataFrame(tb_stats)
    print(df_tb.to_string(index=False))

    # Close Datasets
    meta_obs.close(); obs_obs.close()
    meta_geo.close(); obs_geo.close()

# --- Run section ---
if __name__ == "__main__":
    file_obsforge = "/scratch3/NCEPDEV/da/Hyundeok.Choi/geode_tmp/obsforge/20260915/gdas.t00z.radiance_atms_n20.nc"
    file_geode = "/scratch3/NCEPDEV/da/Hyundeok.Choi/geode_tmp/icechunk2ioda/20260915/gdas.t00z.radiance_atms_n20.nc"
    
    compare_jedi_atms_files(file_obsforge, file_geode)
