from datetime import datetime

from geode.ingest import ingestors


class TacGTSReader:
    """Placeholder consumer for ingesting TAC GTS (ASCII text) reports."""

    def ingest(
        self,
        data_type: str,
        file_paths: list[str],
        reference_datetime: datetime | None = None,
        include_raw_code: bool = False,
    ) -> None:
        """Dispatch TAC files to their registered format ingestors.

        Parameters
        ----------
        data_type : str
            TAC report type, such as ``temp``.
        file_paths : list[str]
            Paths to TAC bulletin files.
        reference_datetime : datetime | None
            Timezone-aware acquisition/reference timestamp for resolving
            TEMP's day/hour groups to an absolute date.
        include_raw_code : bool, default=False
            Include original TEMP groups as one ``MetaData/rawCode`` variable.

        Returns
        -------
        None

        Examples
        --------
        Supply the bulletin receipt time when ingesting TEMP so its day/hour
        fields can be assigned to the correct month and year.
        """
        # TODO: gather TAC report file paths for the requested data_type/date range
        ingestor_class = ingestors.make(f"tac/{data_type}")

        if ingestor_class:
            for file_path in file_paths:
                ingestor = ingestor_class(
                    reference_datetime=reference_datetime,
                    include_raw_code=include_raw_code,
                )
                ingestor.process(file_path)
