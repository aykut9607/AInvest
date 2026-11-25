"""The confirmation score (0-100): every category counts once, with its own weight, the weight of the timeframe it was found on and how well
that very rule did in the backtest. Weights and limits are in table.json (made by fit.py from the backtests, one table per asset)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from signals.data.candles import TIMEFRAMES

TABLE = Path(__file__).with_name("table.json")
# the higher the timeframe, the more a confirmation counts (Aykut); equal steps from 0.45 to 1
FRAME_WEIGHT = {f: round(0.45 + 0.05 * i, 2) for i, f in enumerate(TIMEFRAMES)}


@dataclass(frozen=True)
class Score:
    total: float
    categories: dict[str, dict]          # category -> {points, frame, rule}; only what earned points


@lru_cache
def tables() -> dict:
    return json.loads(TABLE.read_text(encoding="utf-8"))


def quality_of(tag: str, table: dict) -> float:
    """0-1: the backtest value of exactly this rule (with its variant) compared with the best rule of its category. A rule that proved nothing
    gives 0: what its category or its sibling variants proved is not lent to it (Aykut)."""
    return table["quality"].get(tag.removesuffix("|"), 0.0)


def score(tags: dict[str, list[str]], table: dict) -> Score:
    best: dict[str, dict] = {}
    for frame, names in tags.items():
        for tag in names:
            category = tag.split("|")[0]
            points = table["weights"].get(category, 0.0) * FRAME_WEIGHT[frame] * quality_of(tag, table)
            if points > best.get(category, {"points": 0.0})["points"]:
                best[category] = {"points": round(points, 2), "frame": frame, "rule": tag}
    ordered = dict(sorted(best.items(), key=lambda x: -x[1]["points"]))
    return Score(round(sum(v["points"] for v in ordered.values()), 2), ordered)
