import datetime
import logging
import os

from geode.configs.geode_config import geode_config
from geode.configs.table_a_mapping import (
    TankInfo,
    UnmappedTankError,
    table_a_mapping,
    unmapped_tank_info,
)
from geode.ingest import ingestors

logger = logging.getLogger(__name__)

IngestorPrefix = "tank"


class TankConfigError(ValueError):
    """Raised when geode.yaml has no usable ``tank`` section."""


class RestrictedTankError(PermissionError):
    """Raised when a restricted tank is requested without opting in."""


class TankReader:
    """Consume NCEP BUFR tanks of the form ``{root}/YYYYMMDD/bAAA/xxBBB``."""

    def __init__(self):
        if geode_config.tank is None:
            raise TankConfigError(
                "No 'tank' section in geode.yaml; add tank.root_path to read BUFR tanks"
            )
        self.config = geode_config.tank
        self._mpi_app = None

    def get_tank_info(self, tank_id: str) -> TankInfo:
        """Resolve a ``bAAA/xxBBB`` tank ID and enforce the restricted-data policy.

        Unmapped tanks raise ``UnmappedTankError`` unless ``tank.allow_unmapped``
        is set, in which case they get a ``bAAA_xxBBB`` dataset name.
        """
        try:
            info = table_a_mapping.get(tank_id)
        except UnmappedTankError as error:
            if not self.config.allow_unmapped:
                raise UnmappedTankError(
                    f"{error}; add it to the mapping or set "
                    "tank.allow_unmapped: true in geode.yaml"
                ) from error
            info = unmapped_tank_info(tank_id)
            logger.warning(
                f"BUFR tank '{info.tank_id}' is not in {table_a_mapping.mapping_path}; "
                f"using fallback dataset name '{info.dataset}'"
            )

        if info.restricted and not self.config.include_restricted:
            raise RestrictedTankError(
                f"BUFR tank '{info.tank_id}' ({info.dataset}) is restricted; set "
                "tank.include_restricted: true in geode.yaml to ingest it"
            )
        return info

    def get_file_paths(
        self, tank_id: str, start_date: datetime.datetime, end_date: datetime.datetime
    ) -> list[str]:
        """Return existing tank files for each day in [start_date, end_date]."""
        file_paths = []
        day = start_date
        while day <= end_date:
            path = self.config.get_file_path(tank_id, day)
            if os.path.isfile(path):
                file_paths.append(path)
            else:
                logger.info(f"No BUFR tank file for {tank_id} on {day:%Y%m%d}: {path}")
            day += datetime.timedelta(days=1)
        return file_paths

    def ingest(
        self, tank_id: str, start_date: datetime.datetime, end_date: datetime.datetime
    ) -> str:
        """Ingest a BUFR tank over a date range and return its dataset name."""
        info = self.get_tank_info(tank_id)
        file_paths = self.get_file_paths(info.tank_id, start_date, end_date)
        logger.info(
            f"BUFR tank {info.tank_id} -> dataset '{info.dataset}' "
            f"({info.format}); {len(file_paths)} file(s) found"
        )

        ingestor_class = self._find_ingestor(info)
        if ingestor_class is None:
            logger.warning(
                f"No ingestor registered for '{IngestorPrefix}/{info.tank_id}' or "
                f"'{IngestorPrefix}/{info.dataset}'; skipping {len(file_paths)} file(s)"
            )
            return info.dataset

        self._init_mpi()
        for file_path in file_paths:
            ingestor = ingestor_class(info)
            ingestor.process(file_path)

        return info.dataset

    @staticmethod
    def _find_ingestor(info: TankInfo) -> type | None:
        """Prefer a tank-specific ingestor, then fall back to a per-dataset one."""
        registered = ingestors.directory()
        for key in (info.tank_id, info.dataset):
            ingestor_id = f"{IngestorPrefix}/{key}"
            if ingestor_id in registered:
                return ingestors.make(ingestor_id)
        return None

    def _init_mpi(self) -> None:
        # Deferred so mapping/path resolution works without starting the bufr MPI app
        if self._mpi_app is None:
            import sys

            import bufr

            self._mpi_app = bufr.mpi.App(sys.argv)
