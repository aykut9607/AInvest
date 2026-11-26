"""Pictures for MENTOR_VIEW.md (glossary, training panel, mentors): sketches and our own data.

  .\\venv\\Scripts\\python.exe -m signals.rules.mentor_draw        rebuild mentor-visuals.html
"""

from __future__ import annotations

import sys
from datetime import timedelta
from pathlib import Path

from signals.data.candles import load_series
from signals.rules import ext_detect as ext
from signals.rules.chart import CHART_CSS, Overlay, candle_svg
from signals.rules.elliott_draw import AMBER, RED, card, page, section, svg
from signals.rules.pa_draw import figure
from signals.rules.smc_draw import sketch
from signals.structure.pivots import HIGH

HERE = Path(__file__).parent


def sketches() -> str:
    cards = [
        sketch("Gerçek kırılım ve sahte kırılım (MB-01)", [(50, 58, 49, 57), (57, 60, 54, 55), (55, 62, 54, 58), (58, 59, 53, 54), (54, 64, 53.5, 63), (63, 65, 60, 64)],
               Overlay(lines=[(1, 60, 5, 60, "lred", "")], marks=[(2, 62, "fitil: sahte", "up"), (4, 64, "gövde: gerçek", "up")]),
               "Çizgi önceki tepenin <b>fitil ucundan</b>. Yeni mumun <b>gövdesi</b> keserse (üstünde kapanırsa) kırılım; yalnız fitil keserse sahte / sweep."),
        card("MSB ve CHoCH (MB-02)", None, svg([100, 78, 90, 66, 76, 70, 82, 74, 94], ["", "", "büyük LH", "LL", "küçük LH", "", "CHoCH", "", "MSB"], [(90, "kırılırsa MSB", RED), (76, "kırılırsa CHoCH", AMBER)]),
             [100, 78, 90, 66, 76, 70, 82, 74, 94], "Sözlük: CHoCH iki swing arasında, son büyük tepe kırılmadan olan iç dönüş. LTF'de MSB olan şey HTF'de yalnız CHoCH olabilir."),
        card("Premium / discount / EQ (MB-04)", None, svg([60, 100, 60, 95, 68, 88], ["", "RH", "RL", "short aranır", "long aranır", "EQ'da kâr"], [(100, "RH", AMBER), (80, "EQ: işlem yok", RED), (60, "RL", AMBER)]),
             [60, 100, 60, 95, 68, 88], "EQ üstü pahalı yarı (short), altı ucuz yarı (long). EQ giriş yeri değil, kâr alma yeri."),
        card("EXT bandı: süpürme ve gerçek kırılım (MB-20)", None, svg([62, 80, 70, 83, 74, 79, 86, 88], ["", "tepe", "", "süpürme", "içeri", "", "kırılım", ""], [(80, "tepe", AMBER), (82.3, "1,114", RED), (84.3, "1,214", RED)]),
             [62, 80, 70, 83, 74, 79, 86, 88], "Bant = menzilin %11,4–21,4 ötesi. Bandı görüp içeri kapanış süpürme, bandın ötesinde kapanış gerçek kırılım. (Ölçüler şematik.)"),
        card("Giriş sırası (MB-05)", None, svg([70, 90, 76, 96, 72, 84, 78, 100], ["", "", "likidite", "", "sweep", "MSB", "retest = giriş", "hedef"], [(76, "süpürülen dip", RED)]),
             [70, 90, 76, 96, 72, 84, 78, 100], "Likidite → sweep → MSB → retest → giriş (PR-60 ile aynı)."),
    ]
    return section("1. Kural çizimleri (kendi sayılarımız)", cards)


def ext_figure(kind: str, want: str, tf: str) -> str:
    daily, cs = load_series("BTCUSDT", "1d").candles, load_series("BTCUSDT", tf).candles
    e = [e for e in ext.ext_events(cs, ext.reference_ranges(daily, kind)) if e.kind == want and e.index + 12 < len(cs)][-1]
    r = e.range
    start = next(i for i, c in enumerate(cs) if c.time >= r.known - (timedelta(days=1) if kind == "Pazartesi" else timedelta(days=7)))
    known = next(i for i, c in enumerate(cs) if c.time >= r.known)
    i1 = min(len(cs) - 1, e.index + 40)
    over = Overlay(lines=[(start, r.high, i1, r.high, "lblue", f"{kind} yüksek"), (start, r.low, i1, r.low, "lblue", f"{kind} düşük"),
                          (known, (r.high + r.low) / 2, i1, (r.high + r.low) / 2, "lgray", "0,5")],
                   boxes=[(start, r.low, known, r.high, "zblue"), (known, *(lambda b: (b[0], i1, b[1]))(r.band(e.side)), "zred" if e.side == HIGH else "zgreen")],
                   marks=[(e.index, cs[e.index].close, want, "up" if e.side == HIGH else "down")])
    return figure(f"{kind} EXT bandı, {want} — BTC {tf}", candle_svg(cs[start:i1 + 1], over, start, date="%d.%m %H:%M"),
                  f"Mavi kutu menzilin oluştuğu dönem; bant {r.band(e.side)[0]:,.0f}–{r.band(e.side)[1]:,.0f}. En yeni örnek.")


def chaos_figure() -> str:
    cs = load_series("BTCUSDT", "4h").candles
    best = None
    for i in range(60, len(cs) - 12):
        c, span = cs[i], cs[i].high - cs[i].low
        usual = sum(x.high - x.low for x in cs[i - 50:i]) / 50
        volume = sum(x.volume for x in cs[i - 50:i]) / 50
        if span > 3 * usual and abs(c.close - c.open) < 0.25 * span and c.volume > 2 * volume:
            best = i
    i0, i1 = best - 40, best + 12
    return figure("Kaos fitili — BTC 4h (en yeni)", candle_svg(cs[i0:min(len(cs), i1 + 1)], Overlay(marks=[(best, cs[best].low, "kaos fitili", "down")]), i0),
                  "Mum boyu olağanın 3 katından büyük, gövde boyun %25'inden küçük, hacim 2 katından fazla (sayılar benim tanımım).")


def handbook() -> str:
    real = [ext_figure("Pazartesi", ext.SWEEP, "1h"), ext_figure("Pazartesi", ext.BREAK, "1h"), ext_figure("Hafta", ext.SWEEP, "4h"),
            ext_figure("Hafta", ext.BREAK, "4h"), chaos_figure()]
    lead = "Sözlük, gösterge paneli ve mentor videolarından çıkan kurallar. Numaralar MENTOR_VIEW.md'deki kurallardır. Örnekler en yeni olana göre seçildi."
    return page("Mentor bakışı kural görselleri", sketches() + section("2. Aynı kurallar gerçek grafikte", real), lead).replace("</style>", CHART_CSS + "</style>")


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    path = HERE / "mentor-visuals.html"
    path.write_text(handbook(), encoding="utf-8")
    print(path)


if __name__ == "__main__":
    main()
