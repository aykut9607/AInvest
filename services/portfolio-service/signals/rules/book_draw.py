"""Pictures for BOOKS.md: sketches with our own numbers and the same rules on our data.

  .\\venv\\Scripts\\python.exe -m signals.rules.book_draw        rebuild book-visuals.html
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

from signals.data.candles import load_series
from signals.rules import book_detect as bk
from signals.rules.chart import CHART_CSS, Overlay, candle_svg
from signals.rules.elliott_draw import AMBER, RED, card, page, section, svg
from signals.rules.pa_draw import figure
from signals.rules.smc_detect import sessions
from signals.structure.pivots import HIGH
from signals.structure.zigzag import zigzag

HERE = Path(__file__).parent


def curve(values, first, cls, label=""):
    """Polyline as segments; `values` may contain None."""
    seg = [(first + i, a, first + i + 1, b, cls, "") for i, (a, b) in enumerate(zip(values, values[1:])) if a is not None and b is not None]
    return seg[:-1] + [(*seg[-1][:5], label)] if seg else []


def sketches() -> str:
    cards = [
        card("VWAP iki yarıya böler (BK-02…05)", None, svg([80, 92, 83, 96, 88, 110, 100, 85], ["", "", "dönüş", "", "", "uzak: dönüş aranır", "", "kâr al"], [(78, "VWAP", AMBER), (90, "+1 sapma", RED)]),
             [80, 92, 83, 96, 88, 110, 100, 85], "VWAP üstünde long, altında short aranır; VWAP'a yakınken işlem yok, kesişim işlemi yok. Uzakta (≥ 1 sapma) VWAP'a dönüş işlemi: hedef VWAP'a varmadan, en az 2R yer olmalı."),
        card("Kırılım hacmi (BK-25)", None, svg([70, 89, 78, 90, 80, 98, 91, 108], ["", "", "", "", "", "kırılım: hacim ↑", "tereddüt: hacim ↓", ""], [(90, "direnç", RED)]),
             [70, 89, 78, 90, 80, 98, 91, 108], "Yüksek hacimle kırıp düşük hacimle seviyeye dönerse gerçek; tersi (düşük hacimle kırıp artan hacimle dönüş) boğa tuzağı."),
        card("Elliott osilatörü (BK-27)", None, svg([60, 72, 65, 98, 84, 106], ["0", "1", "2", "3: en yüksek", "4: sıfıra", "5: düşük"], []),
             [60, 72, 65, 98, 84, 106], "EMA5 − EMA35. 3. dalganın tepesi 5. dalganınkinden yüksek olmalı (E- listesindeki uyumsuzlukla aynı fikir)."),
        card("Zigzag oranları (BK-28)", None, svg([100, 70, 85, 55], ["5", "A", "B ≤ %75", "C = A"], [(92.5, "B sınırı %75", RED)]),
             [100, 70, 85, 55], "B genelde A'nın %50'si, en çok %75'i; C = 1, 1,62 ya da 2,62 × A."),
    ]
    return section("1. Kural çizimleri (kendi sayılarımız)", cards)


def vwap_figure() -> str:
    cs = load_series("BTCUSDT", "15m").candles
    last = max(i for i, c in enumerate(cs) if c.time.hour == 23 and c.time.minute == 45 and c.time.weekday() < 5)
    i0 = last - 95
    rows = bk.session_vwap(cs[i0:last + 1])
    lines = curve([r.value for r in rows], i0, "lamber", "VWAP")
    for k, name in ((1, "+1σ"), (-1, "−1σ"), (2, "+2σ"), (-2, "−2σ")):
        lines += curve([r.value + k * r.deviation for r in rows], i0, "lblue" if abs(k) == 1 else "lgray", name)
    day = cs[i0].time
    us = sessions(datetime(day.year, day.month, day.day, tzinfo=timezone.utc))["new york"][0]
    k = next(i for i in range(i0, last + 1) if cs[i].time >= us)
    low, high = bk.opening_range(cs[i0:last + 1], day)
    return figure(f"Günlük VWAP ve sapma bantları — BTC 15m, {day:%d.%m.%Y} (UTC)", candle_svg(cs[i0:last + 1], Overlay(lines=lines, boxes=[(k, low, k + 3, high, "zgreen")]), i0, date="%H:%M"),
                  "Sarı VWAP, mavi ±1 sapma, gri ±2 sapma; yeşil kutu ABD açılışının ilk saati (BK-10). Verideki son tam hafta içi gün, seçilmedi.")


def ema_figure() -> str:
    cs = load_series("BTCUSDT", "1w").candles
    e = bk.ema([c.close for c in cs], 21)
    i0 = len(cs) - 120
    return figure("21 haftalık EMA — BTC 1w", candle_svg(cs[i0:], Overlay(lines=curve(e[i0:], i0, "lamber", "EMA 21")), i0),
                  "BK-22: haftalık kapanış üstüne çıkınca al, altına inince sat. Son 120 hafta.")


def break_figure() -> str:
    cs = load_series("BTCUSDT", "1d").candles
    found = None
    for p in (p for p in zigzag(cs, multiple=3.0) if p.kind == HIGH):
        b = next((i for i in range(p.confirmed_at + 1, len(cs)) if cs[i].close > p.price), None)
        if b is None or b - p.index < 15:
            continue
        r = next((i for i in range(b + 2, min(len(cs), b + 25)) if cs[i].low <= p.price * 1.005), None)
        if r is not None and r + 15 < len(cs) and b - p.index < 150 and bk.volume_confirms(cs, b, r):
            found = (p, b, r)
    p, b, r = found
    i0, i1 = p.index - 10, min(len(cs) - 1, r + 25)
    return figure(f"Hacimli kırılım ve düşük hacimli dönüş — BTC 1d, {cs[b].time:%d.%m.%Y}", candle_svg(cs[i0:i1 + 1], Overlay(
        lines=[(p.index, p.price, i1, p.price, "lred", "direnç")], marks=[(b, cs[b].close, "kırılım: hacim ↑", "up"), (r, cs[r].low, "dönüş: hacim ↓", "down")]), i0),
        "En yeni örnek. Sonucuna bakılarak seçilmedi; kuralın tuttuğu anlamına gelmez.")


def handbook() -> str:
    lead = "Kitaplardan çıkan kurallar (book data). Numaralar BOOKS.md'deki kurallardır; kitapların metni ya da görselleri kopyalanmadı."
    real = [vwap_figure(), break_figure(), ema_figure()]
    return page("Kitap kuralları", sketches() + section("2. Aynı kurallar gerçek grafikte", real), lead).replace("</style>", CHART_CSS + "</style>")


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    path = HERE / "book-visuals.html"
    path.write_text(handbook(), encoding="utf-8")
    print(path)


if __name__ == "__main__":
    main()
