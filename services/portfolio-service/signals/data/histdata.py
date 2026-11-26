r"""HistData.com 1-minute files (downloaded by hand, ASCII M1 zips) -> 15-minute UTC candles.

  .\venv\Scripts\python.exe -m signals.data.histdata "C:\Users\<you>\Downloads"     copy the zips and rebuild the 15m files

XAUUSD (spot gold, 2009-) and SPXUSD (S&P 500 CFD, 2010-) give the lower frames Yahoo lacks for GC=F and ES=F (15m: 60 days). There is no
volume in them, so volume, profile, VWAP and CVD rules are not measured on these series. The file clock is New York local time WITH
daylight saving in every year 2009-2026: the 08:30 New York data releases sit at 08:30 of the file in summer and winter, and the hourly
returns match GC=F / ES=F (correlation 0.98-0.99) only that way (checked 25 Nov 2026; the site's own note says otherwise).
"""

from __future__ import annotations

import csv
import re
import shutil
import sys
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from signals.data.download import RAW_DIR

FOLDER = RAW_DIR / "histdata"
SYMBOLS = {"XAU": "XAUUSD", "SPX": "SPXUSD"}
NAME = re.compile(r"HISTDATA_COM_ASCII_(\w+)_M1(\d{4})(\d{2})?\.zip$")
NEW_YORK = ZoneInfo("America/New_York")
QUARTER = 15 * 60
MIN_MINUTES = 8                             # a 15m candle needs at least this many traded minutes


def collect(source: Path) -> list[str]:
    """Copy the zips (browser duplicates like "(1)" have another name and are skipped)."""
    FOLDER.mkdir(parents=True, exist_ok=True)
    taken = []
    for path in sorted(source.glob("HISTDATA_COM_ASCII_*.zip")):
        if NAME.search(path.name) and zipfile.is_zipfile(path):
            target = FOLDER / path.name
            if not target.exists() or target.stat().st_size != path.stat().st_size:
                shutil.copy2(path, target)
            taken.append(path.name)
    return taken


def months_present(symbol: str) -> set[tuple[int, int]]:
    out = set()
    for path in FOLDER.glob(f"*_{symbol}_M1*.zip"):
        m = NAME.search(path.name)
        out |= {(int(m[2]), int(m[3]))} if m[3] else {(int(m[2]), k) for k in range(1, 13)}
    return out


def minutes(symbol: str):
    """(UTC time, open, high, low, close), oldest first, every minute once."""
    rows = {}
    for path in sorted(FOLDER.glob(f"*_{symbol}_M1*.zip")):
        with zipfile.ZipFile(path) as archive:
            name = next(n for n in archive.namelist() if n.lower().endswith(".csv"))
            for line in archive.read(name).decode("ascii").splitlines():
                stamp, o, h, l, c, *_ = line.split(";")
                rows[stamp] = (float(o), float(h), float(l), float(c))
    for stamp in sorted(rows):
        yield datetime.strptime(stamp, "%Y%m%d %H%M%S").replace(tzinfo=NEW_YORK).astimezone(timezone.utc), *rows[stamp]


def build(key: str) -> Path:
    """Write data/raw/histdata/<symbol>_15m.csv."""
    out, bucket, part = [], None, []

    def flush():
        if len(part) >= MIN_MINUTES:
            out.append((bucket.isoformat(), part[0][0], max(p[1] for p in part), min(p[2] for p in part), part[-1][3], 0, len(part)))

    for t, o, h, l, c in minutes(SYMBOLS[key]):
        start = t - timedelta(seconds=(t.minute * 60 + t.second) % QUARTER)
        if start != bucket:
            flush()
            bucket, part = start, []
        part.append((o, h, l, c))
    flush()
    path = FOLDER / f"{SYMBOLS[key]}_15m.csv"
    with path.open("w", newline="", encoding="utf-8") as handle:
        w = csv.writer(handle)
        w.writerow(["open_time", "open", "high", "low", "close", "volume", "minutes"])
        w.writerows(out)
    return path


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    if len(sys.argv) > 1:
        print(len(collect(Path(sys.argv[1]))), "zips")
    for key in SYMBOLS:
        have = months_present(SYMBOLS[key])
        first, last = min(have), max(have)
        wanted = {(y, m) for y in range(first[0], last[0] + 1) for m in range(1, 13) if (y, m) <= last and (y, m) >= first}
        print(key, build(key).name, f"{first} - {last}", "missing months:", sorted(wanted - have))


if __name__ == "__main__":
    main()
