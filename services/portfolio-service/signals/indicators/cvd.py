"""CVD (cumulative volume delta) from Binance's taker-buy volume (BTCUSDT only; Yahoo futures have no buy/sell split).

Per candle: delta = buyer-initiated volume - seller-initiated volume = 2 x taker_buy_volume - volume.
CVD is the running sum of the deltas. For a divergence only the shape matters (higher/lower lows and highs between two
pivots), so the starting point of the sum does not change the result (RULES.md 3).
"""

from __future__ import annotations

from collections.abc import Sequence

from signals.data.candles import Candle
from signals.indicators.rsi_divergence import Divergence, DivergenceSettings, divergences


def cvd(candles: Sequence[Candle]) -> list[float | None]:
    """Running CVD; None for every candle if the series has no taker-buy volume (futures)."""
    if any(c.taker_buy_volume is None for c in candles):
        return [None] * len(candles)
    total, out = 0.0, []
    for c in candles:
        total += 2 * c.taker_buy_volume - c.volume
        out.append(total)
    return out


def cvd_divergences(candles: Sequence[Candle], settings: DivergenceSettings = DivergenceSettings()) -> list[Divergence]:
    """Same four divergence kinds as the RSI indicator, with CVD as the oscillator; empty for futures."""
    return divergences(candles, cvd(candles), "CVD", settings)
