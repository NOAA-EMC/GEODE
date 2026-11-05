import importlib.util
import logging
import os
import subprocess
import sys

import pytest

import geode
from geode._logging import preserve_root_logger


def _clobber_root_like_wxflow():
    root = logging.getLogger()
    root.setLevel(logging.ERROR)
    for handler in list(root.handlers):
        root.removeHandler(handler)
    root.addHandler(logging.StreamHandler(sys.stdout))
    root.propagate = False


def test_preserve_root_logger_restores_state():
    root = logging.getLogger()
    kept_handler = logging.NullHandler()
    root.addHandler(kept_handler)
    level_before = root.level
    handlers_before = list(root.handlers)

    try:
        preserve_root_logger(_clobber_root_like_wxflow)

        assert root.level == level_before
        assert root.handlers == handlers_before
        assert root.propagate is True
    finally:
        root.removeHandler(kept_handler)


def test_preserve_root_logger_restores_on_error():
    root = logging.getLogger()
    level_before = root.level
    handlers_before = list(root.handlers)

    def clobber_then_fail():
        _clobber_root_like_wxflow()
        raise RuntimeError("import failed")

    with pytest.raises(RuntimeError, match="import failed"):
        preserve_root_logger(clobber_then_fail)

    assert root.level == level_before
    assert root.handlers == handlers_before


@pytest.mark.skipif(
    importlib.util.find_spec("bufr") is None, reason="bufr is not installed"
)
def test_geode_warnings_survive_bufr_obs_builder_import():
    # Fresh interpreter: the wxflow side effect only happens on first import
    code = (
        "import logging\n"
        "import geode\n"
        "import bufr.obs_builder\n"
        "root = logging.getLogger()\n"
        "assert root.level == logging.WARNING, root.level\n"
        "assert root.handlers == [], root.handlers\n"
        "logging.getLogger('geode.test').warning('geode warning is visible')\n"
    )
    src_dir = os.path.dirname(os.path.dirname(geode.__file__))
    env = {**os.environ, "PYTHONPATH": src_dir}

    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        check=False,
        text=True,
        env=env,
        timeout=120,
    )

    assert result.returncode == 0, result.stderr
    assert "geode warning is visible" in result.stderr
    assert "geode warning is visible" not in result.stdout


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
