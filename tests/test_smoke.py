"""Smoke test: the package imports and exposes a version.

Keeps CI green from the first commit; real coverage for the fair-value engine
and the cost model is added alongside those modules.
"""

import qdii_fve


def test_package_imports() -> None:
    assert isinstance(qdii_fve.__version__, str)
    assert qdii_fve.__version__
