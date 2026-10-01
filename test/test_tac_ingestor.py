import pytest

from geode.ingest.ingestors.tac_ingestor import TacIngestor


def test_tac_ingestor_placeholder():
    ingestor = TacIngestor("temp")

    assert ingestor.data_type == "temp"

    with pytest.raises(NotImplementedError, match="TAC parsing not yet implemented"):
        ingestor._process("unused")