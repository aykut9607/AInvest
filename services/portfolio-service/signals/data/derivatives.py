"""BTC open interest and funding from the Binance public data archive (USD-M futures, BTCUSDT perpetual).

  data/futures/um/daily/metrics/BTCUSDT      5-minute open interest since 2020-09-01   -> data/raw/binance/BTCUSDT_oi_1h.csv
  data/futures/um/monthly/fundingRate/BTCUSDT  8-hour funding since 2020-01            -> data/raw/binance/BTCUSDT_funding.csv

Every zip is checked against Binance's SHA-256 file and kept in data/raw/binance/_zips (git-ignored). The open interest is
reduced to one value per hour: the last 5-minute value known at that full hour (no look-ahead).

  .\\venv\\Scripts\\python.exe -m signals.data.derivatives
"""

from __future__ import annotations

import csv
import hashlib
import io
import sys
import zipfile
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone

from signals.data.download import RAW_DIR, _http_get, binance_months, parse_checksum, sha256_of

BASE = "https://data.binance.vision/data/futures/um"
SYMBOL = "BTCUSDT"
OI_FIRST, FUNDING_FIRST = date(2020, 9, 1), date(2020, 1, 1)


def parse_metrics(text: str) -> list[tuple[datetime, float]]:
    """(time, open interest in BTC) rows of one metrics CSV."""
    rows = []
    for row in csv.DictReader(io.StringIO(text)):
        value = row.get("sum_open_interest") or ""
        if value and float(value) > 0:                  # the archive has a few zero rows (no data), never a real value
            rows.append((datetime.fromisoformat(row["create_time"]).replace(tzinfo=timezone.utc), float(value)))
    return rows


def hourly(rows: list[tuple[datetime, float]]) -> list[tuple[datetime, float]]:
    """The newest value at or before each full hour, only if it is at most one hour old; oldest first."""
    rows = sorted(rows)
    out: list[tuple[datetime, float]] = []
    if not rows:
        return out
    hour = rows[0][0].replace(minute=0, second=0, microsecond=0)
    k = 0
    last: tuple[datetime, float] | None = None
    while hour <= rows[-1][0]:
        while k < len(rows) and rows[k][0] <= hour:
            last = rows[k]
            k += 1
        if last is not None and hour - last[0] <= timedelta(hours=1):
            out.append((hour, last[1]))
        hour += timedelta(hours=1)
    return out


def parse_funding(text: str) -> list[tuple[datetime, float]]:
    """(time, funding rate) rows of one fundingRate CSV (calc_time in milliseconds)."""
    out = []
    for row in csv.DictReader(io.StringIO(text)):
        out.append((datetime.fromtimestamp(int(row["calc_time"]) / 1000, tz=timezone.utc), float(row["last_funding_rate"])))
    return out


def _archive(path: str) -> str | None:
    """The CSV text of one verified zip; None when Binance has no such file."""
    local = RAW_DIR / "binance" / "_zips" / "um" / path.rsplit("/", 1)[-1]
    checksum = _http_get(f"{BASE}/{path}.CHECKSUM")
    if checksum is None:
        return None
    expected = parse_checksum(checksum.decode())
    if not (local.exists() and sha256_of(local) == expected):
        content = _http_get(f"{BASE}/{path}")
        if content is None:
            return None
        if hashlib.sha256(content).hexdigest() != expected:
            raise ValueError(f"Checksum mismatch: {path}")
        local.parent.mkdir(parents=True, exist_ok=True)
        local.write_bytes(content)
    with zipfile.ZipFile(local) as archive:
        return archive.read(archive.namelist()[0]).decode()


def download(today: date | None = None) -> dict[str, int]:
    today = today or datetime.now(timezone.utc).date()
    days = [OI_FIRST + timedelta(days=i) for i in range((today - OI_FIRST).days)]
    metrics = [f"daily/metrics/{SYMBOL}/{SYMBOL}-metrics-{d:%Y-%m-%d}.zip" for d in days]
    funding = [f"monthly/fundingRate/{SYMBOL}/{SYMBOL}-fundingRate-{m:%Y-%m}.zip" for m in binance_months(FUNDING_FIRST, today)]
    with ThreadPoolExecutor(max_workers=6) as pool:
        oi_texts = list(pool.map(_archive, metrics))
        funding_texts = list(pool.map(_archive, funding))
    oi = hourly([r for text in oi_texts if text for r in parse_metrics(text)])
    rates = sorted({t: v for text in funding_texts if text for t, v in parse_funding(text)}.items())
    for name, header, rows in (("oi_1h", "open_interest_btc", oi), ("funding", "funding_rate", rates)):
        with (RAW_DIR / "binance" / f"{SYMBOL}_{name}.csv").open("w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(["time", header])
            writer.writerows([t.isoformat(), v] for t, v in rows)
    return {"oi files": sum(t is not None for t in oi_texts), "oi missing": sum(t is None for t in oi_texts), "oi hours": len(oi),
            "funding files": sum(t is not None for t in funding_texts), "funding missing": sum(t is None for t in funding_texts),
            "funding rows": len(rates)}


def load(name: str) -> list[tuple[datetime, float]]:
    """"oi_1h" or "funding", oldest first."""
    with (RAW_DIR / "binance" / f"{SYMBOL}_{name}.csv").open(encoding="utf-8") as handle:
        reader = csv.reader(handle)
        next(reader)
        return [(datetime.fromisoformat(t), float(v)) for t, v in reader]


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    print(download())
