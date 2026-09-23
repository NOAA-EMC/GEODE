# test.py
from pathlib import Path

from datastore import IcechunkDataStore
from catalog.marine import MarineCatalog
from catalog.atmos import AtmosCatalog

ICECHUNK_ROOT = Path("demo_icechunk")
MARINE_ROOT = Path("demo_marine_catalog")
ATMOS_ROOT = Path("demo_atmos_catalog")


def main() -> None:
    store = IcechunkDataStore(ICECHUNK_ROOT)

    # 1. Marine Catalog
    marine = MarineCatalog()
    marine_products = [
        ("argo", "marine_nc_data/gdas.t06z.insitu_profile_argo.2021063006.nc"),
        ("glider", "marine_nc_data/gdas.t06z.insitu_profile_glider.2021063006.nc"),
    ]

    for address, nc_rel in marine_products:
        nc_path = Path(nc_rel)
        if nc_path.exists():
            print(f"Registering NetCDF into Icechunk: {address}...")
            store.register_netcdf(nc_path, address)

        meta = store.metadata(address)
        marine.add_product(
            address=address,
            netcdf_file=nc_path,
            start_datetime=meta["start_datetime"],
            end_datetime=meta["end_datetime"],
            attributes=meta["attributes"],
            data_store_location=store.location(address),
            bbox=meta["bbox"],
            geometry=meta["geometry"],
        )

    marine.save(MARINE_ROOT)
    print("\n=== Marine STAC Catalog Output ===")
    marine.inspect()

    # 2. Atmos Catalog
    atmos = AtmosCatalog()
    atmos_products = [
        ("viirs_n20", "atmos_nc_data/gdas.t00z.retrieval_amv_viirs_n20.nc"),
        ("avhrr_n18", "atmos_nc_data/gdas.t00z.retrieval_amv_avhrr_n18.nc"),
    ]

    for address, nc_rel in atmos_products:
        nc_path = Path(nc_rel)
        if nc_path.exists():
            print(f"Registering NetCDF into Icechunk: {address}...")
            store.register_netcdf(nc_path, address)

        meta = store.metadata(address)
        atmos.add_product(
            address=address,
            netcdf_file=nc_path,
            start_datetime=meta["start_datetime"],
            end_datetime=meta["end_datetime"],
            attributes=meta["attributes"],
            data_store_location=store.location(address),
            bbox=meta["bbox"],
            geometry=meta["geometry"],
        )

    atmos.save(ATMOS_ROOT)
    print("\n=== Atmos STAC Catalog Output ===")
    atmos.inspect()


if __name__ == "__main__":
    main()
