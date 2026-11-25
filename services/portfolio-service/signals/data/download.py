"""One-time download of the candle history the 4.4 module is backtested on.

Everything goes to the local disk only (services/portfolio-service/data/raw, git-ignored): nothing is committed,
nothing goes to a database or a cloud. After the download the 4.4 module works offline on these files.

Sources (all in US dollars):
  BTCUSDT  Binance public data archive, https://data.binance.vision (docs: github.com/binance/binance-public-data)
           spot klines 15m, 30m, 1h, 2h, 4h, 6h, 12h, 1d since 2017-08; every zip is checked against Binance's SHA-256 file.
           Intraday gaps in the data are real exchange outages (e.g. 2018-02-08/09, ~33 h), they are not filled.
           Each candle carries the taker-buy volume, so CVD can be computed without trade-level data.
  GC=F     COMEX gold futures, front month, via Yahoo Finance (library: yfinance, Apache 2.0)
  ES=F     E-mini S&P 500 futures, front month, via Yahoo Finance
           Yahoo limits: 1d/1w full history, 1h the last ~730 days, 15m/30m the last ~60 days.

Kept raw on purpose: 45m (3 x 15m), BTC 1w / 3d / 1M (from 1d), 2h-12h for the futures (from 1h), 3d / 1M (from 1d) and the futures roll
adjustment are built later,
in code, from these files, so the raw data always stays exactly what the source sent.

Run (from services/portfolio-service):
  .\\venv\\Scripts\\python.exe -m signals.data.download            # everything
  .\\venv\\Scripts\\python.exe -m signals.data.download --only binance
Re-running is cheap: verified Binance zips are kept in data/raw/binance/_zips and not downloaded again.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import time
import urllib.error
import urllib.request
import zipfile
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

SERVICE_DIR = Path(__file__).resolve().parents[2]
RAW_DIR = SERVICE_DIR / "data" / "raw"

BINANCE_BASE = "https://data.binance.vision/data/spot"
BINANCE_SYMBOLS = {"BTCUSDT": ["15m", "30m", "1h", "2h", "4h", "6h", "12h", "1d"],
                   "PAXGUSDT": ["15m", "30m", "1h", "2h"]}      # tokenised gold: long lower-frame history (Yahoo gives 60 days)
BINANCE_FIRST_MONTH = date(2017, 8, 1)  # BTCUSDT spot trading started on 2017-08-17
# no "1w": the archive's weekly files miss the weeks that cross a month boundary (8 gaps found on 23 Nov 2026)
# and there are no daily files for it, so the weekly candles are built from the gap-free 1d file instead

# Yahoo interval name -> our name, and how far back Yahoo serves it
YAHOO_SYMBOLS = {"GC=F": "gold futures (COMEX), USD", "ES=F": "E-mini S&P 500 futures (CME), USD"}
# daily closes only, for the yearly volatility of the 4.3 basket (Yahoo closes are adjusted for splits, not for dividends)
YAHOO_DAILY = {"NVDA": "Nvidia share, USD"}
YAHOO_INTERVALS = [
    ("1wk", "1w", None),   # None = full history ("max")
    ("1d", "1d", None),
    ("1h", "1h", 729),     # days back; Yahoo refuses intraday requests beyond its window
    ("30m", "30m", 59),
    ("15m", "15m", 59),
]

USER_AGENT = "ainvest-research-downloader/0.1"
OUTPUT_COLUMNS = ["open_time", "open", "high", "low", "close", "volume",
                  "quote_volume", "trades", "taker_buy_volume", "taker_buy_quote_volume"]


# ---------- pure helpers (unit-tested, no network) ----------

def kline_time_to_utc(raw: str) -> datetime:
    """Binance kline open time -> UTC datetime. Spot files from 2025 on use microseconds instead of
    milliseconds, so the unit is told apart by size: a millisecond timestamp has 13 digits, microseconds 16."""
    value = int(raw)
    seconds = value / 1_000_000 if value >= 10**15 else value / 1_000
    return datetime.fromtimestamp(seconds, tz=timezone.utc)


def parse_binance_kline_csv(text: str) -> list[dict]:
    """Rows of one Binance kline CSV. Some files start with a header line, most do not: a first field that is
    not a number is a header and skipped. Columns (Binance docs): open_time, open, high, low, close, volume,
    close_time, quote_volume, trades, taker_buy_volume, taker_buy_quote_volume, ignore."""
    rows = []
    for fields in csv.reader(io.StringIO(text)):
        if not fields or not fields[0].strip().isdigit():
            continue
        rows.append({
            "open_time": kline_time_to_utc(fields[0]).isoformat(),
            "open": fields[1], "high": fields[2], "low": fields[3], "close": fields[4], "volume": fields[5],
            "quote_volume": fields[7], "trades": fields[8],
            "taker_buy_volume": fields[9], "taker_buy_quote_volume": fields[10],
        })
    return rows


def parse_checksum(text: str) -> str:
    """Binance .CHECKSUM file: '<sha256>  <file name>' -> the hash."""
    return text.strip().split()[0].lower()


def binance_months(first: date, today: date) -> list[date]:
    """First day of every complete month from `first` up to the month before `today` (monthly archives)."""
    months, current = [], date(first.year, first.month, 1)
    this_month = date(today.year, today.month, 1)
    while current < this_month:
        months.append(current)
        current = date(current.year + (current.month == 12), current.month % 12 + 1, 1)
    return months


def binance_days_of_current_month(today: date) -> list[date]:
    """Days of the running month before today (daily archives; today's file does not exist yet)."""
    return [date(today.year, today.month, d) for d in range(1, today.day)]


def dedupe_sorted(rows: list[dict]) -> list[dict]:
    """One row per open_time, oldest first (monthly and daily archives can overlap at the edges)."""
    by_time = {row["open_time"]: row for row in rows}
    return [by_time[t] for t in sorted(by_time)]


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


# ---------- download ----------

@dataclass
class Report:
    files: list[dict] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)


