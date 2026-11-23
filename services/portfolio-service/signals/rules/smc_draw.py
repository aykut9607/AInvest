"""Pictures for SMART_MONEY.md: sketches and the same rules found by smc_detect.py in our own data.

  .\\venv\\Scripts\\python.exe -m signals.rules.smc_draw        rebuild smc-visuals.html
"""

from __future__ import annotations

import sys
from collections.abc import Sequence
from datetime import datetime, timedelta, timezone
from pathlib import Path

from signals.data.candles import Candle, load_series
from signals.rules import smc_detect as sm
from signals.rules.chart import CHART_CSS, Overlay, candle_svg
from signals.rules.elliott_draw import AMBER, RED, card, page, section, svg
from signals.rules.pa_detect import DOWN, UP, structure_breaks
from signals.rules.pa_draw import figure
from signals.structure.pivots import HIGH
from signals.structure.sfp import BULLISH, find_sfps
from signals.structure.zigzag import zigzag

HERE = Path(__file__).parent


def toy(rows: Sequence[tuple[float, float, float, float]]) -> list[Candle]:
    t0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
    return [Candle(time=t0 + timedelta(days=i), open=o, high=h, low=lo, close=c, volume=1) for i, (o, h, lo, c) in enumerate(rows)]


def sketch(title: str, rows: Sequence[tuple[float, float, float, float]], over: Overlay, note: str) -> str:
    return figure(title, candle_svg(toy(rows), over, date="", size=(440, 270)), note, wide=False)


