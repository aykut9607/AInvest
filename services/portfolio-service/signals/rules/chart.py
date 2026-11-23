"""Candle charts of our own downloaded data with rule annotations, as inline SVG (no external resources)."""

from __future__ import annotations

import html
import math
from collections.abc import Sequence
from dataclasses import dataclass, field

from signals.data.candles import Candle

SIZE = (760, 380)
LEFT, RIGHT, TOP, BOTTOM = 8, 74, 16, 26

CHART_CSS = """
.cu{stroke:var(--good);fill:var(--good)}.cd{stroke:var(--bad);fill:var(--bad)}.wide{grid-column:1/-1}
.lblue{stroke:var(--motive);stroke-width:1.8}.lred{stroke:var(--bad);stroke-width:1.6}.lgreen{stroke:var(--good);stroke-width:1.6}
.lamber{stroke:var(--guide);stroke-width:1.6}.lgray{stroke:var(--corr);stroke-width:1.2;stroke-dasharray:4 3}
.zgreen{fill:var(--good);opacity:.14}.zred{fill:var(--bad);opacity:.14}.zblue{fill:var(--motive);opacity:.14}
svg text.t{font-size:11.5px}svg text.ax{font-size:10.5px;font-weight:400;fill:var(--muted)}
"""


@dataclass
class Overlay:
    lines: list[tuple[float, float, float, float, str, str]] = field(default_factory=list)   # i0, p0, i1, p1, class, text
    marks: list[tuple[float, float, str, str]] = field(default_factory=list)                 # i, price, text, "up" / "down"
    boxes: list[tuple[float, float, float, float, str]] = field(default_factory=list)        # i0, low, i1, high, class


def candle_svg(candles: Sequence[Candle], overlay: Overlay, first: int = 0, log: bool = False, date: str = "%d.%m.%y",
               size: tuple[int, int] = SIZE) -> str:
    """candles: the window to draw; `first` = index of its first candle (overlay coordinates are series indices)."""
    W, H = size
    n = len(candles)
    prices = [c.high for c in candles] + [c.low for c in candles]
    prices += [p for _, p0, _, p1, _, _ in overlay.lines for p in (p0, p1)] + [p for _, p, _, _ in overlay.marks]
    f = math.log if log else (lambda v: v)
    low, high = f(min(prices)), f(max(prices))
    pad = (high - low) * 0.06
    low, high = low - pad, high + pad

    def x(i: float) -> float:
        return LEFT + (i - first + 0.5) / n * (W - LEFT - RIGHT)

    def y(p: float) -> float:
        return TOP + (high - f(p)) / ((high - low) or 1) * (H - TOP - BOTTOM)

    out = [f'<svg viewBox="0 0 {W} {H}" role="img">']
    for k in range(5):
        value = low + (high - low) * k / 4
        price = math.exp(value) if log else value
        out.append(f'<line x1="{LEFT}" x2="{W - RIGHT}" y1="{y(price):.1f}" y2="{y(price):.1f}" style="stroke:var(--grid)"/>'
                   f'<text class="ax" x="{W - RIGHT + 5}" y="{y(price) + 4:.1f}">{price:,.0f}</text>')
    for k in range(5):
        i = int(k * (n - 1) / 4)
        anchor = "start" if k == 0 else "end" if k == 4 else "middle"
        out.append(f'<text class="ax" x="{x(first + i):.1f}" y="{H - 8}" text-anchor="{anchor}">{candles[i].time:{date}}</text>')
    for i0, p0, i1, p1, css in overlay.boxes:
        out.append(f'<rect class="{css}" x="{x(i0):.1f}" y="{y(p1):.1f}" width="{max(1.0, x(i1) - x(i0)):.1f}" '
                   f'height="{max(1.0, y(p0) - y(p1)):.1f}"/>')
    body = max(1.0, 0.62 * (W - LEFT - RIGHT) / n)
    for k, c in enumerate(candles):
        css, cx = ("cu" if c.close >= c.open else "cd"), x(first + k)
        top, bottom = y(max(c.open, c.close)), y(min(c.open, c.close))
        out.append(f'<g class="{css}"><line x1="{cx:.1f}" x2="{cx:.1f}" y1="{y(c.high):.1f}" y2="{y(c.low):.1f}"/>'
                   f'<rect x="{cx - body / 2:.1f}" y="{top:.1f}" width="{body:.1f}" height="{max(1.0, bottom - top):.1f}"/></g>')
    for i0, p0, i1, p1, css, text in overlay.lines:
        out.append(f'<line class="{css}" x1="{x(i0):.1f}" y1="{y(p0):.1f}" x2="{x(i1):.1f}" y2="{y(p1):.1f}"/>')
        if text:
            out.append(f'<text class="t" x="{min(x(i1) + 3, W - RIGHT - 4):.1f}" y="{y(p1) - 4:.1f}" '
                       f'text-anchor="{"end" if x(i1) > W - RIGHT - 60 else "start"}">{html.escape(text)}</text>')
    for i, p, text, where in overlay.marks:
        out.append(f'<circle class="dot" cx="{x(i):.1f}" cy="{y(p):.1f}" r="2.6"/><text class="t" x="{x(i):.1f}" '
                   f'y="{y(p) + (-8 if where == "up" else 17):.1f}" text-anchor="middle">{html.escape(text)}</text>')
    return "".join(out) + "</svg>"
