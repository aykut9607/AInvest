"""The confirmation score (0-100), Aykut, 26 Nov 2026. Every rule earns points from its OWN success on its own timeframe and asset:
quality = the larger of the Wilson lower bound at 80 % confidence and 0.8 x the success rate, with at least 5 cases and at least 51 % (else 0).
The 100 is shared: HTF (4h and up) 70, LTF (15m-2h) 30, in proportion to the qualities, so that the best rule of every category on both sides,
all at once, make exactly 100. At one top every category counts once per side with its best timeframe; the same category on further timeframes
of that side adds +5 % each, at most +10 % (15m + 30m divergence adds little, 15m + 4h a lot). A trade never rests on a single category.
The points per timeframe and rule are in table.json (made by fit.py from the backtest, one table per asset)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from signals.live import plan as planning

TABLE = Path(__file__).with_name("table.json")
LTF_FRAMES = ("15m", "30m", "45m", "1h", "2h")
SHARE = {"HTF": 70.0, "LTF": 30.0}
MORE_FRAMES, MORE_FRAMES_MAX = 0.05, 2          # +5 % for each further timeframe on the same side, at most two of them (+10 %)
MIN_CATEGORIES = 2                              # a divergence (or any other category) alone is never a trade


@dataclass(frozen=True)
class Score:
    total: float
    categories: dict[str, dict]          # category -> {points, frame, rule, also}; only what earned points


@lru_cache
def tables() -> dict:
    return json.loads(TABLE.read_text(encoding="utf-8"))


def side_of(frame: str) -> str:
    return "LTF" if frame in LTF_FRAMES else "HTF"


def points_of(tag: str, frame: str, table: dict) -> float:
    """The points of exactly this rule (with its variant) on this timeframe: what its category or sibling variants proved is not lent to it."""
    return table["points"].get(frame, {}).get(tag.removesuffix("|"), 0.0)


def combine(found: dict[str, dict[str, tuple[float, str]]]) -> Score:
    """category -> frame -> (points, rule) -> the score."""
    best = {}
    for category, frames in found.items():
        sides = []
        for side in ("HTF", "LTF"):
            here = {f: v for f, v in frames.items() if side_of(f) == side and v[0] > 0}
            if not here:
                continue
            top = max(here, key=lambda f: here[f][0])
            also = [f for f in here if f != top]
            sides.append((here[top][0] * (1 + MORE_FRAMES * min(len(also), MORE_FRAMES_MAX)), top, here[top][1], also))
        if not sides:
            continue
        lead = max(sides, key=lambda s: s[0])
        also = [f for s in sides for f in s[3] + ([] if s is lead else [s[1]])]
        best[category] = {"points": round(sum(s[0] for s in sides), 2), "frame": lead[1], "rule": lead[2], "also": also}
    ordered = dict(sorted(best.items(), key=lambda x: -x[1]["points"]))
    return Score(round(min(100.0, sum(v["points"] for v in ordered.values())), 2), ordered)


def score(tags: dict[str, list[str]], table: dict) -> Score:
    found: dict[str, dict[str, tuple[float, str]]] = {}          # category -> frame -> its best (points, rule)
    for frame, names in tags.items():
        for tag in names:
            category = tag.split("|")[0]
            points = points_of(tag, frame, table)
            here = found.setdefault(category, {})
            if points > here.get(frame, (0.0, ""))[0]:
                here[frame] = (points, tag)
    return combine(found)


def eligible(s: Score) -> bool:
    return len(s.categories) >= MIN_CATEGORIES


def kind_of(s: Score, table: dict) -> str | None:
    """The kind of trade this score allows on this asset, or None."""
    return planning.kind_of(s.total, table["limits"]) if eligible(s) else None