def _http_get(url: str, retries: int = 3) -> bytes | None:
    """GET with a timeout and a few retries; None for 404 (an archive that does not exist)."""
    for attempt in range(1, retries + 1):
        try:
            request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(request, timeout=30) as response:
                return response.read()
        except urllib.error.HTTPError as error:
            if error.code == 404:
                return None
            if attempt == retries:
                raise
        except (urllib.error.URLError, TimeoutError):
            if attempt == retries:
                raise
        time.sleep(2 * attempt)
    return None


def _binance_archive(symbol: str, kind: str, interval: str, stamp: str, zips_dir: Path, report: Report) -> list[dict]:
    """One monthly or daily archive: cached zip if its checksum still matches, otherwise download + verify."""
    name = f"{symbol}-{interval}-{stamp}.zip"
    url = f"{BINANCE_BASE}/{kind}/klines/{symbol}/{interval}/{name}"
    zip_path = zips_dir / interval / name
    checksum_raw = _http_get(url + ".CHECKSUM")
    if checksum_raw is None:
        report.missing.append(url)
        return []
    expected = parse_checksum(checksum_raw.decode())

    if not (zip_path.exists() and sha256_of(zip_path) == expected):
        content = _http_get(url)
        if content is None:
            report.missing.append(url)
            return []
        if hashlib.sha256(content).hexdigest() != expected:
            raise ValueError(f"Checksum mismatch for {url}: the file is not what Binance published")
        zip_path.parent.mkdir(parents=True, exist_ok=True)
        zip_path.write_bytes(content)

    with zipfile.ZipFile(zip_path) as archive:
        return parse_binance_kline_csv(archive.read(archive.namelist()[0]).decode())


