from pathlib import Path
from catalog.marine import MarineCatalog
from catalog.search import STACQueryEngine
from datastore import IcechunkDataStore

ICECHUNK_ROOT = Path("demo_icechunk")

def main():
    store = IcechunkDataStore(ICECHUNK_ROOT)

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

    engine = STACQueryEngine(marine_cat.catalog._catalog)

    # Note on BBoxes:
    # Argo BBox:   [-174.81, -59.77, 170.49, 76.25]  (Global coverage)
    # Glider BBox: [-127.54,  15.61, -53.66, 47.73]  (North American coastal regions)

    print("=== TEST 1: Query BBox around North Atlantic / US East Coast [-80, 20, -60, 40] ===")
    # Expecting BOTH Argo and Glider
    results = engine.search(bbox=[-80.0, 20.0, -60.0, 40.0])
    for item in results:
        print(f"Matched: {item.id}")

    print("\n=== TEST 2: Query BBox around Indian Ocean / Australia [60, -40, 110, -10] ===")
    # Expecting ONLY Argo (Glider is restricted to West Hemisphere)
    results = engine.search(bbox=[60.0, -40.0, 110.0, -10.0])
    for item in results:
        print(f"Matched: {item.id}")

if __name__ == "__main__":
    main()