def sketches() -> str:
    cards = [
        sketch("Mum formasyonları (SM-01…04)",
               [(50, 52, 40, 51), (50, 51, 46, 47), (46.5, 53, 46, 52.5), (52, 55, 49, 52.1), (51, 56, 48, 54), (53, 54.5, 50, 52)],
               Overlay(marks=[(0, 40, "pin", "down"), (2, 53, "engulfing", "up"), (3, 49, "doji", "down"), (5, 50, "inside", "down")]),
               "Pin: uzun fitil, küçük gövde. Engulfing: önceki gövdeyi kaplar. Doji: açılış ≈ kapanış. Inside: öncekinin içinde."),
        sketch("FVG (SM-60)", [(50, 53, 49, 52), (52, 62, 51.5, 61), (61, 64, 57, 63), (63, 65, 60, 61), (61, 62, 55, 60), (60, 68, 59, 67)],
               Overlay(boxes=[(1, 53, 5, 57, "zgreen")], marks=[(0, 53, "1. mum yükseği", "up"), (2, 57, "3. mum düşüğü", "down")]),
               "1. mumun yükseği ile 3. mumun düşüğü arası boşluk. 5. mum boşluğun %50'sine indi, döndü."),
        sketch("Order block (SM-40)", [(60, 61, 55, 56), (56, 57, 50, 51), (51, 53, 47, 48), (48, 58, 47.5, 57), (57, 66, 56.5, 65), (65, 66, 58, 59), (59, 60, 50.5, 58), (58, 70, 57, 69)],
               Overlay(boxes=[(2, 47, 7, 53, "zgreen")], lines=[(0, 61, 4, 61, "lgreen", "yapı kırıldı"), (2, 50, 7, 50, "lgray", "0,5")]),
               "Yapıyı kıran hareketten önceki <b>son kırmızı mum</b>. Bölge mumun tamamı, giriş 0,5'i. Stop bölgenin altı."),
        card("Breaker (SM-50)", None, svg([60, 78, 70, 92, 80, 100, 66, 84, 55], ["", "", "", "", "HL", "HH", "MSB", "retest", ""], [(80, "kırılan HL", RED)]),
             [60, 78, 70, 92, 80, 100, 66, 84, 55], "HH'yi yapan dip (80) kapanışla kırıldı: eski destek, alttan geri gelişte direnç."),
        card("Range ve deviasyon (SM-20…23)", None, svg([70, 100, 60, 98, 61, 86, 54, 80, 100], ["", "RH", "RL", "RH", "RL", "", "süpürme", "EQ", "RH"], [(100, "range yüksek", AMBER), (80, "EQ", AMBER), (60, "range düşük", AMBER)]),
             [70, 100, 60, 98, 61, 86, 54, 80, 100], "Alt uç süpürülür, kapanış içeri döner → hedef EQ, sonra üst uç. Ortada işlem yok."),
        sketch("SFP (SM-30)", [(50, 54, 49, 53), (53, 60, 52, 58), (58, 59, 52, 53), (53, 56, 51, 55), (55, 63, 53, 54), (54, 55, 46, 47)],
               Overlay(lines=[(1, 60, 5, 60, "lred", "önceki tepe")], marks=[(4, 63, "fitil geçti, altında kapandı", "up")]),
               "Önceki tepenin <b>fitil ucu</b> geçilir, aynı (ya da sonraki) mum altında kapanır. Stop fitilin ucu."),
        sketch("Arz-talep (SM-10)", [(60, 61, 55, 56), (56, 57, 53, 54), (54, 55, 53, 54.5), (54.5, 55.5, 53.2, 54), (54, 64, 53.8, 63), (63, 66, 61, 65), (65, 66, 58, 59), (59, 60, 54.5, 57), (57, 67, 56, 66)],
               Overlay(boxes=[(2, 53, 8, 55.5, "zgreen")]), "Küçük mumlardan oluşan taban + güçlü mum. İlk dönüş (taze bölge) en güçlüsü."),
        card("Eşit tepeler = likidite (SM-70)", None, svg([60, 90, 75, 90, 78, 96, 62], ["", "EQH", "", "EQH", "", "süpürme", ""], [(90, "$", RED)]),
             [60, 90, 75, 90, 78, 96, 62], "Belirgin eşit tepelerin üstünde stoplar birikir: önce oraya gidilir, sonra dönülür. Stop oraya konmaz."),
        card("OTE (SM-55)", None, svg([60, 100, 72, 104], ["1 (LL)", "0 (HH)", "giriş", "hedef"], [(75.2, "0,62", AMBER), (71.8, "0,705", AMBER), (68.4, "0,79", AMBER)]),
             [60, 100, 72, 104], "Son hareketin 0,62–0,79'u. Hedef 0, sonra −0,27 / −0,67 / −1. Stop 1'in ötesi."),
        card("Power of 3 (SM-90)", None, svg([80, 86, 79, 86, 80, 70, 100], ["", "", "", "", "", "manipülasyon", "dağıtım"], [(86, "birikim üst", AMBER), (79, "birikim alt", AMBER)]),
             [80, 86, 79, 86, 80, 70, 100], "Birikim (dar aralık) → bir uç süpürülür (sahte hareket) → asıl hareket ters yöne."),
    ]
    return section("1. Kural çizimleri (kendi sayılarımız)", cards)


def window(candles: Sequence[Candle], i0: int, i1: int) -> tuple[int, int]:
    return max(0, i0), min(len(candles) - 1, i1)


def zone_figure(title: str, candles: list[Candle], zone: sm.Zone, after: int, before: int = 12, extra: Overlay | None = None, note: str = "") -> str:
    touch = sm.first_touch(candles, zone)
    i0, i1 = window(candles, zone.index - before, (touch if touch is not None else zone.known_at) + after)
    over = extra or Overlay()
    over.boxes.append((zone.index, zone.low, i1, zone.high, "zgreen" if zone.direction == UP else "zred"))
    over.lines.append((zone.index, zone.mid, i1, zone.mid, "lgray", "0,5"))
    if touch is not None:
        over.marks.append((touch, zone.high if zone.direction == UP else zone.low, "ilk dönüş", "down" if zone.direction == UP else "up"))
    q = f" Kalite: {', '.join(zone.quality)}." if zone.quality else ""
    return figure(title, candle_svg(candles[i0:i1 + 1], over, i0), note + q)


def newest(zones: list[sm.Zone], candles: list[Candle], direction: str, wait: tuple[int, int], need: str | None = None) -> sm.Zone:
    """Newest zone of a direction whose first touch came within `wait` bars after it was known."""
    for z in reversed(zones):
        if z.direction != direction or (need and need not in z.quality):
            continue
        t = sm.first_touch(candles, z)
        if t is not None and wait[0] <= t - z.known_at <= wait[1] and t + 10 < len(candles):
            return z
    raise ValueError(f"no example: {direction}")


