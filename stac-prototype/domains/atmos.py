from __future__ import annotations

from catalog import Catalog
from datastore import IcechunkDataStore


class AtmosCatalog(Catalog):
    """Atmospheric observation catalog with domain defaults."""

    def __init__(
        self,
        datastore: IcechunkDataStore,
        id: str = "atmos",
        description: str = "Atmospheric observation products",
    ):
        super().__init__(
            id=id,
            description=description,
            datastore=datastore,
            default_collection_id="atmospheric-motion-vectors",
            default_collection_description="Atmospheric Motion Vector observation products",
            property_keys=[
                "platformCommonName",
                "platformLongDescription",
                "sensorCommonName",
                "sensorLongDescription",
                "source",
                "sourceFiles",
                "processingLevel",
                "converter",
                "description",
            ],
        )
