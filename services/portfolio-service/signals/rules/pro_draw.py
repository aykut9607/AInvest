"""Pictures for PROFESSIONAL.md: sketches and the same rules found in our own data (newest example, not the best one).

  .\\venv\\Scripts\\python.exe -m signals.rules.pro_draw        rebuild pro-visuals.html
"""

from __future__ import annotations

import sys
from collections.abc import Sequence
from datetime import timedelta
from pathlib import Path

from signals.data.candles import Candle, load_series
from signals.data.derivatives import load
from signals.indicators.cvd import cvd, cvd_divergences
from signals.indicators.rsi_divergence import HIDDEN_BULLISH, REGULAR_BEARISH, REGULAR_BULLISH, rsi, rsi_divergences
from signals.rules import pro_detect as pr
from signals.rules import smc_detect as sm
from signals.rules.chart import BOTTOM, CHART_CSS, LEFT, RIGHT, SIZE, Overlay, candle_svg
from signals.rules.elliott_draw import AMBER, RED, card, page, section, svg
from signals.rules.pa_detect import UP, structure_breaks
from signals.rules.pa_draw import figure
from signals.rules.smc_draw import sketch
from signals.structure.sfp import BULLISH, find_open_sfps
from signals.structure.zigzag import zigzag

HERE = Path(__file__).parent


def panel(values: Sequence[float | None], title: str, marks: Sequence[tuple[int, float]] = (), levels: Sequence[float] = (), height: int = 130) -> str:
    """A line under the candles (same x scale); marks: (position in the window, value), joined by a line."""
    W = SIZE[0]
    real = [v for v in values if v is not None]
    low, high = min([*real, *levels]), max([*real, *levels])
    pad = (high - low) * 0.08 or 1.0
    low, high = low - pad, high + pad
    x = lambda i: LEFT + (i + 0.5) / len(values) * (W - LEFT - RIGHT)
    y = lambda v: 6 + (high - v) / (high - low) * (height - 12)
    out = [f'<svg viewBox="0 0 {W} {height}" role="img">']
    for lv in levels:
        out.append(f'<line class="lgray" x1="{LEFT}" x2="{W - RIGHT}" y1="{y(lv):.1f}" y2="{y(lv):.1f}"/>'
                   f'<text class="ax" x="{W - RIGHT + 5}" y="{y(lv) + 4:.1f}">{lv:g}</text>')
    path = " ".join(f"{x(i):.1f},{y(v):.1f}" for i, v in enumerate(values) if v is not None)
    out.append(f'<polyline class="sub" style="stroke:var(--motive);stroke-width:1.6" points="{path}"/>')
    if len(marks) == 2:
        (i, a), (j, b) = marks
        out.append(f'<line class="lred" x1="{x(i):.1f}" y1="{y(a):.1f}" x2="{x(j):.1f}" y2="{y(b):.1f}"/>')
    out += [f'<circle class="dotbad" cx="{x(i):.1f}" cy="{y(v):.1f}" r="3.5"/>' for i, v in marks]
    out.append(f'<text class="t" x="{LEFT + 2}" y="16">{title}</text>')
    return "".join(out) + "</svg>"


def profile_svg(candles: list[Candle], i0: int, i1: int, profile: pr.Profile, overlay: Overlay) -> str:
    """Candles with the profile's histogram drawn from the left edge of its session."""
    start = next(i for i in range(i0, i1 + 1) if candles[i].time >= profile.start)
    end = next((i for i in range(i0, i1 + 1) if candles[i].time >= profile.end), i1)
    top = max(profile.bins)
    step = (profile.high - profile.low) / len(profile.bins)
    for k, v in enumerate(profile.bins):
        low = profile.low + k * step
        inside = profile.val <= low + step / 2 <= profile.vah
        overlay.boxes.append((start, low, start + (end - start) * 0.9 * v / top, low + step, "zblue" if inside else "zred"))
    return candle_svg(candles[i0:i1 + 1], overlay, i0, date="%d.%m %H:%M")


