"""Statistics and the calibration table (RULES.md 9).

Per rule x variant x sample (calibration / untouched test):
  n, wins, win rate with its 95% Wilson interval, average R, worst losing streak,
  and the same numbers for random entries (same direction, same stop/target distances, same holding limit),
  plus buy & hold over the sample. Score v0 = 100 x the lower Wilson bound of the TEST sample's win rate: a rule only
  earns points for what it proved on data it was not tuned on, and few trades give a wide interval -> few points.
"""

from __future__ import annotations

import math
import random
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

from signals.backtest.engine import LONG, Params, Trade, WIN
from signals.data.candles import Candle

CALIBRATION, TEST = "calibration", "test"


def wilson(wins: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """95% confidence interval of a win rate; honest for small samples (unlike +-1.96 x standard error)."""
    if n == 0:
        return 0.0, 0.0
    p = wins / n
    denominator = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denominator
    margin = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denominator
    return max(0.0, centre - margin), min(1.0, centre + margin)


def worst_streak(trades: Sequence[Trade]) -> int:
    worst = current = 0
    for t in sorted(trades, key=lambda t: t.entry_time):
        current = 0 if t.outcome == WIN else current + 1
        worst = max(worst, current)
    return worst


def random_baseline(candles: Sequence[Candle], trades: Sequence[Trade], params: Params,
                    start: datetime, end: datetime, per_trade: int = 20, seed: int = 44) -> tuple[float, float, int]:
    """Win rate and average R of random entries with each trade's direction and stop/target distances."""
    rng = random.Random(seed)
    indices = [i for i, c in enumerate(candles) if start <= c.time < end and i + 1 < len(candles)]
    if not indices or not trades:
        return 0.0, 0.0, 0
    wins, total_r, n = 0, 0.0, 0
    for t in trades:
        sign = 1 if t.setup.direction == LONG else -1
        stop_distance = abs(t.entry_price - t.setup.invalidation) / t.entry_price
        target_distance = abs(t.setup.target - t.entry_price) / t.entry_price
        for _ in range(per_trade):
            i = rng.choice(indices)
            entry = candles[i].close
            stop, target = entry * (1 - sign * stop_distance), entry * (1 + sign * target_distance)
            exit_price, won = None, False
            for j in range(i + 1, min(len(candles), i + 1 + params.max_hold)):
                bar = candles[j]
                if (bar.low <= stop) if sign == 1 else (bar.high >= stop):
                    exit_price = stop
                    break
                if (bar.high >= target) if sign == 1 else (bar.low <= target):
                    exit_price, won = target, True
                    break
            if exit_price is None:
                exit_price = candles[min(len(candles) - 1, i + params.max_hold)].close
            risk = abs(entry - stop)
            total_r += (exit_price - entry) * sign / risk - 2 * params.fee * entry / risk
            wins += won
            n += 1
    return wins / n, total_r / n, n


@dataclass
class Row:
    rule: str
    asset: str
    timeframe: str
    variant: str
    sample: str
    period: str
    n: int
    wins: int
    win_rate: float
    ci: tuple[float, float]
    avg_r: float
    worst_streak: int
    random_win_rate: float
    random_avg_r: float
    buy_hold: float
    score: int | None           # TEST rows only


def build_rows(trades: Sequence[Trade], candles: Sequence[Candle], split: datetime, params: Params) -> list[Row]:
    if not candles:
        return []
    first, last = candles[0].time, candles[-1].time
    groups: dict[tuple, list[Trade]] = defaultdict(list)
    for t in trades:
        sample = CALIBRATION if t.entry_time < split else TEST
        groups[(t.setup.rule, t.setup.asset, t.setup.timeframe, t.variant, sample)].append(t)

    rows = []
    for (rule, asset, timeframe, variant, sample), group in sorted(groups.items()):
        start, end = (first, split) if sample == CALIBRATION else (split, last)
        wins = sum(t.outcome == WIN for t in group)
        n = len(group)
        ci = wilson(wins, n)
        rnd_wr, rnd_r, _ = random_baseline(candles, group, params, start, end)
        window = [c for c in candles if start <= c.time <= end]
        buy_hold = window[-1].close / window[0].close - 1 if len(window) > 1 else 0.0
        rows.append(Row(rule, asset, timeframe, variant, sample, f"{start:%Y-%m-%d} – {end:%Y-%m-%d}", n, wins,
                        wins / n, ci, sum(t.r for t in group) / n, worst_streak(group), rnd_wr, rnd_r, buy_hold,
                        round(100 * ci[0]) if sample == TEST else None))
    return rows


def markdown(rows: Sequence[Row], header: str) -> str:
    lines = [header, "",
             "| Kural | Varlık / dilim | Giriş | Örnek | Dönem | n | Başarı | %95 aralık | Ort. R | En kötü seri "
             "| Rastgele başarı / R | Al-tut | Puan v0 |",
             "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        lines.append(
            f"| {r.rule} | {r.asset} {r.timeframe} | {r.variant} | {'kalibrasyon' if r.sample == CALIBRATION else 'test'} "
            f"| {r.period} | {r.n} | %{100 * r.win_rate:.0f} | %{100 * r.ci[0]:.0f}–{100 * r.ci[1]:.0f} "
            f"| {r.avg_r:+.2f} | {r.worst_streak} | %{100 * r.random_win_rate:.0f} / {r.random_avg_r:+.2f} "
            f"| {100 * r.buy_hold:+.0f}% | {'' if r.score is None else r.score} |")
    return "\n".join(lines)
