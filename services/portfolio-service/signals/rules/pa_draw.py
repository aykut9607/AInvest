"""Pictures for PRICE_ACTION.md: one sketch per rule and the same rule found by pa_detect.py in our own data.

  .\\venv\\Scripts\\python.exe -m signals.rules.pa_draw                         rebuild pa-visuals.html
  .\\venv\\Scripts\\python.exe -m signals.rules.pa_draw BTCUSDT 1d 2025-06-01 2026-11-20    structure of any window
      -> data/reports/pa-check.html (git-ignored)
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

from signals.data.candles import Candle, load_series
from signals.data.download import SERVICE_DIR
from signals.rules import pa_detect as pa
from signals.rules.chart import CHART_CSS, Overlay, candle_svg
from signals.rules.elliott_draw import AMBER, RED, card, page, section, svg
from signals.structure.pivots import HIGH
from signals.structure.zigzag import zigzag

HERE = Path(__file__).parent
TR = {pa.RISING_WEDGE: "Yükselen kama", pa.FALLING_WEDGE: "Alçalan kama", pa.SYMMETRIC: "Simetrik üçgen"}
WAY = {pa.UP: "yukarı", pa.DOWN: "aşağı", None: "yok"}


def day(text: str) -> datetime:
    return datetime.fromisoformat(text).replace(tzinfo=timezone.utc)


def index_at(candles: list[Candle], when: datetime) -> int:
    return next((i for i, c in enumerate(candles) if c.time >= when), len(candles) - 1)


def figure(title: str, picture: str, note: str = "", wide: bool = True) -> str:
    return (f'<figure class="card{" wide" if wide else ""}"><h3>{title}</h3>{picture}'
            f'<p class="note">{note}</p></figure>')


def structure_figure(asset: str, tf: str, start: str, end: str, multiple: float, note: str = "") -> str:
    candles = load_series(asset, tf).candles
    points = zigzag(candles, multiple=multiple)
    i0, i1 = index_at(candles, day(start)), index_at(candles, day(end))
    over = Overlay()
    for p, label in pa.swing_labels(points):
        if i0 <= p.index <= i1:
            over.marks.append((p.index, p.price, label, "up" if p.kind == HIGH else "down"))
    for b in pa.structure_breaks(candles, points):
        if i0 <= b.level_index and b.index <= i1:
            css = "lred" if b.kind == pa.MSB else "lgreen" if b.direction == pa.UP else "lgray"
            over.lines.append((b.level_index, b.level, b.index, b.level, css, b.kind))
    for b in pa.choch_breaks(candles, points):
        if i0 <= b.level_index and b.index <= i1:
            over.lines.append((b.level_index, b.level, b.index, b.level, "lamber", "CHoCH"))
    return figure(f"{asset} {tf}: piyasa yapısı (gerçek veri, {multiple:g} × ATR)", candle_svg(candles[i0:i1 + 1], over, i0), note)


def outcome(candles: list[Candle], entry_index: int, direction: str, target: float, stop: float, limit: int) -> str:
    sign = 1 if direction == pa.UP else -1
    for c in candles[entry_index + 1:entry_index + 1 + limit]:
        if sign * (c.low if sign == 1 else c.high) <= sign * stop:
            return "stop önce"
        if sign * (c.high if sign == 1 else c.low) >= sign * target:
            return "hedefe ulaştı"
    return f"{limit} mumda ikisi de olmadı"


def pattern_figure(asset: str, tf: str, multiple: float, kind: str, first_day: str, title_note: str = "") -> str:
    """first_day: date of the pattern's first swing."""
    candles = load_series(asset, tf).candles
    found = [p for p in pa.converging_patterns(candles, zigzag(candles, multiple=multiple))
             if p.kind == kind and f"{candles[p.points[0].index].time:%Y-%m-%d}" == first_day]
    if not found:
        raise ValueError(f"{kind} {asset} {tf} {first_day} not found")
    p = found[0]
    start, end = p.points[0].index, p.points[-1].index
    stop_i = p.break_index if p.break_index is not None else int(p.apex)
    span = max(12, end - start)
    i0, i1 = max(0, start - span // 2), min(len(candles) - 1, stop_i + int(1.2 * span))
    over = Overlay()
    for side in ("upper", "lower"):
        over.lines.append((start, p.line(side, start), min(stop_i + 2, p.apex), p.line(side, min(stop_i + 2, p.apex)), "lblue", ""))
    over.marks += [(q.index, q.price, "", "up" if q.kind == HIGH else "down") for q in p.points]
    note = "kırılım yok"
    if p.break_index is not None:
        entry = candles[p.break_index].close
        sign = 1 if p.break_direction == pa.UP else -1
        level = p.line("upper" if sign == 1 else "lower", p.break_index)
        target = level + sign * p.height
        stop = min(q.price for q in p.points[-2:]) if sign == 1 else max(q.price for q in p.points[-2:])
        over.lines += [(p.break_index, target, i1, target, "lgreen", "hedef"), (p.break_index, stop, i1, stop, "lred", "stop")]
        over.marks.append((p.break_index, entry, "kırılım", "up" if sign == 1 else "down"))
        note = (f"Kırılım {WAY[p.break_direction]}, {candles[p.break_index].time:%d.%m.%Y} kapanışı; hedef = kırılan çizgi ± en geniş yer "
                f"({p.height:,.0f}). Sonuç: <b>{outcome(candles, p.break_index, p.break_direction, target, stop, 4 * span)}</b>.")
    return figure(f"{TR[kind]} — {asset} {tf} (gerçek veri)", candle_svg(candles[i0:i1 + 1], over, i0), f"{note} {title_note}")


def diamond_figure(asset: str, tf: str, multiple: float, first_day: str, note: str = "") -> str:
    candles = load_series(asset, tf).candles
    d = next(x for x in pa.diamonds(candles, zigzag(candles, multiple=multiple))
             if f"{candles[x.points[0].index].time:%Y-%m-%d}" == first_day)
    pts = d.points
    over = Overlay()
    tops, lows = [p for p in pts if p.kind == HIGH], [p for p in pts if p.kind != HIGH]
    for a, b in ((tops[0], tops[1]), (tops[1], tops[2]), (lows[0], lows[1]), (lows[1], lows[2])):
        over.lines.append((a.index, a.price, b.index, b.price, "lblue", ""))
    span = pts[-1].index - pts[0].index
    last = d.break_index if d.break_index is not None else pts[-1].confirmed_at
    i0, i1 = max(0, pts[0].index - span // 2), min(len(candles) - 1, last + int(1.2 * span))
    text = "Kırılım yok."
    if d.break_index is not None:
        sign = 1 if d.break_direction == pa.UP else -1
        entry = candles[d.break_index].close
        target, stop = entry + sign * d.height, (min if sign == 1 else max)(p.price for p in pts[-2:])
        over.lines += [(d.break_index, target, i1, target, "lgreen", "hedef"), (d.break_index, stop, i1, stop, "lred", "stop")]
        over.marks.append((d.break_index, entry, "kırılım", "up" if sign == 1 else "down"))
        text = f"Kırılım {WAY[d.break_direction]}. Sonuç: <b>{outcome(candles, d.break_index, d.break_direction, target, stop, 4 * span)}</b>."
    return figure(f"Elmas — {asset} {tf} (gerçek veri)", candle_svg(candles[i0:i1 + 1], over, i0), f"{text} {note}")


def trend_line_figure(asset: str, tf: str, multiple: float, first_day: str, note: str = "") -> str:
    candles = load_series(asset, tf).candles
    t = next(x for x in pa.trend_lines(candles, zigzag(candles, multiple=multiple))
             if f"{candles[x.touches[0].index].time:%Y-%m-%d}" == first_day)
    a, c = t.touches[0].index, t.touches[-1].index
    last = t.retest_index or t.break_index or c
    i0, i1 = max(0, a - 5), min(len(candles) - 1, last + (c - a) // 2 + 5)
    over = Overlay(lines=[(a, t.at(a), min(last + 3, i1), t.at(min(last + 3, i1)), "lblue", "")])
    over.marks += [(p.index, p.price, str(n + 1), "down" if t.direction == pa.UP else "up") for n, p in enumerate(t.touches)]
    if t.break_index is not None:
        over.marks.append((t.break_index, candles[t.break_index].close, "kırılım", "down" if t.direction == pa.UP else "up"))
    if t.retest_index is not None:
        over.marks.append((t.retest_index, t.at(t.retest_index), "retest", "up" if t.direction == pa.UP else "down"))
    return figure(f"Trend çizgisi — {asset} {tf} (gerçek veri)", candle_svg(candles[i0:i1 + 1], over, i0), note)


def level_figure(asset: str, start: str, note: str = "") -> str:
    """Monthly body levels that price came back to (within 1.5%) at least once, nearest six to the last close."""
    daily = load_series(asset, "1d").candles
    months = pa.monthly(daily)
    i0 = index_at(months, day(start))
    last = months[-1].close
    chosen: list[pa.Level] = []
    for lv in sorted(pa.body_levels(months[:-1]), key=lambda lv: abs(lv.price / last - 1)):
        back = any(m.low <= lv.price * 1.015 and m.high >= lv.price * 0.985 for m in months[lv.index + 2:])
        if back and lv.index >= i0 and all(abs(lv.price / o.price - 1) > 0.04 for o in chosen):
            chosen.append(lv)
        if len(chosen) == 5:
            break
    over = Overlay(lines=[(lv.index, lv.price, len(months) - 1, lv.price, "lred" if lv.kind == HIGH else "lgreen", "")
                          for lv in chosen])
    over.marks += [(lv.index, lv.price, f"M {lv.price:,.0f}", "up" if lv.kind == HIGH else "down") for lv in chosen]
    return figure(f"Aylık seviyeler — {asset} (gerçek veri)", candle_svg(months[i0:], over, i0, log=True, date="%m.%y"), note)


def sketches() -> str:
    down = [100, 82, 92, 70, 82, 58, 70, 50, 75, 62, 88]
    up = [50, 68, 58, 80, 68, 92, 80, 100, 75, 88, 62]
    cards = [
        card("Düşüşte BOS, sonra MSB (PA-03, PA-04)", None,
             svg(down, ["", "", "LH", "BOS", "LH", "BOS", "LH", "LL", "MSB", "HL", "BOS"], [(70, "", RED), (75, "", AMBER)]),
             down, "Son dibi (50) yapan tepe 70: onun üstünde kapanış MSB (kırmızı çizgi). Sonra HL (62) ve 75'in kırılması yeni yönün ilk BOS'u (sarı)."),
        card("Yükselişte BOS, sonra MSB (ayna)", None,
             svg(up, ["", "", "HL", "BOS", "HL", "BOS", "HL", "HH", "MSB", "LH", "BOS"], [(80, "", RED), (75, "", AMBER)]), up,
             "Son tepeyi (100) yapan dip 80: altında kapanış MSB (notlarda CHoCH). Sonra LH (88) ve 75'in altı ilk aşağı BOS."),
        card("Yükselen kama (PA-30)", None, svg([50, 80, 64, 90, 77, 96, 70], ["", "1", "a", "2", "b", "3", "kırılım"], lines=[(1, 5, 6), (2, 4, 6)]),
             [50, 80, 64, 90, 77, 96, 70], "İki çizgi de yukarı, alt çizgi daha dik. Giriş alt çizginin altında kapanış."),
        card("Alçalan kama (PA-31)", None, svg([100, 70, 86, 60, 73, 54, 80], ["", "a", "1", "b", "2", "c", "kırılım"], lines=[(2, 4, 6), (1, 5, 6)]),
             [100, 70, 86, 60, 73, 54, 80], "İki çizgi de aşağı, üst çizgi daha dik."),
        card("Simetrik üçgen (PA-32)", None, svg([60, 100, 70, 94, 76, 89, 98], ["", "1", "a", "2", "b", "3", "kırılım"], lines=[(1, 5, 6), (2, 4, 6)]),
             [60, 100, 70, 94, 76, 89, 98], "Yön önceden bilinmez; kapanış beklenir."),
        card("Elmas (PA-33)", None, svg([80, 88, 74, 96, 66, 90, 73, 84, 60], ["", "1", "a", "2", "b", "3", "c", "4", "kırılım"], lines=[(1, 3, 3), (2, 4, 4), (3, 5, 7), (4, 6, 7)]),
             [80, 88, 74, 96, 66, 90, 73, 84, 60], "Önce genişler (2 daha yüksek, b daha düşük), sonra daralır (3 daha alçak, c daha yüksek)."),
        card("Seviye dönüşümü (PA-23)", None, svg([60, 80, 68, 80, 70, 95, 81, 100], ["", "direnç", "", "direnç", "", "", "destek", ""], [(80, "flip", AMBER)]),
             [60, 80, 68, 80, 70, 95, 81, 100], "Kırılan direnç destek olur (tersi de)."),
        card("Trend çizgisi: kırılım ve retest (PA-12, PA-13)", None, svg([50, 72, 60, 84, 70, 92, 66, 78, 60], ["1", "", "2", "", "3", "", "kırılım", "retest", ""], lines=[(0, 4, 7.3)]),
             [50, 72, 60, 84, 70, 92, 66, 78, 60], "Fitille geçmek kırılım değildir; kapanış gerekir."),
    ]
    return section("1. Kural çizimleri (kendi sayılarımız)", cards)


def handbook() -> str:
    real = [
        structure_figure("BTCUSDT", "1d", "2026-01-15", "2026-11-21", 2.0,
                         "Kırmızı çizgi MSB (trend döndü), sarı CHoCH (iç dönüş, erken uyarı), yeşil yukarı BOS, gri aşağı BOS. Çizgi kırılan tepe/dipten, <b>kapanışla</b> kırıldığı muma kadar."),
        structure_figure("GC", "1d", "2026-02-01", "2026-11-20", 2.0),
        level_figure("BTCUSDT", "2023-06-01", "Aylık mum gövdelerinin döndüğü yerler (yukarı mumun kapanışı ve ardından aşağı mum, tersi). Fiyatın sonradan "
                                              "geri geldiği, bugüne en yakın beş seviye."),
        trend_line_figure("BTCUSDT", "4h", 3.0, TREND_EXAMPLE, "Üç temas, kapanışla kırılım, sonra çizgiye dönüş (retest)."),
        *[pattern_figure(*e) for e in PATTERN_EXAMPLES],
        diamond_figure("BTCUSDT", "4h", 3, DIAMOND_EXAMPLE),
    ]
    lead = ("Üstte kuralın çizimi, altta aynı kuralın pa_detect.py ile kendi verimizde bulunmuş hali. İkisi uyuşmuyorsa kuralı yanlış anlamışım "
            "demektir: doğru görseli at, düzelteyim. Numaralar PRICE_ACTION.md'deki kurallardır.")
    body = sketches() + section("2. Aynı kurallar gerçek grafikte", real)
    return page("Price action kural görselleri", body, lead).replace("</style>", CHART_CSS + "</style>")


TREND_EXAMPLE, DIAMOND_EXAMPLE = "", ""
PATTERN_EXAMPLES: list[tuple] = []


def _pick_examples() -> None:
    """The newest trend line with a break and a retest, the newest diamond with a break (BTC 4h)."""
    global TREND_EXAMPLE, DIAMOND_EXAMPLE
    candles = load_series("BTCUSDT", "4h").candles
    points = zigzag(candles, multiple=3)
    PATTERN_EXAMPLES.clear()
    for kind, ways in ((pa.RISING_WEDGE, (pa.DOWN, pa.UP)), (pa.FALLING_WEDGE, (pa.UP, pa.DOWN)), (pa.SYMMETRIC, (pa.UP, pa.DOWN))):
        for way in ways:                                   # newest example of each kind in each break direction
            found = [p for p in pa.converging_patterns(candles, points) if p.kind == kind and p.break_direction == way]
            if found:
                PATTERN_EXAMPLES.append(("BTCUSDT", "4h", 3, kind, f"{candles[found[-1].points[0].index].time:%Y-%m-%d}"))
    t = [x for x in pa.trend_lines(candles, points) if x.retest_index is not None][-1]
    d = [x for x in pa.diamonds(candles, points) if x.break_index is not None][-1]
    TREND_EXAMPLE = f"{candles[t.touches[0].index].time:%Y-%m-%d}"
    DIAMOND_EXAMPLE = f"{candles[d.points[0].index].time:%Y-%m-%d}"


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    if len(sys.argv) == 1:
        _pick_examples()
        path = HERE / "pa-visuals.html"
        path.write_text(handbook(), encoding="utf-8")
    else:
        asset, tf, start, end = sys.argv[1:5]
        multiple = float(sys.argv[5]) if len(sys.argv) > 5 else 2.0
        path = SERVICE_DIR / "data" / "reports" / "pa-check.html"
        path.parent.mkdir(parents=True, exist_ok=True)
        body = section("Yapı", [structure_figure(asset, tf, start, end, multiple)])
        path.write_text(page("Piyasa yapısı", body).replace("</style>", CHART_CSS + "</style>"), encoding="utf-8")
    print(path)


if __name__ == "__main__":
    main()
