from datetime import datetime, timezone
from pathlib import Path

from datastore import IcechunkDataStore
from domains.atmos import AtmosCatalog
from domains.marine import MarineCatalog

ICECHUNK_ROOT = Path("demo_icechunk")
MARINE_DATA_ROOT = Path("marine_nc_data")


def main():
    store = IcechunkDataStore(ICECHUNK_ROOT)

    # ------------------------------------------------------------
    # 1. Marine Catalog
    # ------------------------------------------------------------

    marine = MarineCatalog(datastore=store)

    for nc_file in sorted(MARINE_DATA_ROOT.glob("*.nc")):
        marine.add_product(
            nc_file.stem,
            nc_file,
        )

    print("\n=== Marine Catalog ===")
    print(f"Collections: {list(marine.collections)}")
    print(
        f"Items: {len(list(marine._catalog.get_all_items()))}"
    )

    # ------------------------------------------------------------
    # 2. Query: Marine products in a geographic region
    # ------------------------------------------------------------

    print("\n=== QUERY 1: Marine products in North Atlantic ===")

    items = marine.search(
        bbox=[-80.0, 20.0, 0.0, 70.0],
    )

    for item in items:
        print(f"  {item.id}")

#     # ------------------------------------------------------------
#     # 3. Query: Marine products in a time window
#     # ------------------------------------------------------------
# 
#     print("\n=== QUERY 2: Marine products during June 30, 2021 ===")
# 
#     items = marine.search(
#         datetime_range=(
#             datetime(2021, 6, 30, 0, 0, tzinfo=timezone.utc),
#             datetime(2021, 6, 30, 12, 0, tzinfo=timezone.utc),
#         ),
#     )
# 
#     for item in items:
#         print(
#             f"  {item.id}: "
#             f"{item.common_metadata.start_datetime} → "
#             f"{item.common_metadata.end_datetime}"
#         )
# 
#     # ------------------------------------------------------------
#     # 4. Query: Specific product type
#     # ------------------------------------------------------------
# 
#     print("\n=== QUERY 3: Marine in-situ profile products ===")
# 
#     items = marine.search(
#         properties={
#             "description": "6-hrly in situ ARGO profiles",
#         }
#     )
# 
#     for item in items:
#         print(f"  {item.id}")
# 
#     # ------------------------------------------------------------
#     # 5. Query: Combine spatial + temporal + property filters
#     # ------------------------------------------------------------
# 
#     print(
#         "\n=== QUERY 4: ARGO products in North Atlantic "
#         "during June 30, 2021 ==="
#     )
# 
#     items = marine.search(
#         bbox=[-80.0, 20.0, 0.0, 70.0],
#         datetime_range=(
#             datetime(2021, 6, 30, 0, 0, tzinfo=timezone.utc),
#             datetime(2021, 6, 30, 12, 0, tzinfo=timezone.utc),
#         ),
#         properties={
#             "description": "6-hrly in situ ARGO profiles",
#         },
#     )
# 
#     for item in items:
#         print(f"  {item.id}")

    # ------------------------------------------------------------
    # 4. Query: Products from a particular observation network
    # ------------------------------------------------------------

    print("\n=== QUERY 3: PIRATA products ===")

    items = marine.search(
        properties={
            "source": "NCEP data tank",
            "sourceFiles": "2025061900-gdas.t00z.subpfl.tm00.bufr_d",
        }
    )

    for item in items:
        print(f"  {item.id}")

    # ------------------------------------------------------------
    # 5. Query: Spatial + temporal filtering
    # ------------------------------------------------------------

    print(
        "\n=== QUERY 4: North Atlantic products with waterTemperature "
        "during June 30, 2021 ==="
    )
    items = marine.search(
        bbox=[-80.0, 20.0, 0.0, 70.0],
        datetime_range=(
            datetime(2021, 6, 30, 0, 0, tzinfo=timezone.utc),
            datetime(2021, 6, 30, 12, 0, tzinfo=timezone.utc),
        ),
        properties={
            "measurement_variables": "waterTemperature",
        },
    )

    for item in items:
        print(f"  {item.id}")

    # ------------------------------------------------------------
    # 6. Search products, then inspect their actual contents
    # ------------------------------------------------------------

    print(
        "\n=== QUERY 5: North Atlantic products "
        "and their variables ==="
    )

    items = marine.search(
        bbox=[-80.0, 20.0, 0.0, 70.0],
        datetime_range=(
            datetime(2021, 6, 30, 0, 0, tzinfo=timezone.utc),
            datetime(2021, 6, 30, 12, 0, tzinfo=timezone.utc),
        ),
    )

    for item in items:
        print(f"\n  {item.id}")

        datasets = marine.load_dataset(item)

        for group_name, dataset in datasets.items():
            print(
                f"    {group_name}: "
                f"{list(dataset.data_vars)}"
            )

    # ------------------------------------------------------------
    # 6. Load the products returned by the query
    # ------------------------------------------------------------

    print("\n=== QUERY 5: Search and load ARGO ===")

    results = marine.search_and_load(
        datetime_range=(
            datetime(2021, 6, 30, 0, 0, tzinfo=timezone.utc),
            datetime(2021, 6, 30, 12, 0, tzinfo=timezone.utc),
        ),
        properties={
            "description": "6-hrly in situ ARGO profiles",
        },
    )

    for item_id, groups in results.items():
        print(f"  Loaded: {item_id}")
        print(
            f"    ObsValue: "
            f"{list(groups['ObsValue'].data_vars)}"
        )
        print(
            f"    MetaData: "
            f"{list(groups['MetaData'].data_vars)[:6]}"
        )

    # ------------------------------------------------------------
    # 7. Atmos Catalog
    # ------------------------------------------------------------

    atmos = AtmosCatalog(datastore=store)

    atmos.add_product(
        "viirs_n20",
        "atmos_nc_data/gdas.t00z.retrieval_amv_viirs_n20.nc",
    )

    atmos.add_product(
        "avhrr_n18",
        "atmos_nc_data/gdas.t00z.retrieval_amv_avhrr_n18.nc",
    )

    print("\n=== QUERY 6: Atmos products from VIIRS ===")

    items = atmos.search(
        properties={
            "sensorCommonName": "VIIRS",
        }
    )

    for item in items:
        print(f"  {item.id}")

    # ------------------------------------------------------------
    # 8. Demonstrate the STAC boundary
    # ------------------------------------------------------------

    print("\n=== QUERY 7: Observation-level query ===")
    print(
        "STAC can identify the ARGO product, but cannot directly "
        "query individual observations such as:"
    )
    print("  salinity > 35")
    print("  depth < 100 m")
    print("  5 < waterTemperature < 10")


if __name__ == "__main__":
    main()