def download_binance(today: date, report: Report, symbol: str = "BTCUSDT") -> None:
    out_dir = RAW_DIR / "binance" / symbol
    zips_dir = RAW_DIR / "binance" / "_zips"
    for interval in BINANCE_SYMBOLS[symbol]:
        rows: list[dict] = []
        for month in binance_months(BINANCE_FIRST_MONTH, today):
            rows += _binance_archive(symbol, "monthly", interval, month.strftime("%Y-%m"), zips_dir, report)
        for day in binance_days_of_current_month(today):
            rows += _binance_archive(symbol, "daily", interval, day.isoformat(), zips_dir, report)
        rows = dedupe_sorted(rows)
        path = _write_csv(out_dir / f"{interval}.csv", rows)
        report.files.append(_describe(path, "binance", symbol, interval, rows,
                                      f"{BINANCE_BASE}/(monthly|daily)/klines/{symbol}/{interval}/"))
        print(f"binance {symbol} {interval}: {len(rows)} candles")


def download_yahoo(today: date, report: Report, symbols: dict[str, str], intervals: list[tuple]) -> None:
    import yfinance  # only needed here; the rest of the service does not depend on it

    for symbol, description in symbols.items():
        out_dir = RAW_DIR / "yahoo" / symbol.replace("=", "_")
        for yahoo_interval, interval, days_back in intervals:
            ticker = yfinance.Ticker(symbol)
            if days_back is None:
                frame = ticker.history(period="max", interval=yahoo_interval, auto_adjust=False, actions=False)
            else:
                start = today - timedelta(days=days_back)
                frame = ticker.history(start=start.isoformat(), end=(today + timedelta(days=1)).isoformat(),
                                       interval=yahoo_interval, auto_adjust=False, actions=False)
            rows = []
            for stamp, values in frame.iterrows():
                moment = stamp.to_pydatetime()
                moment = moment.replace(tzinfo=timezone.utc) if moment.tzinfo is None else moment.astimezone(timezone.utc)
                rows.append({"open_time": moment.isoformat(), "open": values["Open"], "high": values["High"],
                             "low": values["Low"], "close": values["Close"], "volume": values["Volume"]})
            rows = dedupe_sorted(rows)
            path = _write_csv(out_dir / f"{interval}.csv", rows)
            report.files.append(_describe(path, "yahoo", symbol, interval, rows,
                                          f"yfinance {yfinance.__version__}: Ticker('{symbol}').history(interval='{yahoo_interval}')",
                                          note=description))
            print(f"yahoo {symbol} {interval}: {len(rows)} candles")


def _write_csv(path: Path, rows: list[dict]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=OUTPUT_COLUMNS, extrasaction="ignore", restval="")
        writer.writeheader()
        writer.writerows(rows)
    return path


def _describe(path: Path, source: str, symbol: str, interval: str, rows: list[dict], origin: str, note: str = "") -> dict:
    return {
        "file": path.relative_to(RAW_DIR).as_posix(), "source": source, "symbol": symbol, "interval": interval,
        "origin": origin, "note": note, "rows": len(rows),
        "first": rows[0]["open_time"] if rows else None, "last": rows[-1]["open_time"] if rows else None,
        "sha256": sha256_of(path),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Download the 4.4 candle history into data/raw (local only).")
    parser.add_argument("--only", choices=["binance", "yahoo", "daily", "paxg"], help="download one source only")
    args = parser.parse_args()

    today = datetime.now(timezone.utc).date()
    report = Report()
    if args.only in (None, "binance"):
        download_binance(today, report)
    if args.only in (None, "paxg"):
        download_binance(today, report, "PAXGUSDT")
    if args.only in (None, "yahoo"):
        download_yahoo(today, report, YAHOO_SYMBOLS, YAHOO_INTERVALS)
    if args.only in (None, "daily"):
        download_yahoo(today, report, YAHOO_DAILY, [("1d", "1d", None)])

    # what was downloaded, when, from where, and the hash of every file: the same files give the same backtest
    manifest_path = RAW_DIR / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {"files": []}
    replaced = {f["file"] for f in report.files}
    manifest["files"] = [f for f in manifest["files"] if f["file"] not in replaced] + report.files
    manifest["downloaded_at"] = datetime.now(timezone.utc).isoformat()
    if args.only not in ("yahoo", "daily"):          # Yahoo has no archives: the list of the last Binance run stays
        manifest["missing_archives"] = report.missing
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"manifest: {manifest_path} ({len(report.files)} files, {len(report.missing)} archives missing)")


if __name__ == "__main__":
    main()
