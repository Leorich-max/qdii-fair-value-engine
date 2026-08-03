"""Fair-value reconstruction for US-underlying ETFs during A-share hours.

Exchange IOPV is stale while the US underlying is closed. This subpackage
reconstructs a real-time fair value from the last published NAV, the
NASDAQ-100 futures move, and USDCNH against the CFETS central parity.
"""
