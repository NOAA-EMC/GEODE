from datetime import datetime, timezone
from pathlib import Path

from catalog.atmos import AtmosCatalog
from catalog.marine import MarineCatalog
from catalog.search import STACQueryEngine
from datastore import IcechunkDataStore

ICECHUNK_ROOT = Path("demo_icechunk")

def main():
    store = IcechunkDataStore(ICECHUNK_ROOT)

    # 1. Populate Catalogs from Datastore
    marine_cat = MarineCatalog()
    for address, nc_rel in [
        ("argo", "marine_nc_data/gdas.t06z.insitu_profile_argo.2021063006.nc"),
        ("glider", "marine_nc_data/gdas.t06z.insitu_profile_glider.2021063006.nc"),
    ]:
        meta = store.metadata(address)
        marine_cat.add_product(
            address=address,
            netcdf_file=Path(nc_rel),
            start_datetime=meta["start_datetime"],
            end_datetime=meta["end_datetime"],
            attributes=meta["attributes"],
            data_store_location=store.location(address),
            bbox=meta["bbox"],
            geometry=meta["geometry"],
        )

    atmos_cat = AtmosCatalog()
    for address, nc_rel in [
        ("viirs_n20", "atmos_nc_data/gdas.t00z.retrieval_amv_viirs_n20.nc"),
        ("avhrr_n18", "atmos_nc_data/gdas.t00z.retrieval_amv_avhrr_n18.nc"),
    ]:
        meta = store.metadata(address)
        atmos_cat.add_product(
            address=address,
            netcdf_file=Path(nc_rel),
            start_datetime=meta["start_datetime"],
            end_datetime=meta["end_datetime"],
            attributes=meta["attributes"],
            data_store_location=store.location(address),
            bbox=meta["bbox"],
            geometry=meta["geometry"],
        )

    # 2. Test Queries
    print("=== TEST 1: Query Atmos by Sensor (VIIRS) ===")
    engine_atmos = STACQueryEngine(atmos_cat.catalog._catalog)
    results = engine_atmos.search(properties={"sensorCommonName": "VIIRS"})
    for item in results:
        print(f"Matched Item: {item.id}")

    print("\n=== TEST 2: Query Marine by Datetime Interval ===")
    engine_marine = STACQueryEngine(marine_cat.catalog._catalog)
    # Target interval around 2021-06-30 05:00 UTC
    query_start = datetime(2021, 6, 30, 4, 0, tzinfo=timezone.utc)
    query_end = datetime(2021, 6, 30, 6, 0, tzinfo=timezone.utc)
    results = engine_marine.search(datetime_range=(query_start, query_end))
    for item in results:
        print(f"Matched Item: {item.id} (Start: {item.common_metadata.start_datetime})")

if __name__ == "__main__":
    main()
