"""qdii_fve — fair-value engine for China-listed NASDAQ-100 QDII ETFs.

Reconstructs a current fair value from the last published NAV, the QQQ move since
the NAV valuation date and the USDCNH move against that date's CFETS central parity,
and measures each ETF's premium to it. Synthetic sample data only; no vendor data.
"""

__version__ = "0.1.0"
