from pathlib import Path

from catalog.atmos import AtmosCatalog
from catalog.search import STACQueryEngine, stac_item_to_dataset
from datastore import IcechunkDataStore

ICECHUNK_ROOT = Path("demo_icechunk")


def main() -> None:
    store = IcechunkDataStore(ICECHUNK_ROOT)

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

    # 1. Search for VIIRS dataset via STAC
    engine = STACQueryEngine(atmos_cat.catalog._catalog)
    results = engine.search(properties={"sensorCommonName": "VIIRS"})

    print(f"Matched STAC Items: {len(results)}")
    stac_item = results[0]
    print(f"Selected Item ID: {stac_item.id}")

    # 2. Materialize to Xarray Datasets via Icechunk Bridge
    datasets = stac_item_to_dataset(stac_item, store)

    print("\n=== Materialized Xarray Datasets ===")
    for group_name, ds in datasets.items():
        print(f"\nGroup: {group_name}")
        print(ds)


if __name__ == "__main__":
    main()
