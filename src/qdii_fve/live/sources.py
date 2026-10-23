"""Public data sources: network fetchers plus pure parsers (the parsers are tested offline).

| Input | Primary | Fallback |
|---|---|---|
| ETF daily closes | Tencent ``fqkline`` (raw, unadjusted) | — |
| Fund NAV + valuation date | EastMoney ``lsjz`` (20 rows per page) | — |
| USD/CNY central parity | SAFE ``RMBQuery`` | chinamoney ``CcprHisNew`` |
| QQQ closes + dividends | Yahoo chart API | Nasdaq API |

All sources throttle bursts, so requests are small and spaced; the full NAV and parity histories are
kept in the repository and only recent rows are fetched on a normal day.
"""

from __future__ import annotations

import json
import re
import time
import urllib.parse
import urllib.request
from datetime import UTC, datetime

UA = {"User-Agent": "Mozilla/5.0"}

# The 12 China-listed NASDAQ-100 QDII ETFs (exchange prefix + code).
FUNDS = {
    "513100": "sh", "513300": "sh", "513390": "sh", "513110": "sh", "513870": "sh",
    "159941": "sz", "159632": "sz", "159501": "sz", "159513": "sz", "159660": "sz",
    "159659": "sz", "159696": "sz",
}  # fmt: skip


class SourceError(RuntimeError):
    """A source failed or returned something unusable."""


def http_get(url, headers=None, data=None, retries=3, pause=2.0, timeout=25):
    last = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={**UA, **(headers or {})}, data=data)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                raw = r.read()
                charset = r.headers.get_content_charset()
            return decode(raw, charset)
        except Exception as e:  # noqa: BLE001 - every network failure is retried the same way
            last = e
            time.sleep(pause * (attempt + 1))
    raise SourceError(f"{url.split('?')[0]}: {last}")


def decode(raw, charset=None):
    """Decode with the declared charset (header, else <meta>), falling back to UTF-8.

    Some sources (e.g. SAFE) serve GBK; decoding them as UTF-8 silently garbles the headers.
    """
    if not charset:
        m = re.search(rb"charset=[\"']?([A-Za-z0-9_-]+)", raw[:2048])
        charset = m.group(1).decode("ascii") if m else "utf-8"
    try:
        return raw.decode(charset, "replace")
    except LookupError:
        return raw.decode("utf-8", "replace")


# ---------------------------------------------------------------- ETF prices (Tencent)
def parse_tencent(text, symbol):
    """{date: close} from a Tencent fqkline response for one symbol (e.g. 'sh513100')."""
    try:
        rows = json.loads(text)["data"][symbol]["day"]
    except (KeyError, TypeError, ValueError) as e:
        raise SourceError(f"tencent {symbol}: unexpected payload ({e})") from e
    out = {}
    for r in rows:
        close = float(r[2])
        if close <= 0:
            raise SourceError(f"tencent {symbol}: non-positive close on {r[0]}")
        out[r[0]] = close
    return out


def fetch_etf_closes(code):
    sym = FUNDS[code] + code
    url = f"https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={sym},day,,,2000,"
    return parse_tencent(http_get(url), sym)


# ---------------------------------------------------------------- NAV (EastMoney)
def parse_lsjz(text):
    """[(valuation_date, nav)] from one EastMoney lsjz page, newest first."""
    try:
        rows = json.loads(text)["Data"]["LSJZList"]
    except (KeyError, TypeError, ValueError) as e:
        raise SourceError(f"lsjz: unexpected payload ({e})") from e
    out = []
    for r in rows:
        if r.get("DWJZ") in (None, ""):
            continue
        nav = float(r["DWJZ"])
        if nav <= 0:
            raise SourceError(f"lsjz: non-positive NAV on {r.get('FSRQ')}")
        out.append((r["FSRQ"], nav))
    return out


def fetch_nav_page(code, page=1):
    url = f"https://api.fund.eastmoney.com/f10/lsjz?fundCode={code}&pageIndex={page}&pageSize=20"
    return parse_lsjz(http_get(url, {"Referer": "https://fundf10.eastmoney.com/"}))


# ---------------------------------------------------------------- CFETS parity (SAFE, chinamoney)
def parse_safe(html):
    """{date: USD/CNY parity} from the SAFE query table (quoted as CNY per 100 USD).

    The USD column is located from the table's own header row, never assumed.
    """
    html = re.sub(r"<!--.*?-->", "", html, flags=re.S)  # header cells carry template comments
    col = None
    out = {}
    for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", html, re.S):
        heads = re.findall(r"<t[hd][^>]*>\s*([^<]*?)\s*</t[hd]>", tr)
        if col is None and "美元" in heads:
            col = heads.index("美元")
            continue
        cells = re.findall(r"<td[^>]*>\s*([^<]*?)\s*</td>", tr)
        if col is not None and cells and re.match(r"\d{4}-\d\d-\d\d$", cells[0]):
            out[cells[0]] = round(float(cells[col]) / 100, 6)
    if col is None:
        raise SourceError("safe: USD column not found")
    if not out:
        raise SourceError("safe: no rows")
    return out