def sketches() -> str:
    cards = [
        card("SFP + MSB + retest (PR-60): dersteki short", None,
             svg([90500, 94100, 93300, 94789, 93900, 94400, 91265, 93506, 91306], ["", "", "büyük dip", "SFP", "", "", "0", "giriş", "hedef"],
                 [(94930.8, "stop 94.931", RED), (93300, "MSB", RED), (93506, "0,618–0,66", AMBER)]),
             [90500, 94100, 93300, 94789, 93900, 94400, 91265, 93506, 91306],
             "Aykut'un gönderdiği görüntüdeki sayılar: 1 = 94.789, 0 = 91.265, giriş 93.506 (0,636), stop tepenin 142 üstünde "
             "(hareketin %4'ü), hedef 91.306. R/R 1,54. Ara noktalar şematik; süpürülen HTF tepe 94.589."),
        sketch("FVG dolum durumları (PR-30)", [(50, 53, 49, 52), (52, 64, 51.5, 63), (63, 66, 61, 65), (65, 66, 60, 62), (62, 63, 56.5, 60), (60, 66, 59, 65), (65, 66, 52, 54)],
               Overlay(boxes=[(1, 53, 6, 61, "zgreen")], lines=[(1, 57, 6, 57, "lgray", "%50")], marks=[(3, 60, "kısmi", "down"), (4, 56.5, "%50", "down"), (6, 52, "tam doldu", "down")]),
               "Kısmi dolum → tepki yeri %50. Tam dolunca bölge zayıflar."),
        card("Klasik uyumsuzluk (PR-20)", None, svg([90, 60, 78, 52, 80], ["", "LL-1", "", "LL-2 · RSI yükseliyor", ""], []), [90, 60, 78, 52, 80],
             "P.U: fiyat daha düşük dip, RSI daha yüksek dip → dönüş uyarısı. N.U tersi. Trend devam (gizli): fiyat HL, RSI LL."),
        card("CME gap (PR-50)", None, svg([60, 64, 78, 70, 82, 64, 76], ["", "Cuma kapanış", "Pazar açılış", "", "", "dolum", ""], [(64, "gap alt", AMBER), (78, "gap üst", AMBER)]),
             [60, 64, 78, 70, 82, 64, 76], "Cuma kapanışı ile Pazar açılışı arası. <b>29 Mayıs 2026'dan beri CME 7/24: yeni gap oluşmuyor.</b>"),
    ]
    return section("1. Kural çizimleri (kendi sayılarımız)", cards)


def divergence_figure(title: str, candles: list[Candle], values: Sequence[float | None], d, name: str, levels: Sequence[float] = (), note: str = "") -> str:
    i0, i1 = max(0, d.previous_index - 12), min(len(candles) - 1, d.confirmed_at + 25)
    bull = d.kind in (REGULAR_BULLISH, HIDDEN_BULLISH)
    over = Overlay(lines=[(d.previous_index, d.previous_price, d.pivot_index, d.price, "lgreen" if bull else "lred", "")],
                   marks=[(d.previous_index, d.previous_price, "1", "down" if bull else "up"), (d.pivot_index, d.price, "2", "down" if bull else "up"),
                          (d.confirmed_at, candles[d.confirmed_at].close, "kesinleşme", "up" if bull else "down")])
    top = candle_svg(candles[i0:i1 + 1], over, i0)
    low = panel(values[i0:i1 + 1], name, [(d.previous_index - i0, d.previous_value), (d.pivot_index - i0, d.value)], levels)
    return figure(title, top + low, note)


