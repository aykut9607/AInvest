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
        card("Haber pivotu (BK-70)", None, svg([70, 76, 72, 96, 88, 94, 78, 92], ["", "", "son fiyat", "haber", "", "", "pivot tuttu", ""], [(74, "pivot", RED), (90, "boşluk ucu", AMBER)]),
             [70, 76, 72, 96, 88, 94, 78, 92], "Haberden önceki son fiyat referanstır. Fiyat oraya dönüp tutunursa haber geçerli; altına geçerse piyasa haberi reddetti."),
        card("Yuvarlak sayı ve stop (BK-76)", None, svg([112, 104, 110, 100.5, 108, 118], ["", "", "giriş", "kalabalığın stopu", "", ""], [(100, "100", AMBER), (96, "bizim stop", RED)]),
             [112, 104, 110, 100.5, 108, 118], "Long stopu 100'ün hemen üstünde değil, altında ve en az bir günlük aralık uzakta."),
        card("Sıkışma kırılımı ve stop (BK-101, BK-131)", None, svg([100, 109, 101, 110, 102, 116, 111, 126], ["", "", "", "", "", "kırılım", "ekleme: kârda", ""], [(110, "aralık üstü", AMBER), (99, "stop: aralık dışı", RED)]),
             [100, 109, 101, 110, 102, 116, 111, 126], "Dar aralıkta işlem yok; kapanışla kırılınca küçük giriş, kâra geçtikçe ekleme. Stop aralığın ortasında değil dışında."),
        card("Sapan dönüşü (BK-74, BK-180)", None, svg([100, 84, 96, 85, 94, 79, 92, 104], ["", "dip", "", "dip", "", "sahte", "giriş", ""], [(84, "herkesin izlediği seviye", AMBER), (77, "stop", RED)]),
             [100, 84, 96, 85, 94, 79, 92, 104], "Çok izlenen seviye kırılır, fiyat hemen geri alınır: kırılıma satanlar ters yönde kapatmak zorunda kalır. Bizdeki SFP ile aynı."),
        card("Yorulan destek (BK-72)", None, svg([80, 110, 92, 106, 92, 100, 92, 80], ["", "", "destek", "zayıf", "", "daha zayıf", "", "kırılım"], [(91, "destek", RED)]),
             [80, 110, 92, 106, 92, 100, 92, 80], "Her sıçrama öncekinden zayıf: alıcı azalıyor. Sonraki kırılım trendin yorulduğunu gösterir."),
        card("Stop gürültünün dışında (BK-75, BK-145)", None, svg([100, 112, 104, 110, 103, 120], ["", "", "giriş", "", "gürültü", ""], [(101, "yakın stop: vurulur", AMBER), (94, "1 günlük aralık uzakta", RED)]),
             [100, 112, 104, 110, 103, 120], "Stop en az bir ortalama günlük aralık uzakta. Mesafe uzarsa miktar küçülür, risk tutarı aynı kalır."),
        card("Simetri (BK-77)", None, svg([70, 80, 90, 100, 90, 80, 70], ["başlangıç", "", "", "tepe", "", "", "aynı süre"], []),
             [70, 80, 90, 100, 90, 80, 70], "Çıkış kaç mum sürdüyse iniş de o kadar: hem fiyat hem süre. Tek başına sebep sayılmaz."),
        card("Deneme ve piramit (BK-102)", None, svg([90, 100, 96, 108, 103, 118, 113, 126], ["", "1", "", "2", "", "3", "", ""], [(94, "ilk stop", RED)]),
             [90, 100, 96, 108, 103, 118, 113, 126], "Küçük ilk alım; yalnız kâra geçtikçe, azalarak eklenir. Kâra geçmiyorsa çıkılır."),
        card("Üç gün kuralı (BK-120)", None, svg([110, 98, 103, 96, 101, 94, 97, 88], ["", "", "", "", "", "1", "2", "3: kesin"], [(99, "kırılan çizgi", RED)]),
             [110, 98, 103, 96, 101, 94, 97, 88], "Çizginin ötesinde 2–3 gün kapanış kırılımı kesinleştirir; daha azı yanlış sinyal olabilir."),
        card("Aralığa geri dönen kırılım (BK-168)", None, svg([100, 110, 101, 110, 102, 116, 108, 101], ["", "", "", "", "", "kırılım", "yarısı çıkar", ""], [(110, "aralık üstü", AMBER), (100, "aralık altı", AMBER)]),
             [100, 110, 101, 110, 102, 116, 108, 101], "Kırılan aralığın içine dönen fiyatta en az yarısı satılır; fiyat genelde öbür uca kadar gider."),
        card("Geniş tabandan yeni yüksek (BK-163)", None, svg([60, 100, 82, 98, 86, 99, 90, 108], ["", "", "taban", "", "", "", "", "giriş"], [(100, "eski yüksek", AMBER), (110, "tabandan %10: geç", RED)]),
             [60, 100, 82, 98, 86, 99, 90, 108], "Dip değil, tabandan yeni yükseğe çıkış alınır; tabandan %10 uzaklaşmışsa alınmaz."),
        card("Başarısız taban ve short (BK-167)", None, svg([70, 100, 90, 108, 92, 99, 80, 89, 68], ["", "", "", "başarısız", "", "", "taban altı", "short", ""], [(90, "taban", RED)]),
             [70, 100, 90, 108, 92, 99, 80, 89, 68], "Geç tabandan çıkış tutmadı; tabanın altına hacimle indi; tabana ilk dönüş short yeri."),
        card("Oynaklık kırılımı (BK-152)", None, svg([100, 103, 100.5, 102.5, 101, 102.2, 101.2, 112], ["", "", "", "", "", "daralma", "", "kırılım"], [(103, "dar aralık", AMBER)]),
             [100, 103, 100.5, 102.5, 101, 102.2, 101.2, 112], "Aralık giderek daralır; birden genişlediği yönde girilir."),
        card("Ölçülü hareket (BK-42, BK-153)", None, svg([100, 110, 101, 110, 100, 120], ["", "", "", "", "", ""], [(110, "aralık üstü", AMBER), (120, "hedef: + aralık yüksekliği", AMBER), (99, "stop", RED)]),
             [100, 110, 101, 110, 100, 120], "Aralık 100–110 ise kırılım hedefi 120: yükseklik kadar."),
        card("Zaman stopu (BK-150)", None, svg([90, 100, 98, 101, 98.5, 100.5, 98.8, 100], ["", "giriş", "", "", "", "", "", "2 hafta: çık"], [(94, "fiyat stopu (vurulmadı)", RED)]),
             [90, 100, 98, 101, 98.5, 100.5, 98.8, 100], "Beklenen hareket gelmiyorsa fiyat stopu vurulmasa da çıkılır."),
        card("Taban kırılana kadar tut (BK-170)", None, svg([60, 84, 78, 100, 92, 110, 101, 109, 96], ["giriş", "", "taban", "", "taban", "", "son taban", "", "kırıldı: çık"], [(101, "son taban", RED)]),
             [60, 84, 78, 100, 92, 110, 101, 109, 96], "Hedef fiyat yok; son tabanın altına inince çıkılır."),
        card("Önceki osilatör tepesi (BK-173)", None, svg([70, 100, 92, 104, 86, 72], ["başlangıç", "osilatör tepesi", "", "fiyat tepesi", "", "bitiş"], []),
             [70, 100, 92, 104, 86, 72], "Süre fiyat tepesinden değil, ondan önceki osilatör tepesinden sayılır (M-tepe)."),
        card("Yuvarlak sayı ivmesi (BK-194)", None, svg([80, 90, 86, 98, 102, 118, 112, 132], ["", "", "", "", "giriş", "", "", ""], [(100, "100", AMBER)]),
             [80, 90, 86, 98, 102, 118, 112, 132], "Yuvarlak sayı ilk kez aşılınca hareket hızlanır; hemen devam etmezse çıkılır."),
        card("Yuvarlak sayıda başarısız ivme (BK-194)", None, svg([270, 290, 284, 303, 292, 298, 302.75, 296], ["", "", "", "giriş", "", "", "devam etmedi", "çık"], [(300, "300", AMBER)]),
             [270, 290, 284, 303, 292, 298, 302.75, 296], "Seviye aşıldı ama hızla ilerlemedi ve geri dönüyor: plan bozuldu, hemen çıkılır."),
        card("Aralıkta işlem yok (BK-191)", None, svg([1.1, 1.18, 1.11, 1.19, 1.12, 1.195, 1.22, 1.25], ["", "", "", "", "", "", "giriş", ""], [(1.2, "üst sınır", AMBER), (1.1, "alt sınır", AMBER)]),
             [1.1, 1.18, 1.11, 1.19, 1.12, 1.195, 1.22, 1.25], "1,10–1,20 arasında yön tahmin edilmez; 1,20 aşılınca alınır."),
        card("Boğa sonu: önder geri çıkamaz (BK-197)", None, svg([70, 90, 84, 104, 98, 112, 100, 106, 99, 104], ["", "", "", "", "", "son tepe", "ilk düşüş", "çıkamadı", "", ""], [(112, "eski tepe", RED)]),
             [70, 90, 84, 104, 98, 112, 100, 106, 99, 104], "Önder, ilk kez birkaç puan düşüp eski tepesine dönemez; piyasanın kalanı henüz dönmemiş olabilir."),
        card("Baz pozisyon ve düzeltme (BK-186)", None, svg([90, 102, 98, 110, 103, 120, 113, 130], ["", "baz", "", "", "ekle", "", "", ""], [(95, "stop", RED)]),
             [90, 102, 98, 110, 103, 120, 113, 130], "Tamamı kapatılmaz: baz tutulur, düzeltmede eklenir; düzeltme gelmese de hareket kaçmaz."),
        card("Dönüş günü (BK-189)", None, svg([90, 96, 94, 101, 99, 106, 92, 88], ["", "", "", "", "önceki kapanış", "yeni yüksek", "gün kapanışı", ""], [(99, "önceki kapanış", AMBER)]),
             [90, 96, 94, 101, 99, 106, 92, 88], "Gün içinde yeni yüksek yapılır ama gün, önceki kapanışın altında biter."),
        card("Stop ve hedef yerleşimi (BK-212)", None, svg([116, 119, 117, 119.1, 117.5, 118.6, 115, 117, 112], ["", "tepe", "", "tepe", "", "giriş", "", "", "hedef"], [(119.6, "stop: tepeler ve 119,5 üstü", RED), (111.5, "büyük destek", AMBER)]),
             [116, 119, 117, 119.1, 117.5, 118.6, 115, 117, 112], "Stop tepelerin ve yuvarlak sayının ötesinde, hedef desteğe varmadan."),
        card("Rejim testi: 20 günlük zirve (BK-206)", None, svg([90, 100, 93, 99, 94, 104, 100, 110], ["", "eski zirve", "", "", "", "yeni zirve", "", "trend"], [(100, "20 günlük zirve", AMBER)]),
             [90, 100, 93, 99, 94, 104, 100, 110], "Son 10 günde yeni 20 günlük zirve varsa trend; yoksa aralık sayılır."),
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


