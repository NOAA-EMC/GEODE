from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

import pystac
import xarray as xr

from datastore import IcechunkDataStore


class Catalog:
    """
    Generic STAC Catalog wrapping an IcechunkDataStore.

    Handles ingestion, search indexing, and data materialization.
    """

    def __init__(
        self,
        id: str,
        description: str,
        datastore: IcechunkDataStore,
        default_collection_id: str = "default-collection",
        default_collection_description: str = "Default Collection",
        property_keys: Sequence[str] | None = None,
    ):
        self.id = id
        self.description = description
        self.datastore = datastore
        self.default_collection_id = default_collection_id
        self.default_collection_description = default_collection_description
        self.property_keys = list(property_keys) if property_keys else []

        self._catalog = pystac.Catalog(id=id, description=description)
        self.collections: dict[str, pystac.Collection] = {}

    def get_or_create_collection(
        self,
        collection_id: str,
        description: str,
        start_datetime: datetime,
        end_datetime: datetime,
        bbox: list[float] | None = None,
    ) -> pystac.Collection:
        """Get or create a STAC collection and update its extent."""

        if collection_id not in self.collections:
            spatial_bbox = (
                bbox
                if bbox is not None
                else [-180.0, -90.0, 180.0, 90.0]
            )

            collection = pystac.Collection(
                id=collection_id,
                description=description,
                extent=pystac.Extent(
                    spatial=pystac.SpatialExtent(
                        bboxes=[spatial_bbox]
                    ),
                    temporal=pystac.TemporalExtent(
                        intervals=[
                            [start_datetime, end_datetime]
                        ]
                    ),
                ),
            )

            self._catalog.add_child(collection)
            self.collections[collection_id] = collection

        else:
            collection = self.collections[collection_id]

            # Expand temporal extent.
            interval = collection.extent.temporal.intervals[0]

            interval[0] = min(
                interval[0],
                start_datetime,
            )
            interval[1] = max(
                interval[1],
                end_datetime,
            )

            # Expand spatial extent.
            if bbox is not None:
                current_bbox = collection.extent.spatial.bboxes[0]

                current_bbox[0] = min(
                    current_bbox[0],
                    bbox[0],
                )
                current_bbox[1] = min(
                    current_bbox[1],
                    bbox[1],
                )
                current_bbox[2] = max(
                    current_bbox[2],
                    bbox[2],
                )
                current_bbox[3] = max(
                    current_bbox[3],
                    bbox[3],
                )

        return collection

    def add_product(
        self,
        address: str,
        nc_file: str | Path,
        collection_id: str | None = None,
        collection_description: str | None = None,
        branch: str = "main",
    ) -> pystac.Item:
        """
        Register a NetCDF file into Icechunk, request normalized metadata
        from the Datastore, and index it into standard STAC structures.
        """
        nc_path = Path(nc_file)

        # 1. Datastore handles storage registration
        registration = self.datastore.register_netcdf(
            nc_path,
            address=address,
        )

        # 2. Datastore inspects data and provides standardized metadata
        meta = self.datastore.metadata(address)

        cid = collection_id or self.default_collection_id
        cdesc = collection_description or self.default_collection_description

        collection = self.get_or_create_collection(
            collection_id=cid,
            description=cdesc,
            start_datetime=meta["start_datetime"],
            end_datetime=meta["end_datetime"],
            bbox=meta["bbox"],
        )

        filename = nc_path.name
        item_id = filename.removesuffix(".nc")

        if self.property_keys:
            extracted_props = {
                k: meta["attributes"][k]
                for k in self.property_keys
                if k in meta["attributes"]
            }
        else:
            extracted_props = dict(meta["attributes"])

        extracted_props["measurement_variables"] = (
            registration["variables"].get("ObsValue", [])
        )

        start_dt = meta["start_datetime"]
        end_dt = meta["end_datetime"]
        dt = start_dt if start_dt == end_dt else None

        item = pystac.Item(
            id=item_id,
            geometry=meta["geometry"],
            bbox=meta["bbox"],
            datetime=dt,
            properties=extracted_props,
            start_datetime=start_dt if dt is None else None,
            end_datetime=end_dt if dt is None else None,
        )

        asset = pystac.Asset(
            href=self.datastore.location(address),
            title=filename,
            roles=["data", "zarr"],
            extra_fields={
                "icechunk:repository": self.datastore.location(address),
                "icechunk:branch": branch,
                "icechunk:group": f"/{address}",
                "icechunk:address": address,
            },
        )
        item.add_asset("zarr", asset)
        collection.add_item(item)
        return item

    def search(
        self,
        bbox: list[float] | tuple[float, float, float, float] | None = None,
        datetime_range: tuple[datetime, datetime] | None = None,
        properties: dict[str, Any] | None = None,
    ) -> list[pystac.Item]:
        """Search catalog items by spatial bbox, temporal window, and properties."""
        matched = []
        all_items = list(self._catalog.get_all_items())

        for item in all_items:
            # Spatial BBox Matching
            if bbox is not None:
                if item.bbox is None:
                    continue
                q_min_lon, q_min_lat, q_max_lon, q_max_lat = bbox
                i_min_lon, i_min_lat, i_max_lon, i_max_lat = item.bbox

                if (
                    i_min_lon > q_max_lon
                    or i_max_lon < q_min_lon
                    or i_min_lat > q_max_lat
                    or i_max_lat < q_min_lat
                ):
                    continue

            # Temporal Range Matching
            if datetime_range is not None:
                q_start, q_end = datetime_range

                if q_start.tzinfo is None:
                    q_start = q_start.replace(tzinfo=timezone.utc)
                if q_end.tzinfo is None:
                    q_end = q_end.replace(tzinfo=timezone.utc)

                item_start = item.common_metadata.start_datetime or item.datetime
                item_end = item.common_metadata.end_datetime or item.datetime

                if item_start is None or item_end is None:
                    continue

                if q_end < item_start or q_start > item_end:
                    continue

            # Property Key-Value Matching
            if properties is not None:
                match_props = True
                for p_key, p_val in properties.items():
                    actual = item.properties.get(p_key)

                    if isinstance(actual, list):
                        if p_val not in actual:
                            match_props = False
                            break
                    elif actual != p_val:
                        match_props = False
                        break

                if not match_props:
                    continue

            matched.append(item)

        return matched

    def load_dataset(self, item: pystac.Item, asset_key: str = "zarr") -> dict[str, xr.Dataset]:
        """Materialize xarray Datasets directly from a matched STAC Item."""
        if asset_key not in item.assets:
            raise KeyError(f"Asset '{asset_key}' not found in STAC Item '{item.id}'")

        asset = item.assets[asset_key]
        extra = asset.extra_fields

        branch = extra.get("icechunk:branch", "main")
        group = extra.get("icechunk:group")
        address = extra.get("icechunk:address")

        if address is None:
            raise ValueError(f"Missing 'icechunk:address' in asset '{asset_key}'")

        return self.datastore.open_dataset(address=address, group=group, branch=branch)

    def search_and_load(
        self,
        bbox: list[float] | tuple[float, float, float, float] | None = None,
        datetime_range: tuple[datetime, datetime] | None = None,
        properties: dict[str, Any] | None = None,
    ) -> dict[str, dict[str, xr.Dataset]]:
        """Search and materialize matching datasets in a single call."""
        items = self.search(bbox=bbox, datetime_range=datetime_range, properties=properties)
        return {item.id: self.load_dataset(item) for item in items}

    def save(self, root: str | Path) -> None:
        self._catalog.normalize_hrefs(str(root))
        self._catalog.save(catalog_type=pystac.CatalogType.SELF_CONTAINED)