def fetch_parity_safe(start, end):
    body = urllib.parse.urlencode({"startDate": start, "endDate": end, "queryYN": "true"}).encode()
    html = http_get(
        "https://www.safe.gov.cn/AppStructured/hlw/RMBQuery.do",
        {"Referer": "https://www.safe.gov.cn/safe/rmbhlzjj/"},
        data=body,
    )
    return parse_safe(html)


def parse_chinamoney(text):
    try:
        recs = json.loads(text)["records"]
        return {r["date"]: float(r["values"][0]) for r in recs}
    except (KeyError, TypeError, ValueError, IndexError) as e:
        raise SourceError(f"chinamoney: unexpected payload ({e})") from e


def fetch_parity_chinamoney(start, end):
    url = (
        "https://www.chinamoney.com.cn/ags/ms/cm-u-bk-ccpr/CcprHisNew"
        f"?startDate={start}&endDate={end}&currency=USD/CNY&pageNum=1&pageSize=50"
    )
    return parse_chinamoney(http_get(url, {"Referer": "https://www.chinamoney.com.cn/"}))


def fetch_parity(start, end):
    """(rates, source) — SAFE first, chinamoney if SAFE fails. Keep spans short (<= ~60 days)."""
    try:
        return fetch_parity_safe(start, end), "SAFE"
    except SourceError as first:
        try:
            return fetch_parity_chinamoney(start, end), "chinamoney"
        except SourceError as second:
            raise SourceError(f"parity: {first}; {second}") from second


# ---------------------------------------------------------------- QQQ (Yahoo, Nasdaq)
def parse_yahoo(text):
    """({US date: close}, {ex-date: dividend}) from a Yahoo chart response (unadjusted closes).

    Daily bars are stamped at the US open, so the UTC date of the timestamp is the US trading date.
    """
    try:
        res = json.loads(text)["chart"]["result"][0]
        ts, closes = res["timestamp"], res["indicators"]["quote"][0]["close"]
    except (KeyError, TypeError, ValueError, IndexError) as e:
        raise SourceError(f"yahoo: unexpected payload ({e})") from e
    day = lambda t: datetime.fromtimestamp(t, UTC).strftime("%Y-%m-%d")  # noqa: E731
    px = {day(t): float(c) for t, c in zip(ts, closes, strict=True) if c is not None}
    divs = {
        day(int(k)): float(v["amount"])
        for k, v in (res.get("events") or {}).get("dividends", {}).items()
    }
    return px, divs


def fetch_qqq_yahoo():
    url = "https://query1.finance.yahoo.com/v8/finance/chart/QQQ?range=5y&interval=1d&events=div"
    return parse_yahoo(http_get(url))


def _us_date(s):
    m, d, y = s.split("/")
    return f"{y}-{m}-{d}"


def parse_nasdaq(hist_text, div_text):
    try:
        rows = json.loads(hist_text)["data"]["tradesTable"]["rows"]
        px = {
            _us_date(r["date"]): float(r["close"].replace("$", "").replace(",", "")) for r in rows
        }
        drows = json.loads(div_text)["data"]["dividends"]["rows"]
        divs = {_us_date(r["exOrEffDate"]): float(r["amount"].replace("$", "")) for r in drows}
    except (KeyError, TypeError, ValueError, AttributeError) as e:
        raise SourceError(f"nasdaq: unexpected payload ({e})") from e
    return px, divs


def fetch_qqq_nasdaq(start):
    h = {"Accept": "application/json"}
    hist = http_get(
        f"https://api.nasdaq.com/api/quote/QQQ/historical?assetclass=etf&fromdate={start}&limit=9999",
        h,
    )
    div = http_get("https://api.nasdaq.com/api/quote/QQQ/dividends?assetclass=etf", h)
    return parse_nasdaq(hist, div)


def fetch_qqq(start):
    """((closes, dividends), source) — Yahoo first, Nasdaq if Yahoo fails."""
    try:
        return fetch_qqq_yahoo(), "Yahoo"
    except SourceError as first:
        try:
            return fetch_qqq_nasdaq(start), "Nasdaq"
        except SourceError as second:
            raise SourceError(f"qqq: {first}; {second}") from second
