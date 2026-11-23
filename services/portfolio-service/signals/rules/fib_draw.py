"""Draw the user's Fibonacci tools.

  .\\venv\\Scripts\\python.exe -m signals.rules.fib_draw                                rebuild fib-visuals.html
  .\\venv\\Scripts\\python.exe -m signals.rules.fib_draw trend 57755.8 66937.7 62240    0, 1, 2
  .\\venv\\Scripts\\python.exe -m signals.rules.fib_draw fine  57755.8 66937.7 62240    0, 1, 2 (the second trend set)
  .\\venv\\Scripts\\python.exe -m signals.rules.fib_draw ret   55100 64572.5            start, end
  .\\venv\\Scripts\\python.exe -m signals.rules.fib_draw mon   64572.5 60350            Monday high, low
"""

from __future__ import annotations

import html
import sys
from collections.abc import Sequence
from pathlib import Path

from signals.data.download import SERVICE_DIR
from signals.rules import fib_tools as ft
from signals.rules.elliott_draw import page, section

HERE = Path(__file__).parent
W, H = 460, 400
COLOUR = {ft.SUPPORT: "var(--good)", ft.EQUAL: "var(--bad)", ft.TRIGGER: "var(--guide)", ft.TARGET: "var(--motive)",
          ft.FAR: "var(--corr)", ft.POCKET: "var(--bad)", ft.MIDDLE: "var(--ink)", ft.EDGE: "var(--ink)",
          ft.SWEEP: "var(--guide)", ft.DEEP: "var(--good)", ft.MINOR: "var(--corr)"}
ROLE = {ft.SUPPORT: "tutma bölgesi", ft.EQUAL: "eşitlik", ft.TRIGGER: "tetik", ft.TARGET: "hedef", ft.FAR: "uzak hedef",
        ft.POCKET: "ana bölge", ft.MIDDLE: "orta", ft.EDGE: "uç", ft.SWEEP: "süpürme bölgesi", ft.DEEP: "derin", ft.MINOR: "ara seviye"}


def svg(levels: Sequence[ft.FibLevel], points: Sequence[tuple[str, float]], path: Sequence[float] = ()) -> str:
    """points: labelled anchors at the left; path: prices of a sketch drawn after them."""
    walk = [p for _, p in points] + list(path)
    every = [lv.price for lv in levels] + walk
    low, high = min(every), max(every)

    def y(price: float) -> float:
        return 18 + (high - price) / ((high - low) or 1.0) * (H - 36)

    def x(i: int) -> float:
        return 26 + i / max(1, len(walk) - 1) * 220

    out = [f'<svg viewBox="0 0 {W} {H}" role="img">']
    rows: list[float] = []
    for lv in sorted(levels, key=lambda lv: -lv.price):
        text_y = max(y(lv.price) + 4, (rows[-1] + 13) if rows else 0)        # keep neighbouring labels apart
        rows.append(text_y)
        out.append(f'<line x1="14" x2="286" y1="{y(lv.price):.1f}" y2="{y(lv.price):.1f}" '
                   f'style="stroke:{COLOUR[lv.role]};stroke-width:1.6"/>'
                   f'<line x1="286" x2="298" y1="{y(lv.price):.1f}" y2="{text_y - 4:.1f}" style="stroke:{COLOUR[lv.role]};stroke-width:1"/>'
                   f'<text x="302" y="{text_y:.1f}" style="font-size:11px">{lv.ratio:g} <tspan class="p">{lv.price:,.1f} · '
                   f'{ROLE[lv.role]}</tspan></text>')
    out.append('<polyline class="sub" style="stroke:var(--ink);stroke-width:2" points="'
               + " ".join(f"{x(i):.1f},{y(p):.1f}" for i, p in enumerate(walk)) + '"/>')
    for i, (label, price) in enumerate(points):
        out.append(f'<circle class="dot" cx="{x(i):.1f}" cy="{y(price):.1f}" r="4"/>'
                   f'<text x="{x(i):.1f}" y="{y(price) - 8:.1f}" text-anchor="middle">{html.escape(label)}</text>')
    return "".join(out) + "</svg>"


def card(title: str, levels: Sequence[ft.FibLevel], points: Sequence[tuple[str, float]], note: str = "",
         path: Sequence[float] = ()) -> str:
    note = f'<p class="note">{note}</p>' if note else ""
    return f'<figure class="card"><h3>{html.escape(title)}</h3>{svg(levels, points, path)}{note}</figure>'