def real() -> str:
    hour, four, day = (load_series("BTCUSDT", tf).candles for tf in ("1h", "4h", "1d"))
    quarter = load_series("BTCUSDT", "15m").candles
    out = []
    # volume profile of the last complete week, 1h candles
    week = [p for p in pr.session_profiles(hour, 7) if p.end <= hour[-1].time][-2]
    i0 = next(i for i, c in enumerate(hour) if c.time >= week.start) - 12
    i1 = min(len(hour) - 1, i0 + 12 + 24 * 11)
    out.append(figure(f"Hacim profili — BTC 1h, {week.start:%d.%m} haftası", profile_svg(hour, i0, i1, week, Overlay(
        lines=[(i0 + 12, week.poc, i1, week.poc, "lred", "POC"), (i0 + 12, week.vah, i1, week.vah, "lblue", "VAH"), (i0 + 12, week.val, i1, week.val, "lblue", "VAL")])),
        "Mavi: hacmin %70'inin olduğu değer alanı. POC en çok işlem gören fiyat. Seviyeler hafta bitince kesinleşir."))
    # daily POC that stayed naked for at least two days and was touched later
    daily = pr.session_profiles(quarter, 1)
    p = next(p for p in reversed(daily) if (t := pr.poc_touch(hour, p)) is not None and timedelta(days=2) <= hour[t].time - p.end <= timedelta(days=9))
    t = pr.poc_touch(hour, p)
    i0 = next(i for i, c in enumerate(hour) if c.time >= p.start) - 12
    i1 = min(len(hour) - 1, t + 24)
    out.append(figure(f"NPOC — BTC 1h, {p.start:%d.%m.%Y} gününün POC'u", profile_svg(hour, i0, i1, p, Overlay(
        lines=[(i0 + 12, p.poc, t, p.poc, "lred", "")], marks=[(t, p.poc, "ilk dokunuş", "up")])),
        f"{(hour[t].time - p.end).days} gün dokunulmadan kaldı (naked), sonra dokunuldu."))
    r4, c1 = rsi([c.close for c in four]), cvd(hour)
    for kind, name in ((REGULAR_BULLISH, "P.U"), (REGULAR_BEARISH, "N.U")):
        d = [d for d in rsi_divergences(four) if d.kind == kind and d.confirmed_at + 10 < len(four)][-1]
        out.append(divergence_figure(f"RSI {name} — BTC 4h", four, r4, d, "RSI 14", (30, 50, 70), "SERS41 RSI mantığı; etiket pivottan 5 mum sonra kesinleşir."))
    d = [d for d in cvd_divergences(hour) if d.kind == REGULAR_BEARISH and d.confirmed_at + 10 < len(hour)][-1]
    out.append(divergence_figure("CVD negatif uyumsuzluk — BTC 1h", hour, c1, d, "CVD (Binance spot)", (), "Fiyat daha yüksek tepe, birikimli alım-satım farkı daha düşük."))
    i, way = [a for a in pr.absorption(hour) if a[0] + 30 < len(hour)][-1]
    i0, i1 = i - 30, i + 30
    out.append(figure("Emilim — BTC 1h", candle_svg(hour[i0:i1 + 1], Overlay(boxes=[(i - 11, min(c.low for c in hour[i - 11:i + 1]), i, max(c.high for c in hour[i - 11:i + 1]), "zgreen" if way == UP else "zred")]), i0, date="%d.%m %H:%M")
                      + panel(c1[i0:i1 + 1], "CVD"), f"12 mumda fiyat neredeyse yerinde, delta olağanın 2+ katı. Beklenen yön: {'yukarı (satış emildi)' if way == UP else 'aşağı (alış emildi)'}."))
    z = [z for z in sm.fair_value_gaps(day, 0.4) if z.known_at + 15 < len(day) and pr.fill_state(day, z, z.known_at + 15) == pr.HALF][-1]
    i0, i1 = z.index - 12, min(len(day) - 1, z.known_at + 20)
    out.append(figure("FVG: %50 dolum — BTC 1d", candle_svg(day[i0:i1 + 1], Overlay(boxes=[(z.index, z.low, i1, z.high, "zgreen" if z.direction == UP else "zred")],
                      lines=[(z.index, z.mid, i1, z.mid, "lgray", "%50")]), i0), "15 mum içinde %50'ye ulaştı, tam dolmadı."))
    lows = structure_breaks(quarter, zigzag(quarter, multiple=2))
    for htf, span, tf in ((day, timedelta(days=1), "1d"), (four, timedelta(hours=4), "4h")):
        plans = [x for x in pr.sfp_msb_plans(htf, span, find_open_sfps(htf), quarter, lows) if x.touch + 100 < len(quarter)]
        lesson = [x for x in plans if tf == "1d" and f"{quarter[x.touch].time:%Y-%m-%d}" == "2026-01-06"]
        for x, name in [(plans[-1], "en yeni")] + ([(lesson[0], "dersteki işlem, Ocak 2026")] if lesson else []):
            begin = next(i for i, c in enumerate(quarter) if c.time >= htf[x.sfp.sweep_index].time)
            i0, i1 = max(0, begin - 60), min(len(quarter) - 1, x.touch + 220)
            up = x.sfp.direction == BULLISH
            low, high = sorted(x.end + r * (x.origin - x.end) for r in pr.RETEST)
            over = Overlay(boxes=[(begin, low, i1, high, "zgreen" if up else "zred")],
                           lines=[(i0, x.sfp.level, x.touch, x.sfp.level, "lamber", "süpürülen seviye"),
                                  (x.msb.level_index, x.msb.level, x.msb.index, x.msb.level, "lgreen" if up else "lred", "MSB"),
                                  (x.touch, x.stop, i1, x.stop, "lred", "stop"), (x.touch, x.end, i1, x.end, "lgreen", "hedef 0"),
                                  (begin, x.origin, i1, x.origin, "lgray", "1")],
                           marks=[(x.touch, x.entry, "giriş", "up" if up else "down")])
            out.append(figure(f"SFP {tf} → MSB 15m → 0,618–0,66 — BTC ({name})", candle_svg(quarter[i0:i1 + 1], over, i0, date="%d.%m %H:%M"),
                              f"R/R {x.risk_reward:.2f}. Stop SFP ucunun, hareketin %4'ü kadar ötesinde; hedef hareketin 0'ı."))
    gap = next(g for g in reversed(pr.weekend_gaps(hour)))
    filled = pr.gap_filled_at(hour, gap)
    i0, i1 = gap.open_index - 60, min(len(hour) - 1, (filled or gap.open_index) + 40)
    i1 = min(i1, gap.open_index + 24 * 12)
    low, high = min(gap.close, gap.open), max(gap.close, gap.open)
    out.append(figure(f"Son CME gap'lerinden biri — {gap.open_time:%d.%m.%Y}", candle_svg(hour[i0:i1 + 1], Overlay(boxes=[(gap.open_index, low, i1, high, "zblue")]), i0),
                      "Spot fiyatla yaklaşık (Cuma 16:00 – Pazar 17:00 Chicago). " + (f"Dolum: {hour[filled].time:%d.%m.%Y}." if filled else "Dolmadı.")))
    oi = load("oi_1h")
    at = dict(oi)
    i0, i1 = len(four) - 180, len(four) - 1
    values = [at.get(c.time + timedelta(hours=4)) for c in four[i0:i1 + 1]]
    fund = load("funding")
    k, last, rates = 0, None, []
    for c in four[i0:i1 + 1]:
        while k < len(fund) and fund[k][0] <= c.time + timedelta(hours=4):
            last = fund[k][1]
            k += 1
        rates.append(None if last is None else last * 100)
    out.append(figure("Open interest ve funding — BTC 4h (son 30 gün)", candle_svg(four[i0:i1 + 1], Overlay(), i0) + panel(values, "Open interest (BTC)") + panel(rates, "Funding %", levels=(0.0, 0.05, -0.05)),
                      "OI↑ fiyat↓ yeni short, OI↓ fiyat↓ long kapanışı (SM-95). Funding ayın dosyası çıkana kadar son bilinen değerde kalır."))
    return section("2. Aynı kurallar gerçek grafikte (en yeni örnekler)", out)


def handbook() -> str:
    lead = ("Üstte kuralın çizimi, altta aynı kuralın kendi verimizde bulunmuş hali. Uyuşmuyorsa kuralı yanlış anlamışım demektir: doğru görseli at, "
            "düzelteyim. Numaralar PROFESSIONAL.md'deki kurallardır.")
    return page("Profesyonel kural görselleri", sketches() + real(), lead).replace("</style>", CHART_CSS + "</style>")


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    path = HERE / "pro-visuals.html"
    path.write_text(handbook(), encoding="utf-8")
    print(path)


if __name__ == "__main__":
    main()
