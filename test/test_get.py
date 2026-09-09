import datetime

import pytest

import geode


def test_get(use_data_lake):
    start_time = datetime.datetime(2024, 1, 1, 0, 0, 0, tzinfo=datetime.UTC)
    end_time = datetime.datetime(2024, 1, 2, 0, 0, 0, tzinfo=datetime.UTC)
    result = geode.get("atms_n20", start_time, end_time)

    assert result is not None


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
