import gc
import sys
import warnings

import pytest


# Belt-and-suspenders: also set at module level for any GC that runs
# during collection or between pytest's per-test catch_warnings contexts.
warnings.filterwarnings("ignore", category=ResourceWarning)


def _suppress_resource_warning_hook(unraisable):
    if unraisable.exc_type is ResourceWarning:
        return
    sys.__unraisablehook__(unraisable)


sys.unraisablehook = _suppress_resource_warning_hook


@pytest.fixture(autouse=True)
def _drain_sqlite_connections():
    """Force GC after each test while ResourceWarning is suppressed.

    Each test creates a Flask app with a SQLite in-memory SQLAlchemy engine.
    Those engines hold open sqlite3.Connection objects that are never
    explicitly disposed. If GC runs later (e.g. during coverage/HTML report
    generation) it emits ResourceWarning. Running gc.collect() here, inside
    a catch_warnings block, drains the connections while our filter is active.
    """
    yield
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", ResourceWarning)
        gc.collect()
