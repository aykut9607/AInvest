"""Volume and CVD for the two assets whose price series has none, only used to FIND divergences (never in the score, which was measured without them).

  XAU  Binance PAXGUSDT (tokenised gold): volume and taker-buy volume, 15m since August 2020
  SPX  Yahoo ES=F (E-mini futures): volume of the hourly bars of the last two years, so only frames of 1h and above; no taker side, so no CVD
"""

from __future__ import annotations

import csv
from datetime import datetime

import numpy as np

from signals.data.download import RAW_DIR

SOURCES = {"XAU": ("binance/PAXGUSDT/15m.csv", 900.0, True), "SPX": ("yahoo/ES_F/1h.csv", 3600.0, False)}


class AuxVolume:
    def __init__(self, asset: str):
        path, self.span, taker = SOURCES[asset]
        t, v, d = [], [], []
        with (RAW_DIR / path).open(encoding="utf-8") as handle:
            for row in csv.DictReader(handle):
                t.append(datetime.fromisoformat(row["open_time"]).timestamp())
                v.append(float(row["volume"] or 0))
                d.append(2 * float(row["taker_buy_volume"]) - v[-1] if taker else 0.0)
        self.t = np.array(t)
        self.v, self.d, self.taker = np.concatenate(([0.0], np.cumsum(v))), np.concatenate(([0.0], np.cumsum(d))), taker

    def of(self, opened: np.ndarray, span: float) -> tuple[np.ndarray | None, np.ndarray | None]:
        """(volume, CVD) of bars opening at these times; NaN where the source has nothing. None when its bars are longer than the frame's."""
        if span < self.span:
            return None, None
        a, z = np.searchsorted(self.t, opened), np.searchsorted(self.t, opened + span)
        volume = self.v[z] - self.v[a]
        missing = (z == a) | (volume <= 0)
        volume = np.where(missing, np.nan, volume)
        return volume, np.where(missing, np.nan, self.d[z]) if self.taker else None