def deviation_figure() -> str:
    cs = load_series("BTCUSDT", "1h").candles
    closes = [c.close for c in cs]
    mean, run = [None] * len(cs), sum(closes[:100])
    for i in range(100, len(cs)):
        mean[i] = run / 100
        run += closes[i] - closes[i - 100]
    dev = [None if m is None else c / m - 1 for c, m in zip(closes, mean)]
    i0 = len(cs) - 500
    past = sorted(v for v in dev[:i0] if v is not None)
    k = int(0.05 * len(past))
    low, high = past[k], past[-k - 1]
    marks, last = [], None
    for i in range(i0, len(cs)):
        side = "up" if dev[i] > high else "down" if dev[i] < low else None
        if side and side != last:
            marks.append((i, cs[i].close, "uç", side))
        last = side
    return figure("100 saatlik ortalamadan sapma, en uç %5 — BTC 1h", candle_svg(cs[i0:], Overlay(lines=curve(mean[i0:], i0, "lamber", "ort. 100"), marks=marks), i0, date="%d.%m"),
                  f"BK-81. Sınırlar yalnız bu pencereden önceki veriden: %{100 * low:.1f} ve %{100 * high:.1f}. Son 500 saat.")


def handbook() -> str:
    lead = "Kitaplardan çıkan kurallar (book data). Numaralar BOOKS.md'deki kurallardır; kitapların metni ya da görselleri kopyalanmadı."
    real = [vwap_figure(), break_figure(), ema_figure(), deviation_figure()]
    return page("Kitap kuralları", sketches() + section("2. Aynı kurallar gerçek grafikte", real), lead).replace("</style>", CHART_CSS + "</style>")


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    path = HERE / "book-visuals.html"
    path.write_text(handbook(), encoding="utf-8")
    print(path)


if __name__ == "__main__":
    main()
