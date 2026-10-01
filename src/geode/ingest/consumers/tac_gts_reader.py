from geode.ingest import ingestors


class TacGTSReader:
    """Placeholder consumer for ingesting TAC GTS (ASCII text) reports."""

    def ingest(self, data_type: str, file_paths: list[str]) -> None:
        # TODO: gather TAC report file paths for the requested data_type/date range
        ingestor_class = ingestors.make(f"tac/{data_type}")

        if ingestor_class:
            for file_path in file_paths:
                ingestor = ingestor_class()
                ingestor.process(file_path)
