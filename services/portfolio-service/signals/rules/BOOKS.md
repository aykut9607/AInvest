# Book data: kitaplardan çıkan kurallar (v1, 24 Kasım 2026)

Ayrı kategori; **hiçbiri ölçülmedi**, backtest sonra. Fikirler kendi cümlelerimizle; kitap metni ve görseli kopyalanmadı.
Görseller: [book-visuals.html](book-visuals.html). Kod: `book_detect.py`.
**Tür:** T = testi yapılabilir grafik kuralı · F = filtre · D = davranış/risk. **Ö** = sayı bizim, kitapta yok.

## 1. VWAP (Terence V. Gronowski, *The VWAP Strategy*, 2019)
| No | Tür | Kural |
|---|---|---|
| BK-01 | T | VWAP = Σ(fiyat × hacim) / Σ hacim, her gün 00:00'da başlar; **çizgi değil bölge**. Başlangıç saati sonucu değiştirir (bizde 00:00 UTC, Ö; kitap Avrupa gece yarısı ve ABD gece yarısı) |
| BK-02 | F | VWAP **sinyal vermez**, yön filtresidir: üstünde long, altında short aranır |
| BK-03 | F | VWAP'a yakınken işlem yok; fiyat–VWAP kesişimi işlem sebebi değil (tuzak bölgesi). Yakın = 0,5 sapma (Ö) |
| BK-04 | T | Ters yön yalnız **en az 1, tercihen 2 standart sapma** uzaktayken ve 5m'de çift tepe/dip + yeni trend oluşunca |
| BK-05 | T | VWAP'a doğru işlemde hedef VWAP'a **varmadan**; giriş–VWAP arası en az 2R (kitap: 10 puan stop için 30 puan yer), yoksa işlem yok |
| BK-06 | F | Büyük yapı önce: yükseliş trendinde VWAP altına iniş long fırsatı olabilir, düşüş trendinde short |
| BK-07 | F | Nakit ve vadeli VWAP'ı farklıysa hacmi büyük olan esas |
| BK-08 | F | **Yatay piyasa listesi:** fiyat VWAP / POC / değer alanında · ilk saatin aralığında · ADX < 25 · simetrik üçgen · iç ve dış mumlar · EMA10–EMA20 sürekli kesişiyor · yuvarlak sayıda. Yataysa işlem yok |
| BK-09 | F | Değer alanı çok darsa işlem yok (kitapta Dow 100, DAX 40 puan; bizde ATR'ye oranlanmalı, Ö) |
| BK-10 | T | Açılış aralığı: ABD açılışının ilk saati. Aralığın ve önceki gün H/L'nin üstü/altı başarının arttığı bölge; açılıştan önceki saatler ve ilk 15 dakika kaçınılır |
| BK-11 | T | Trend çizgisi kırılımı göstergelerden önce haber verir; Elliott itkisi aranır. Trend %100 geri alınana kadar bitmiş sayılmaz (0,618 dönüşte işlemde kalınır) |
| BK-12 | D | Önce kâğıt üstünde kanıt; tek piyasada uzmanlaş; iyi işlemlerden oyun kitabı çıkar |

**Dikkat:** kitap istatistik vermiyor, seçilmiş 2019 örnekleri gösteriyor. Kriptoda kapanış yok; "gün" 24 saat. Altın/S&P gün içi verimiz kısa (15m ~60 gün), BTC 2017'den.

## 2. Borsaya Başlayanlar İçin Altın Kurallar (Murat Bayhan, 2000)
| No | Tür | Kural |
|---|---|---|
| BK-20 | T | Aroon (14): Up 70–100'de kalıyor ve Down 0–30 → güçlü yükseliş; tersi düşüş; paralel hareket → sıkışma; kesişme → yön değişimi |
| BK-21 | T | CCI ±100 dışı aşırı; +100 üstünde alım yok; CCI / momentum / stokastik / RSI / Ultimate **uyumsuzluğu** erken uyarı (RSI bizde var) |
| BK-22 | T | 200 günlük EMA ve **21 haftalık EMA**: kapanış üstünde al, altında sat (yalnız trendde; tepeyi dibi yakalamaz) |
| BK-23 | T | MACD (12, 26, 9): tetik kesişimi; sıfır üstü yükseliş. **Yatayda** sık yanlış, stokastik 20/80 yatayda iyi → önce rejim belirlenir |
| BK-24 | F | Osilatör sinyali fiyat onayıyla beraber; gösterge kendi trend çizgisini / desteğini kırabilir (RSI formasyonu, hatalı salınım) |
| BK-25 | T | **Kırılım + hacim:** yüksek hacimle kırılıp dönüşte hacim azalırsa gerçek; düşük hacimle kırılıp dönüşte artarsa tuzak (boğa / ayı). Pencere 20 mum (Ö). Kırılan direnç destek olur (PA ile aynı) |
| BK-26 | F | Yükseliş her gün azalarak sürüyorsa momentum zayıflıyor; sert yükselişten sonra geri çekilme %60'ı bulabilir (0,618 ile uyumlu) |
| BK-27 | T | **Elliott osilatörü** = EMA5 − EMA35: 3. dalga tepesi > 5. dalga tepesi; 4. dalgada sıfıra yaklaşır |
| BK-28 | T | Zigzag: A beş dalga; B genelde %50, **en çok %75**; C = 1 / 1,62 / 2,62 × A. Düzensiz yassı: B = 1,15–1,25, C = 1,62–2,62. Üçgen çoğunlukla 4. dalgada, 3'ün yönüne kopar; B'deyse A'nın yönüne. 2 basitse 4 karmaşık |
| BK-29 | F | İyimserlik anketi > %85 düşüş, < %25 yükseliş belirtisi (anket verimiz yok; funding benzer rol oynar) |
| BK-30 | F | Olumlu habere rağmen yükselemeyen düşer, olumsuz habere rağmen düşmeyen yükselir |
| BK-31 | D | Risk önceden sınırlı · zararı kes · **zarardaki işleme ekleme yok**, ekleme yalnız kârda ve azalarak · emin değilsen işlem yok · çoğunluğa uyma · plan seans içinde değişmez · seri hatada ara ver |
| BK-32 | F | Dibi/tepeyi yakalamaya çalışma: dönüş **kendini kanıtlasın** (bizdeki kapanış + LTF onayı) |
| BK-33 | F | Portföy: eşit ağırlık, sinyal bozulana kadar tut, açıkta kalan pay başka varlığa kaydırılmaz (Portfolio Service fikri) |
| BK-34 | F | Çoklu gösterge süzgeci (fiyat > EMA21, MACD > tetik, RSI ve CCI kendi ortalamasının üstünde, Aroon yukarı, hacim artıyor…) **aday listesidir**, tek başına al değil |

**Çelişkiler:** BK-28'de B sınırı %75; bizde derin B zaten kesin değil **uyarı** (E-33), öyle kalır. BK-22 ile BK-11 farklı çıkışlar: ikisi de ölçülür.
BK-34'teki göstergelerin çoğu aynı bilgiyi (son kapanışlar) ölçer; 12 onay 12 bağımsız kanıt **değildir**.

## 3. Okuma durumu
| Kitap | Sayfa | Durum |
|---|---|---|
| VWAP Stratejisi | 44 | ✅ tamamı |
| Altın Kurallar | 53 | ✅ tamamı |
| Sıradakiler | | Karar Verme (22), Akıllı Borsacı (67), Trading Psikolojisi (129), Alpha Trader (488), Borsa Sihirbazları (524), Bir Borsa Spekülatörünün Anıları (270), High Performance Trading (312), Market Mind Games (257), Piyasaları Okumak (270) |
| Temel analiz / portföy | | Akıllı Yatırımcı, Borsada Tek Başına, Duygusuz Yatırımcı, Değerleme, Finans Teorileri: 4.4 değil, 4.1–4.3 için |
| Alınmayacak | | Tarih, ekonomi-politik, kişisel gelişim (işlem kuralı yok) |
