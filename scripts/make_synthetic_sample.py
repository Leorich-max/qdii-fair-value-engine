"""Write the synthetic sample dataset to ``data/sample/``.

Usage::

    python scripts/make_synthetic_sample.py

Deterministic: re-running with the same seed reproduces byte-identical CSVs.
The output is SYNTHETIC and clearly named as such; see ``data/sample/README.md``.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from qdii_fve.synthetic import generate_sample

FILES = {
    "daily_bars": "SYNTHETIC_daily_bars.csv",
    "nav": "SYNTHETIC_nav.csv",
    "underlying": "SYNTHETIC_ndx_underlying.csv",
    "usdcnh": "SYNTHETIC_usdcnh.csv",
}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=20260101)
    parser.add_argument("--n-days", type=int, default=260)
    parser.add_argument(
        "--out",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "data" / "sample",
    )
    args = parser.parse_args()

    args.out.mkdir(parents=True, exist_ok=True)
    frames = generate_sample(seed=args.seed, n_days=args.n_days)
    for key, name in FILES.items():
        path = args.out / name
        frames[key].to_csv(path, index=False)
        print(f"wrote {path}  ({len(frames[key])} rows)")


if __name__ == "__main__":
    main()
