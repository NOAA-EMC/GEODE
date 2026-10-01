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
    report_text = """583 
USUS04 KWBC 301800
TTAA 80181 72365 99834 17256 22507 00031 ///// ///// 92718 /////
///// 85452 ///// ///// 70068 03634 23013 50572 12558 19513 40739
23358 21025 30946 29375 20047 25074 35373 21558 20228 42172 21563
15417 54967 21554 10668 66562 26017 88999 77233 21572 41809 31313
45408 81702 51515 10164 00000 10194 ///// 20513=
TTAA 80181 72451 99915 19400 13013 00012 ///// ///// 92696 /////
///// 85423 17400 16041 70066 09400 18542 50579 03902 20032 40753
13715 21529 30965 28970 21533 25093 38970 21050 20242 49774 22059
15425 61769 24568 10671 69365 22013 88999 77152 24569 41416 31313
44108 81703=
"""
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
