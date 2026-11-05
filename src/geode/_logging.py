"""Guard the root logger against third-party import-time reconfiguration.

``wxflow`` (pulled in by ``bufr.obs_builder``) builds an unnamed
``wxflow.Logger(level="error")`` when ``wxflow.exceptions`` is imported. That
sets the *root* logger to ERROR, drops its handlers and adds a stdout handler,
which hides every WARNING from geode and sends log output to stdout.
"""

import importlib
import logging
from collections.abc import Callable


def preserve_root_logger(func: Callable[[], object]) -> None:
    """Run ``func`` and restore the root logger's level and handlers afterwards."""
    root = logging.getLogger()
    saved_level = root.level
    saved_handlers = list(root.handlers)
    saved_propagate = root.propagate
    try:
        func()
    finally:
        for handler in list(root.handlers):
            if handler not in saved_handlers:
                root.removeHandler(handler)
        for handler in saved_handlers:
            if handler not in root.handlers:
                root.addHandler(handler)
        root.setLevel(saved_level)
        root.propagate = saved_propagate


def import_wxflow_quietly() -> None:
    """Import wxflow once, undoing its root-logger changes.

    Python caches modules, so the import-time side effect cannot recur later
    when ``bufr.obs_builder`` or other code imports wxflow.
    """

    def _import() -> None:
        try:
            importlib.import_module("wxflow")
        except ImportError:
            pass

    preserve_root_logger(_import)
