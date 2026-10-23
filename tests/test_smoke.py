"""Smoke test: the package imports and exposes a version.

Fair-value behaviour itself is covered in ``test_fair_value.py``.
"""

import qdii_fve


def test_package_imports() -> None:
    assert isinstance(qdii_fve.__version__, str)
    assert qdii_fve.__version__
