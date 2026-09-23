from __future__ import annotations

from catalog import Catalog
from datastore import IcechunkDataStore


class MarineCatalog(Catalog):
    """Marine observation catalog with domain defaults."""

    def __init__(
        self,
        datastore: IcechunkDataStore,
        id: str = "marine",
        description: str = "Marine observation products",
    ):
        super().__init__(
            id=id,
            description=description,
            datastore=datastore,
            default_collection_id="in-situ-profile",
            default_collection_description="Marine in-situ profile observation products",
            property_keys=[
                "dataProviderOrigin",
                "source",
                "sourceFiles",
                "description",
            ],
        )
