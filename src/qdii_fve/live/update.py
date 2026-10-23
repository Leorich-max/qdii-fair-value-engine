"""Daily update: fetch -> check -> compute -> write ``app/data.js`` and the NAV/parity histories.

``python -m qdii_fve.live.update``             normal day (recent rows only)
``python -m qdii_fve.live.update --backfill``  one-off history fill (slow, small spaced requests)

Fail-safe: everything is fetched and checked in memory first. If any source or check fails, the
process exits with status 1 and writes NOTHING, so the published page keeps its last good version.
"""

from __future__ import annotations

import csv
import json
import os
import sys
import time
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

from qdii_fve.live import model, sources

START = "2025-03-03"  # all 12 funds listed by then
NAV_FIELDS = ["code", "nav_date", "nav", "first_seen_utc", "revised_utc"]
PARITY_FIELDS = ["date", "usdcny", "source", "first_seen_utc"]


class UpdateError(RuntimeError):
    pass


def _root():
    return Path(__file__).resolve().parents[3]


def _read_csv(path):
    if not path.exists():
        return []
    with open(path, encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def _write_atomic(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8", newline="\n")  # identical bytes on every OS
    os.replace(tmp, path)


def _csv_text(rows, fields):
    from io import StringIO

    buf = StringIO()
    w = csv.DictWriter(buf, fieldnames=fields, lineterminator="\n")
    w.writeheader()
    w.writerows(rows)
    return buf.getvalue()


def merge_navs(existing, fetched, seen, now=None):
    """Merge fetched {code: [(date, nav)]} into history rows.

    New rows get first_seen=``seen`` (the run time, or 'backfill' for history filled in one go); a
    changed value keeps its first_seen and gets revised_utc=now. Returns (rows, n_new, revisions).
    """
    now = now or seen
    by = {(r["code"], r["nav_date"]): dict(r) for r in existing}
    n_new, revisions = 0, []
    for code, pairs in fetched.items():
        for d, nav in pairs:
            key = (code, d)
            val = f"{nav:.4f}"
            if key not in by:
                by[key] = dict(code=code, nav_date=d, nav=val, first_seen_utc=seen, revised_utc="")
                n_new += 1
            elif by[key]["nav"] != val:
                revisions.append((code, d, by[key]["nav"], val))
                by[key].update(nav=val, revised_utc=now)
    rows = sorted(by.values(), key=lambda r: (r["code"], r["nav_date"]))
    return rows, n_new, revisions


def merge_parity(existing, fetched, source, now):
    by = {r["date"]: dict(r) for r in existing}
    for d, v in fetched.items():
        if d not in by:
            by[d] = dict(date=d, usdcny=f"{v:.4f}", source=source, first_seen_utc=now)
    return sorted(by.values(), key=lambda r: r["date"])


def fetch_all(backfill=False, today=None, pause=0.6):
    """Everything from the network, in memory. Raises sources.SourceError on any failure."""
    today = today or date.today()
    prices, navs = {}, {}
    for code in sources.FUNDS:
        prices[code] = sources.fetch_etf_closes(code)
        pages, page = [], 1
        while True:
            rows = sources.fetch_nav_page(code, page)
            pages.extend(rows)
            if not backfill or not rows or rows[-1][0] < START:
                break
            page += 1
            time.sleep(pause)
        navs[code] = pages
        time.sleep(pause)
    if backfill:
        parity, src = {}, set()
        d0 = date.fromisoformat(START) - timedelta(days=14)
        while d0 <= today:
            d1 = min(d0 + timedelta(days=40), today)
            part, s = sources.fetch_parity(d0.isoformat(), d1.isoformat())
            parity.update(part)
            src.add(s)
            d0 = d1 + timedelta(days=1)
            time.sleep(3 * pause)
        parity_src = "+".join(sorted(src))
    else:
        parity, parity_src = sources.fetch_parity(
            (today - timedelta(days=20)).isoformat(), today.isoformat()
        )
    (qqq_px, qqq_div), qqq_src = sources.fetch_qqq(START)
    return dict(prices=prices, navs=navs, parity=parity, parity_src=parity_src,
                qqq_px=qqq_px, qqq_div=qqq_div, qqq_src=qqq_src)  # fmt: skip


def check(prices, nav_hist, parity, qqq_px):
    """List of problems that make today's data unfit to publish (empty = OK)."""
    problems = []
    last = max(max(p) for p in prices.values())
    for code, p in prices.items():
        if last not in p:
            problems.append(f"{code}: no close for the latest A-share day {last}")
    newest = {}
    for r in nav_hist:
        newest[r["code"]] = max(newest.get(r["code"], ""), r["nav_date"])
    for code in prices:
        nd = newest.get(code)
        if not nd or (date.fromisoformat(last) - date.fromisoformat(nd)).days > 10:
            problems.append(f"{code}: newest NAV {nd} is more than 10 days before {last}")
    if last not in parity:
        problems.append(f"no CFETS parity for {last}")
    us_last = max(qqq_px)
    if (date.fromisoformat(last) - date.fromisoformat(us_last)).days > 6:
        problems.append(f"newest QQQ close {us_last} is stale against {last}")
    return problems


def build_payload(prices, nav_hist, parity, qqq_px, qqq_div, meta):
    navs = {}
    for r in nav_hist:
        navs.setdefault(r["code"], {})[r["nav_date"]] = float(r["nav"])
    first_seen = {(r["code"], r["nav_date"]): r["first_seen_utc"] for r in nav_hist}
    qtr = model.total_return_index(qqq_px, qqq_div)
    dates = sorted({d for p in prices.values() for d in p if d >= START})
    funds = {}
    for code in sorted(prices):
        rows = {
            r["date"]: r
            for r in model.fund_rows(prices[code], navs.get(code, {}), qtr, parity, START)
        }
        stats = model.residual_stats(model.nav_validation(navs.get(code, {}), qtr, parity, START))
        rd = lambda v, k: None if v is None else round(v, k)  # noqa: E731
        funds[code] = dict(
            price=[rd(rows[d]["price"], 4) if d in rows else None for d in dates],
            fair=[rd(rows[d]["fair"], 4) if d in rows else None for d in dates],
            premium_bp=[rd(rows[d]["premium_bp"], 1) if d in rows else None for d in dates],
            nav=[rows[d]["nav"] if d in rows else None for d in dates],
            nav_date=[rows[d]["nav_date"] if d in rows else None for d in dates],
            residual_std_bp=rd(stats["std_bp"], 2),
            residual_mae_bp=rd(stats["mae_bp"], 2),
            residual_n=stats["n"],
        )
    last = dates[-1]
    ref = funds["513100"]
    i = dates.index(last)
    d = ref["nav_date"][i]
    ql, pl = model.Lookup(qqq_px), model.Lookup(parity)
    calc = dict(
        nav=ref["nav"][i],
        underlying_ref=qqq_px[ql.on_or_before(d)],
        underlying_now=qqq_px[ql.before(last)],
        parity_ref=parity[pl.on_or_before(d)],
        fx_now=parity[last],
        price=ref["price"][i],
        fund="513100",
        nav_date=d,
    )
    return dict(synthetic=False, dates=dates, funds=funds, calc_defaults=calc,
                first_seen_latest={c: first_seen.get((c, funds[c]["nav_date"][i])) for c in funds},
                meta=meta)  # fmt: skip


def run(backfill=False, root=None, now=None, fetch=fetch_all):
    root = Path(root) if root else _root()
    now = now or datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    nav_path, par_path = (
        root / "data" / "live" / "nav_history.csv",
        root / "data" / "live" / "parity_history.csv",
    )
    try:
        f = fetch(backfill=backfill)
    except sources.SourceError as e:
        raise UpdateError(f"source failed: {e}") from e
    # backfilled history is NOT publication evidence: only rows a daily run sees appear get a time
    seen = "backfill" if backfill else now
    nav_rows, n_new, revisions = merge_navs(_read_csv(nav_path), f["navs"], seen, now)
    par_rows = merge_parity(_read_csv(par_path), f["parity"], f["parity_src"], seen)
    parity = {r["date"]: float(r["usdcny"]) for r in par_rows}
    problems = check(f["prices"], nav_rows, parity, f["qqq_px"])
    if problems:
        raise UpdateError("checks failed: " + "; ".join(problems))
    last = max(max(p) for p in f["prices"].values())
    meta = dict(
        generated_utc=now,
        data_through=dict(etf_close=last, qqq_close=max(f["qqq_px"]), parity=max(parity),
                          newest_nav=max(r["nav_date"] for r in nav_rows)),
        sources=dict(etf="Tencent", nav="EastMoney", parity=f["parity_src"], qqq=f["qqq_src"]),
        new_navs=n_new,
        nav_revisions=[list(r) for r in revisions],
    )  # fmt: skip
    payload = build_payload(f["prices"], nav_rows, parity, f["qqq_px"], f["qqq_div"], meta)
    text = "window.FV_DATA = " + json.dumps(payload, separators=(",", ":"), allow_nan=False) + ";\n"
    _write_atomic(nav_path, _csv_text(nav_rows, NAV_FIELDS))
    _write_atomic(par_path, _csv_text(par_rows, PARITY_FIELDS))
    _write_atomic(root / "app" / "data.js", text)
    return meta


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    try:
        meta = run(backfill="--backfill" in argv)
    except UpdateError as e:
        print(f"UPDATE FAILED — nothing written, the page keeps its last good version: {e}")
        return 1
    print(json.dumps(meta, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