def real() -> str:
    day, four = load_series("BTCUSDT", "1d").candles, load_series("BTCUSDT", "4h").candles
    hour = load_series("BTCUSDT", "1h").candles
    pd, p4 = zigzag(day, multiple=1.5), zigzag(four, multiple=2)
    figures = []
    for direction, name in ((UP, "yükselen"), (DOWN, "düşen")):
        z = newest(sm.fair_value_gaps(day, 0.4), day, direction, (2, 40))
        figures.append(zone_figure(f"FVG ({name}) — BTC 1d", day, z, 15, note="Üç mumlu boşluk ve ilk dönüş."))
    blocks = sm.order_blocks(day, pd)
    for direction, name in ((UP, "yükselen"), (DOWN, "düşen")):
        z = newest(blocks, day, direction, (2, 60), "FVG")
        b = next(b for b in structure_breaks(day, pd) if b.index == z.known_at)
        figures.append(zone_figure(f"Order block ({name}) — BTC 1d", day, z, 15,
                                   extra=Overlay(lines=[(b.level_index, b.level, b.index, b.level, "lgreen" if direction == UP else "lred", b.kind)]),
                                   note="Kapanışla yapıyı kıran hareketten önceki son ters mum."))
    for direction, name in ((DOWN, "düşen"), (UP, "yükselen")):
        z = newest(sm.breakers(day, zigzag(day, multiple=2)), day, direction, (1, 60))
        figures.append(zone_figure(f"Breaker ({name}) — BTC 1d", day, z, 15,
                                   extra=Overlay(lines=[(z.index, z.low if direction == DOWN else z.high, z.known_at, z.low if direction == DOWN else z.high, "lred", "MSB")]),
                                   note="MSB ile kırılan dip/tepe, geri gelişte ters rol."))
    # range with a deviation that reached EQ
    for rng in reversed(sm.ranges(p4)):
        dev = [d for d in sm.deviations(four, rng) if d.back_index + 12 < len(four)]
        if dev:
            d = dev[0]
            i0, i1 = window(four, rng.start - 8, d.back_index + 45)
            over = Overlay(lines=[(rng.start, rng.high, i1, rng.high, "lblue", "RH"), (rng.start, rng.eq, i1, rng.eq, "lgray", "EQ"),
                                  (rng.start, rng.low, i1, rng.low, "lblue", "RL")])
            over.marks.append((d.index, d.extreme, "süpürme", "up" if d.side == HIGH else "down"))
            figures.append(figure("Range ve deviasyon — BTC 4h", candle_svg(four[i0:i1 + 1], over, i0),
                                  "İki tepe ve iki dip %15 içinde. Ucun ötesine geçip en çok 3 mumda içeri kapanış = deviasyon."))
            break
    s = [x for x in find_sfps(day) if x.confirmed_at + 12 < len(day)][-1]
    i0, i1 = window(day, s.pivot_index - 8, s.confirmed_at + 12)
    css = "lgreen" if s.direction == BULLISH else "lred"
    level = day[s.pivot_index].low if s.direction == BULLISH else day[s.pivot_index].high
    figures.append(figure("SFP — BTC 1d", candle_svg(day[i0:i1 + 1], Overlay(
        lines=[(s.pivot_index, level, s.confirmed_at, level, css, "")],
        marks=[(s.confirmed_at, day[s.confirmed_at].low if s.direction == BULLISH else day[s.confirmed_at].high, "SFP", "down" if s.direction == BULLISH else "up")]), i0),
        "Pivotun fitil ucu geçilip mum geri kapandı."))
    z = newest(sm.supply_demand(day), day, DOWN, (2, 60))
    figures.append(zone_figure("Arz bölgesi — BTC 1d", day, z, 15, note="Küçük taban + güçlü mum, ilk dönüş."))
    a, b = [(a, b) for a, b in sm.equal_levels(day, pd) if b.index + 20 < len(day)][-1]
    i0, i1 = window(day, a.index - 8, b.index + 30)
    figures.append(figure("Eşit tepe/dip (likidite) — BTC 1d", candle_svg(day[i0:i1 + 1], Overlay(
        lines=[(a.index, a.price, i1, a.price, "lamber", "$")],
        marks=[(a.index, a.price, "EQH" if a.kind == HIGH else "EQL", "up" if a.kind == HIGH else "down"),
               (b.index, b.price, "EQH" if b.kind == HIGH else "EQL", "up" if b.kind == HIGH else "down")]), i0), "İki uç 0,25 ATR içinde eşit."))
    last = day[-1].time
    when = last - timedelta(days=last.weekday() - 2) if last.weekday() >= 2 else last - timedelta(days=last.weekday() + 5)
    levels = sm.key_levels(day, when)
    i0 = next(i for i, c in enumerate(four) if c.time >= when - timedelta(days=12))
    i1 = min(len(four) - 1, next(i for i, c in enumerate(four) if c.time >= when) + 24)
    keep: list[str] = []                       # levels closer than 0.6% share one line and one label
    names: dict[str, str] = {}
    for n in sorted((n for n in levels if n.startswith(("Önceki hafta", "Pazartesi", "Hafta", "Ay"))), key=lambda n: levels[n]):
        if keep and abs(levels[n] / levels[keep[-1]] - 1) < 0.006:
            names[keep[-1]] += " / " + n
        else:
            keep.append(n)
            names[n] = n
    figures.append(figure(f"Kilit seviyeler — BTC 4h, {when:%d.%m.%Y} itibarıyla", candle_svg(four[i0:i1 + 1], Overlay(
        lines=[(i0 + (i1 - i0) * 0.45, levels[n], i1, levels[n], "lgray" if "orta" in n else "lblue", names[n]) for n in keep]), i0),
        "Önceki hafta, Pazartesi aralığı, hafta ve ay açılışı. Hepsi o an bilinen değerler."))
    po = [p for p in sm.power_of_3(hour) if p.distribution is not None][-1]
    i0, i1 = window(hour, po.first - 4, po.first + 24)
    edge = min(hour[i].low for i in range(po.first + 8, po.first + 13)) if po.swept != HIGH else max(hour[i].high for i in range(po.first + 8, po.first + 13))
    boxes = [(po.first, po.low, po.first + 7, po.high, "zblue"),
             (po.first + 8, min(edge, po.low if po.swept != HIGH else po.high), po.first + 12, max(edge, po.low if po.swept != HIGH else po.high), "zred")]
    figures.append(figure(f"Power of 3 — BTC 1h, {po.day:%d.%m.%Y}", candle_svg(hour[i0:i1 + 1], Overlay(
        boxes=boxes, lines=[(po.first, po.high, i1, po.high, "lgray", ""), (po.first, po.low, i1, po.low, "lgray", "")],
        marks=[(po.back_index, hour[po.back_index].close, "içeri kapanış", "down"), (po.distribution, hour[po.distribution].close, "dağıtım", "up")]), i0, date="%d.%m %H:%M"),
        "Mavi: Asya aralığı (00–08 UTC), kırmızı: Londra'da (08–13) süpürme, sonra New York'ta karşı uç."))
    return section("2. Aynı kurallar gerçek grafikte (kodun bulduğu son örnekler)", figures)


def handbook() -> str:
    lead = ("Üstte kuralın çizimi, altta aynı kuralın smc_detect.py ile kendi verimizde bulunmuş hali. Uyuşmuyorsa kuralı yanlış anlamışım "
            "demektir: doğru görseli at, düzelteyim. Numaralar SMART_MONEY.md'deki kurallardır. Örnekler başarılarına göre değil, "
            "<b>en yeni</b> olana göre seçildi.")
    return page("İleri düzey kural görselleri", sketches() + real(), lead).replace("</style>", CHART_CSS + "</style>")


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    path = HERE / "smc-visuals.html"
    path.write_text(handbook(), encoding="utf-8")
    print(path)


if __name__ == "__main__":
    main()
