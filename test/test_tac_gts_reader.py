from pathlib import Path

from geode.ingest.consumers import tac_gts_reader
from geode.ingest.ingestors.tac_ingestor import TacIngestor


def test_tac_gts_reader_dispatches_file(tmp_path, monkeypatch):
    """Verify that the TAC GTS consumer dispatches a report to its ingestor.

    Parameters
    ----------
    tmp_path : pathlib.Path
        Temporary directory for the TAC report fixture.
    monkeypatch : pytest.MonkeyPatch
        Fixture used to intercept the ingestor processing boundary.

    Returns
    -------
    None

    Examples
    --------
    Run with ``pytest test/test_tac_gts_reader.py``.
    """
    report_text = "TTAA 01121\n"
    report_path = tmp_path / "temp.tac"
    report_path.write_text(report_text, encoding="ascii")
    processed_reports = []

    def capture_process(ingestor: TacIngestor, file_path: str) -> None:
        processed_reports.append(
            (ingestor.data_type, Path(file_path).read_text(encoding="ascii"))
        )

    monkeypatch.setattr(TacIngestor, "process", capture_process)

    reader = tac_gts_reader.TacGTSReader()
    reader.ingest("temp", [str(report_path)])

    assert processed_reports == [("temp", report_text)]