def only(levels: list[ft.FibLevel], low: float, high: float) -> list[ft.FibLevel]:
    return [lv for lv in levels if low <= lv.ratio <= high]


def trend_card(p0: float, p1: float, p2: float, fine: bool = False, top: float = 3.0, note: str = "",
               path: Sequence[float] = ()) -> str:
    levels = ft.trend_extension(p0, p1, p2, ft.TREND_FINE if fine else ft.TREND)
    title = "Trend fib (ikinci, ince set)" if fine else "Trend fib (ana set)"
    return card(title, only(levels, 0, top), [("0", p0), ("1", p1), ("2", p2)], note, path)


def handbook() -> str:
    parts = [
        section("1. Dört araç (kendi sayılarımız)", [
            trend_card(100, 160, 130, note="0 → 1 → 2. Seviye k = 2 + k × (1 − 0). Yeşil 0,618–0,786 tutma bölgesi, 1,272 tetik, 1,414–1,618 hedef."),
            trend_card(100, 160, 130, fine=True, top=1.7, note="İnce set: 1,114–1,214 eşitliğin hemen ötesi (süpürme), 1,34–1,382 ara seviye."),
            card("Fib retracement", ft.retracement(100, 160), [("1", 100), ("0", 160)],
                 "0 hareketin sonu, 1 başı. 0,34–0,382 sığ, 0,618–0,66 ana bölge, 0,709, sonra 0,786 ve 0,886 derin.", path=[123]),
            card("Pazartesi aralığı", only(ft.monday_range(160, 140), -0.7, 1.7), [("0", 160), ("1", 140)],
                 "Pazartesi mumu KAPANDIKTAN sonra çizilir. Uçların dışındaki süpürme bölgesi ve geri dönüş aranır.", path=[158, 163, 157, 150]),
        ]),
        section("2. Düşüncenin çizimi", [
            trend_card(100, 160, 130, top=2.0, path=[227, 168, 190],
                       note="Hedeften dönüş → yeşil bölge. Bu örnekte 1. dalganın tepesi 0,5 seviyesinde (2, 1'i %50 geri almış): "
                            "oraya değen 4. dalga E-04'ü bozar. Yeşil bölge bu sınırın hemen üstüdür."),
            trend_card(100, 160, 130, top=2.0, path=[207, 200, 227],
                       note="1,272 üstünde kapanış → hedef 1,414 / 1,618. İptal: 1'in altına dönüş (öneri)."),
            trend_card(160, 100, 130, top=2.0, note="Düşen yapı = ayna."),
        ]),
    ]
    lead = "Seviyeler Aykut'un TradingView ayarları; sayıları fib_tools.py hesaplar (ekran görüntüleriyle aynı). Kurallar: FIBONACCI.md."
    return page("Fibonacci araçları", "".join(parts), lead)


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    if len(sys.argv) == 1:
        path = HERE / "fib-visuals.html"
        path.write_text(handbook(), encoding="utf-8")
    else:
        tool, values = sys.argv[1], [float(a) for a in sys.argv[2:]]
        if tool in ("trend", "fine"):
            levels = ft.trend_extension(*values, ft.TREND if tool == "trend" else ft.TREND_FINE)
            body = trend_card(*values, fine=tool == "fine")
            print(f"1. dalganın sonu (E-04 sınırı) = {ft.wave1_end_as_extension(*values):.3f} seviyesi")
        elif tool == "ret":
            levels = ft.retracement(*values)
            body = card("Fib retracement", levels, [("1", values[0]), ("0", values[1])])
        elif tool == "mon":
            levels = ft.monday_range(*values)
            body = card("Pazartesi aralığı", levels, [("0", values[0]), ("1", values[1])])
        else:
            raise SystemExit("tool: trend | fine | ret | mon")
        for lv in levels:
            print(f"  {lv.ratio:>7g}  {lv.price:>12,.1f}  {ROLE[lv.role]}")
        path = SERVICE_DIR / "data" / "reports" / "fib-check.html"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(page("Fibonacci", section("Seviyeler", [body])), encoding="utf-8")
    print(f"\n{path}")


if __name__ == "__main__":
    main()
