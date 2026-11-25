"""The confirmation score (0-100): every category counts once, with its own weight, the weight of the timeframe it was found on and how well
that very rule did in the backtest. The same category on further timeframes adds a little (Aykut). What decides is the sum, not a checklist; only
one thing is required: a trade never rests on a single category. Weights and limits are in table.json (made by fit.py, one table per asset)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from signals.data.candles import TIMEFRAMES
from signals.live import plan as planning

TABLE = Path(__file__).with_name("table.json")
# the higher the timeframe, the more a confirmation counts (Aykut); equal steps from 0.45 to 1
FRAME_WEIGHT = {f: round(0.45 + 0.05 * i, 2) for i, f in enumerate(TIMEFRAMES)}
MORE_FRAMES, MORE_FRAMES_MAX = 0.05, 4          # +5 % of the category's points for each further timeframe, at most four of them
MIN_CATEGORIES = 2                              # a divergence (or any other category) alone is never a trade


@dataclass(frozen=True)
class Score:
    total: float
    categories: dict[str, dict]          # category -> {points, frame, rule, also}; only what earned points


@lru_cache
def tables() -> dict:
    return json.loads(TABLE.read_text(encoding="utf-8"))


def quality_of(tag: str, table: dict) -> float:
    """0-1: the backtest value of exactly this rule (with its variant) compared with the best rule of its category. A rule that proved nothing
    gives 0: what its category or its sibling variants proved is not lent to it (Aykut)."""
    return table["quality"].get(tag.removesuffix("|"), 0.0)


def score(tags: dict[str, list[str]], table: dict) -> Score:
    found: dict[str, dict[str, tuple[float, str]]] = {}          # category -> frame -> its best (points, rule)
    for frame, names in tags.items():
        for tag in names:
            category = tag.split("|")[0]
            points = table["weights"].get(category, 0.0) * FRAME_WEIGHT[frame] * quality_of(tag, table)
            here = found.setdefault(category, {})
            if points > here.get(frame, (0.0, ""))[0]:
                here[frame] = (points, tag)
    best = {}
    for category, frames in found.items():
        if not frames:
            continue
        frame = max(frames, key=lambda f: frames[f][0])
        also = [f for f in frames if f != frame]
        points = frames[frame][0] * (1 + MORE_FRAMES * min(len(also), MORE_FRAMES_MAX))
        best[category] = {"points": round(points, 2), "frame": frame, "rule": frames[frame][1], "also": also}
    ordered = dict(sorted(best.items(), key=lambda x: -x[1]["points"]))
    return Score(round(min(100.0, sum(v["points"] for v in ordered.values())), 2), ordered)


def eligible(s: Score) -> bool:
    return len(s.categories) >= MIN_CATEGORIES


def kind_of(s: Score, table: dict) -> str | None:
    """The kind of trade this score allows on this asset, or None."""
    return planning.kind_of(s.total, table["limits"]) if eligible(s) else None
