from pathlib import Path

from datastore import IcechunkDataStore
from domains.atmos import AtmosCatalog
from domains.marine import MarineCatalog

ICECHUNK_ROOT = Path("demo_icechunk")
MARINE_DATA_ROOT = Path("marine_nc_data")


def main():
    store = IcechunkDataStore(ICECHUNK_ROOT)

    # 1. Marine Catalog
    marine = MarineCatalog(datastore=store)
    # marine.add_product("argo", "marine_nc_data/gdas.t06z.insitu_profile_argo.2021063006.nc")
    # marine.add_product("glider", "marine_nc_data/gdas.t06z.insitu_profile_glider.2021063006.nc")

    for nc_file in sorted(MARINE_DATA_ROOT.glob("*.nc")):
        address = nc_file.stem
        marine.add_product(
            address,
            nc_file,
        )

    print("\n=== Marine Products ===")
    for item in marine._catalog.get_all_items():
        print(
            f"  {item.id}: "
            f"{item.common_metadata.start_datetime} → "
            f"{item.common_metadata.end_datetime}"
        )

    collection = marine.collections["in-situ-profile"]

    print("\n=== Marine Collection Extent ===")
    print(
        "  Temporal:",
        collection.extent.temporal.intervals[0],
    )
    print(
        "  Spatial:",
        collection.extent.spatial.bboxes[0],
    )

    # 2. Atmos Catalog
    atmos = AtmosCatalog(datastore=store)
    atmos.add_product("viirs_n20", "atmos_nc_data/gdas.t00z.retrieval_amv_viirs_n20.nc")
    atmos.add_product("avhrr_n18", "atmos_nc_data/gdas.t00z.retrieval_amv_avhrr_n18.nc")

    # 3. Test Atmos Search & Load
    print("=== TEST 1: Search & Load Atmos (VIIRS) ===")
    viirs_data = atmos.search_and_load(properties={"sensorCommonName": "VIIRS"})
    for item_id, groups in viirs_data.items():
        print(f"Loaded Item: {item_id}")
        print(f"  MetaData Vars: {list(groups['MetaData'].data_vars.keys())[:3]}")

    # 4. Test Marine Spatial Search & Load
    print("\n=== TEST 2: Search & Load Marine (US West Coast Glider) ===")
    marine_data = marine.search_and_load(
        bbox=[-130.0, 15.0, -100.0, 50.0],
        properties={"description": "6-hrly in situ GLIDER profiles"},
    )
    for item_id, groups in marine_data.items():
        print(f"Loaded Item: {item_id}")
        print(f"  ObsValue Vars: {list(groups['ObsValue'].data_vars.keys())}")


if __name__ == "__main__":
    main()
