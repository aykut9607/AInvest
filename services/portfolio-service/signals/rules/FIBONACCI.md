# Fibonacci kural listesi (v1, 23 Kasım 2026)

Aykut'un cevapları işlendi. `Ö` işaretliler benim önerim; puanlar kurallar bitince backtest'ten gelecek.

Görseller: [fib-visuals.html](fib-visuals.html). Seviyeler Aykut'un TradingView ayarları; `fib_tools.py` ekran görüntülerindeki fiyatları
birebir veriyor (30 seviye test edildi).

```powershell
.\venv\Scripts\python.exe -m signals.rules.fib_draw trend 57755.8 66937.7 62240   # 0 1 2
.\venv\Scripts\python.exe -m signals.rules.fib_draw fine  57755.8 66937.7 62240   # ikinci (ince) trend seti
.\venv\Scripts\python.exe -m signals.rules.fib_draw ret   55100 64572.5           # hareketin başı, sonu
.\venv\Scripts\python.exe -m signals.rules.fib_draw mon   64572.5 60350           # Pazartesi yüksek, düşük
```

**Kaynak:** A = Aykut'un anlattığı/ayarı · M = matematik (gösterilebilir) · W = araştırma · Ö = benim önerim · **?** = sorulacak.

## 1. Dört araç

| Araç | Noktalar | Formül | Ne için |
|---|---|---|---|
| **Trend fib (ana)** | 0 hareket başı, 1 hareket sonu, 2 geri çekilme sonu | 2 + k × (1 − 0) | Hedefler, dalga boyu, "nereden döner" (Elliott 3: 0-1-2; 5: 2-3-4; C: A-B) |
| **Trend fib (ince)** | çoğunlukla **tepeden**: 0 tepe, 1 ilk düşüşün dibi, 2 tepki tepesi | aynı | düşüşün nereye ineceği; **bazen 0,886**'da biter (A) |
| **Fib retracement** | 1 = hareketin başı, 0 = sonu | son − r × (son − baş) | Geri çekilme nerede biter |
| **Pazartesi aralığı** | 0 = Pazartesi yüksek, 1 = düşük | yüksek − r × (yüksek − düşük) | Likidite süpürmesi → dönüş |

## 2. Seviyeler ve görevleri

**Trend fib, ana set**
| Seviye | Renk | Görev |
|---|---|---|
| 0,618 – 0,786 | yeşil | **tutma bölgesi:** yukarıdaki hedeften dönülürse burası tutabilir (A) |
| 1 | kırmızı | eşitlik ([3]=[1], C=A) |
| 1,272 | turuncu | **tetik:** kırılırsa hedefe gider (A) |
| 1,414 · 1,618 | mavi / açık mavi | hedef |
| 1,79 · 2 · 2,618 · 2,79 · 3 · 3,618 · … 7,618 | mavi | uzak hedefler; her tam sayıdan sonra aynı düzen (+0,618, +0,79) |

**Trend fib, ince set:** 0 · 0,236 · 0,382 · 0,5 · 0,618 · 0,786 · 0,886 · 1 · **1,114 · 1,214 (sarı)** · 1,272 · 1,34 · 1,382 · 1,618 · 2,618 · 3,618 · 4,236.
(Kapalı olanlar kullanılmıyor: 3, 3,272, 3,414, 4, 4,272, 4,414, 4,618.)

**Fib retracement:** 0 · 0,114 · 0,236 · **0,34–0,382 (kırmızı, sığ)** · 0,5 · **0,618–0,66 (kırmızı, ana)** · **0,709 (mavi)** · 0,786 · 0,886 · 1.

**Pazartesi:** üst süpürme **−0,114 / −0,214**, derin −0,618, sonra −1,618, −2,618 · orta 0,5 · alt süpürme **1,114 / 1,214**, derin 1,618,
sonra 2,618, 3,618. Üst ve alt simetrik.

## 3. Matematik (neden bu sayılar)

| Gözlem | Anlamı |
|---|---|
| 0,786 = √0,618 · 0,886 = √0,786 · 1,272 = √1,618 · 1,618 = 1/0,618 · 2,618 = 1,618² · 4,236 = 1,618³ | hepsi altın orandan |
| 1,414 = √2 · 0,709 ≈ 1/√2 · 0,5 | altın orandan **değil** |
| 0,382 = 1 − 0,618 · 0,34 = 1 − 0,66 · 0,114 = 1 − 0,886 · 0,214 = 1 − 0,786 | liste simetrik |
| 1,114 = 1 + 0,114 · 1,214 = 1 + 0,214 · 1,34 = 1 + 0,34 · 1,382 = 1 + 0,382 | aynı simetri 1'in ötesinde; Pazartesi seviyeleri de bu |
| **1. dalganın sonu, uzatmada 2'nin geri alma oranına denk gelir** | 2, 1'i %51 geri aldıysa 1'in tepesi 0,51 seviyesidir. **Yeşil bölge bu sınırın hemen üstüdür:** 4. dalga yeşilin altına, o seviyeye inerse E-04 bozulur |
| 3, 1,618'de biterse: 0,618 seviyesi = 3'ün **0,618** geri çekilmesi, 0,786 = **0,514** | yeşil bölge ≈ 3'ün 0,5–0,618'i. Aynı yerin iki adı, **iki ayrı kanıt değil** (E-72). Olağan 4. dalga (0,236–0,382) ise **1,0–1,24** seviyelerine iner |

Son satırın sonucu: fiyat yeşil bölgeye dönmüşse olağan bir 4. dalgadan derindir; ya derin 4'tür ya da itki bitmiş, daha büyük düzeltme başlamıştır.

## 4. Kurallar (onayına)

**Ortak**
| No | Tür | Kural | Kaynak |
|---|---|---|---|
| F-01 | K | Noktalar kesinleşmiş tepe/diplerdir, fitil uçları kullanılır | A (grafikler), E-G1 |
| F-02 | K | Elliott kuralı bozuksa fib kurtarmaz (E-70) | B6 |
| F-03 | K | Seviye **bölgedir**: 0,618–0,786, 0,34–0,382, 0,618–0,66 iki çizgi arası; tek seviyede ±%3 | A |
| F-04 | K | ±%3 yalnız 1'e kadar; 1'in üstünde **sabit ±0,03**. Yoksa 3,618 / 3,79 / 4 birbirine karışıp 3,51–4,12 arası her yer "fib" olur | Ö + M |
| F-05 | K | Aynı bacaktan çıkan iki seviye tek kanıttır; farklı bacaklardan (ör. 0-1-2 ile 2-3-4, HTF ile LTF) çakışma sayılır | E-72 |
| F-06 | K | Seviyeye dokunmak işlem değildir: LTF SFP + P.U/N.U + kapanış onayı (RULES.md 3, 7) | A |
| F-07 | R | Önce seviye yazılır, sonra fiyat beklenir; fiyat geldikten sonra uygun seviye seçilmez (24 + 17 seviye içinde her yere uyan biri bulunur) | Ö |

**Trend fib**
| No | Tür | Kural | Kaynak |
|---|---|---|---|
| FT-01 | K | 2, 0'ı geçemez (E-01 ile aynı) | E-01 |
| FT-02 | K | **Tetik:** **günlük** kapanış 1,272'nin ötesindeyse hedef 1,414, sonra 1,618. Fitil yetmez | A |
| FT-03 | R | Tetik iptali: fiyat 1'in altına dönerse hedef beklentisi biter | Ö |
| FT-04 | K | **Tutma:** fiyat bir hedefe (≥ 1,414) ulaşıp dönerse ilk aday bölge 0,618–0,786; alım için F-06 onayı | A |
| FT-04a | K | Yeşil bölge yalnız 2, 1'i **0,618'den az** geri aldıysa 1'in tepesinin üstündedir. 2 daha derinse bölge 1'in alanına girer: orası 4. dalga olamaz (E-04), itki sayımı bitmiştir | M |
| FT-05 | K | **Üç aşamalı iptal:** (1) günlük kapanış 0,618 altında → **askıda**, yeni alım yok; (2) **haftalık** kapanış da altında → **iptal**; (3) hafta kapanmadan günlük kapanış yeniden 0,618'in üstüne çıkar **ve** LTF'de SFP + P.U varsa → **askı kalkar** | A (RSI ile kalkma, 1W fikri) + Ö |
| FT-05a | K | Askı kalkması açık işlemi kurtarmaz: stop çalıştıysa çalışmıştır; kalkma **yeni** girişe izindir, stop'u son dip | Ö |
| FT-05b | K | Haftalık iptalden sonra geri dönüş eski planı diriltmez; yeni yapı, yeni noktalar | Ö |
| FT-05c | K | 1'in tepesi fitille kırıldıysa 4. dalga sayımı zaten bitmiştir (E-04, E-94); bölge yalnız destek olarak kalabilir | E-04 |
| FT-06 | R | Aşırı yükselişte "nereden döner": hedefte (1,618 / 2,618 …) N.U ve/veya SFP varsa dönüş adayı; geri çekilme sırası: 3'ün 0,236–0,382'si → 0,5 → yeşil bölge | A + E-12, E-19 |
| FT-07 | R | 2,618'in ötesi aşırı uzama: 5'te güdüklük riski (E-16) | T |
| FT-08 | R | İnce sette (düşüşte) bakılan yer **0,886**; 1 = eşitlik, 1,114–1,214 = eşitliğin hemen ötesi (süpürme okuması Ö) | A + Ö |

**Retracement**
| No | Tür | Kural | Kaynak |
|---|---|---|---|
| FR-01 | K | 0 hareketin sonuna, 1 başına konur | A (grafik) |
| FR-02 | R | Derinlik sırası: 0,34–0,382 sığ (güçlü trend, 4. dalga) · 0,5 · 0,618–0,66 ana · 0,709 · 0,786–0,886 derin (harmonik D'ler) | A + E-10, E-12, H-04 |
| FR-03 | K | 1'in ötesi: hareket tamamen geri alındı, geri çekilme bitti | M |
| FR-04 | R | 0,618–0,66–0,709 birbirine çok yakın: **tek bölge** (0,60–0,73) sayılır, üç ayrı onay değil | Ö + M |

**Pazartesi aralığı**
| No | Tür | Kural | Kaynak |
|---|---|---|---|
| FM-01 | K | Aralık ancak **Pazartesi kapanınca** kesindir (UTC 00:00 = TSİ 03:00). Attığın çizimde mum henüz kapanmamıştı (3 sa 34 dk vardı); seviyeler değişebilir | M |
| FM-00 | R | Pazartesi genelde **manipülasyon günüdür**; her hafta aralık yeniden çizilir, Pazar'a kadar geçerlidir | A |
| FM-02 | K | Süpürme: fiyat Pazartesi yükseğini/düşüğünü geçer; bölge 0,114–0,214 ötesi | A |
| FM-03 | K | Alt likidite alınıp dönülürse yukarı, üst alınıp dönülürse aşağı. LTF kapanışı aralığın içinde + F-06 onayı | A |
| FM-03a | R | **0,5 (güç ölçüsü):** kapanışlar 0,5'in üstündeyse fiyat güçlü/yukarı, altındaysa zayıf/aşağı | A |
| FM-04 | R | Model: bir uç süpürülür → 0,5'in öbür tarafında kapanış → hedef **karşı uç**; stop süpürmenin ucu | A + Ö (stop) |
| FM-05 | R | −0,618 / 1,618'in ötesinde günlük kapanış ve geri dönüş yoksa kırılım sayılır | Ö |
| FM-06 | K | **Yalnız BTC.** Altın ve S&P için ölçüm aşağıda: uygun görünmüyor | A + ölçüm |

## 5. Ölçüm (BTC, yalnız kalibrasyon dönemi: 2017-08 – 2024-02; test dönemine bakılmadı)

Yöntem: ZigZag yapıları, 1h mumlarla hangisi önce, aynı mumda stop önce, **ücretsiz ve onaysız** (SFP, uyumsuzluk, HTF yönü yok).
"Rastgele" = aynı hedef/stop mesafesinde yazı-tura oranı. Yapılar örtüştüğü için gerçek belirsizlik aralıktan geniştir.

| Soru | Sonuç |
|---|---|
| 1,272 kırılınca 1,618'e, 1,0'a dönmeden gider mi? | **%67** (n 577; %63–70), rastgele %57. 1D yapılarda %65 (n 85; %54–74), rastgele %54. **Ama** rastgele seçilmiş komşu seviyeler de %59–66 (1,1 · 1,2 · 1,35 · 1,45 · 1,75 · 1,9): kırılım etkisi var, 1,272'ye özgü değil |
| ≥ 1,618'e çıkıp dönünce yeşil bölge tutar mı (hedef +0,214, stop −0,286)? | 0,786'da %52 (n 297), 0,618'de %50 (n 280); rastgele %57. **Onaysız tutmuyor.** 1D yapılarda %56 / %48 (n ~30, sonuç çıkmaz) |
| Dalgalar seviyelerde mi bitiyor? | 1D'de bitişlerin %19,9'u seviyelerin ±0,03'ünde; kaydırılmış sahte seviyelerde %21,9. **Yığılma yok** |
| Retracement seviyesinde tepki farkı? | 0,236–0,886 arası hepsi %50–54 (0,236: %59); ara sahte seviyeler (0,30 · 0,44 · 0,56 · 0,75 · 0,84) ile fark yok |
| Pazartesi süpürülür mü? | Haftaların %98'inde en az bir uç geçiliyor, %41'inde ikisi de; geçişlerin %90'ı hafta içinde 1h kapanışla geri dönüyor. Diğer günlerde de aynı (%87–93) |
| Süpürme 0,114–0,214'te biter mi? | %8'i orada, %6'sı daha önce, %24'ü 0,214–0,618'de, **%62'si 0,618'i geçiyor** (orta değer 0,88 aralık) |
| 0,114'te karşı yön, stop 0,618, hedef 0,5 | %42 (n 408; %38–47), rastgele %45 |
| Süpürme + 1h içeri kapanış, hedef 0,5, stop süpürme ucu | **%58** (n 216; %51–64), rastgele %56; Salı, Perşembe ve Cuma aralıkları da %60–63: Pazartesi'ye özgü değil |

**Pazartesi, ikinci tur** (Aykut'un anlattığı model; BTC 2017-08 – 2024-02, altın 2012 – 2022-06, S&P 2000-09 – 2019-01)

| Soru | Sonuç |
|---|---|
| Günlük kapanış 0,5 üstünde/altında → o kapanıştan Pazar'a aynı yön mü? | BTC Pazartesi kapanışı: üstte → yukarı %52 (n 184), altta → aşağı %41 (n 153); genel yukarı %55. Salı–Perşembe kapanışları ve altın/S&P benzer. **0,5 tek başına yön vermiyor** |
| Süpürme + **1h** kapanış 0,5 ötesi → karşı uç (stop süpürme ucu) | BTC **%77** (n 132; %69–83), rastgele %71. 4h: %79 (n 111), rastgele %73. 1D: %74 (n 43), rastgele %74 |
| Aynı model diğer günlerin aralığıyla | 1h: %66–78 (rastgele %69–73); Çarşamba %78. Pazartesi iyi tarafta ama **tek değil** |
| Kazanç/risk | 0,5'ten sonra hedefe az yol kalır: rastgele %71 ≈ R/R 0,4. +6 puan ≈ işlem başı +0,08 R, **ücretten önce**; haftası içinde bitmeyen 37 işlem hariç |
| Haftanın dibi/tepesi Pazartesi mi? | BTC: dip %35, tepe %26. Hafta başka günden başlatılsa ilk günün dip payı %22–32, tepe payı %17–29. Dip için hafif bir Pazartesi izi var |
| Altın (günlük mum) | **%50** (n 42; %36–64), rastgele %74 → **uygun değil** |
| S&P (günlük mum) | %69 (n 103; %59–77), rastgele %75 → **uygun değil** (saatlik veri kısa, 1h modeli ölçülmedi) |

**Yeşil bölgenin iptali** (günlük mum; BTC + altın + S&P kalibrasyonları; ≥ 1,414'ten sonra 0,786'ya dönen 234 yapı)

| Soru | Sonuç |
|---|---|
| Günlük kapanış 0,618 altına | %47 (n 110) |
| Kırılımdan sonra 1'e dönüş / aynı mesafe aşağı | %49 (n 109): yön bilgisi yok |
| Günlük kapanışla geri alma | 1 günde %36, 3 günde %57, 5 günde %69, 10 günde %76. **Günlük kapanışla kesin iptal fazla erken** |
| Hafta 0,618 **üstünde** kapandıysa, geri alımdan 1'e | %62 (n 24; %43–79), rastgele %52 |
| Hafta **altında** kapandıysa, sonraki geri alımdan 1'e | %53 (n 51; %40–66), rastgele %64 |
| LTF onayının (SFP veya P.U) katkısı | BTC'de 16 olay (onaylı 12): **ölçülemez** |

Ayıran haftalık kapanış gibi duruyor (üstte +10, altta −11 puan), FT-05 buna göre yazıldı. Örnek az, aralıklar geniş: **hipotez**, test döneminde sınanacak.

**Örneğindeki yapı** (57.755,8 → 66.937,7 → 62.240): 19–21 Ağustos'ta 0,618'den 1,618'e kadar seviyeler günlük kapanışla aşıldı; tepe 87.396 (21 Eylül, 2,74:
2,618–2,79 arası). 13 Kasım'da 0,786'ya (69.457) dokundu, en fazla 70.214'e tepki verdi (1 = 71.422'ye dönemedi), 14 Kasım'da
1'in tepesinin (66.938) altına indi. Yani bu örnekte yeşil bölge **tutmadı**; FT-05 (günlük kapanış 64.150) bunu 14 Kasım'da yakalıyor.

**Okuma.** Seviyeler tek başına yazı-turadan ayrılmıyor; fib'in işi **nereye bakılacağını** söylemek. Kazanç varsa onay katmanından (SFP,
P.U/N.U, HTF yönü, farklı bacakların çakışması) gelmeli; sıradaki ölçüm bu. Bu, Elliott/harmonik v0 sonucuyla uyumlu.

## 6. Araştırma
Ölçüm betikleri yerelde: `data/research/` (git dışı).
- TradingView trend fib üç noktalıdır (hareket başı, sonu, düzeltme sonu); 1,414 gibi bazı seviyeler Fibonacci değil, alışkanlıktır (LuxAlgo).
- Akademik tablo karışık, çoğunluk şüpheci: büyük örneklerde 0,382/0,5/0,618'in diğer oranlardan sık görülmediğini aktaran çalışmalar; enerji hisselerinde
  kriptodan iyi sonuç bulan bir çalışma (*Financial Innovation*, 2022); ETF'lerde al-tut'un gerisinde kalan bir öğrenci projesi (HKUST, 2022).
- Pazartesi aralığı yaygın bir trader fikri; kuralı tanımlı, örneklem dışı test edilmiş bir kaynak **bulamadım**. 1,114 / 1,214 / 0,34 / 0,709
  seviyeleri için de kaynak bulunamadı (0,709, ICT'nin 0,705 "OTE" seviyesine yakın; kaynakla doğrulanmadı).
- Bu özetler arama sonuçlarından; makaleler tek tek okunmadı. Tezde kullanılacaksa asılları okunmalı.

## 7. Açık kalanlar (cevap beklemeden ilerlenebilir)
- İnce set okumam: 0 tepe, 1 ilk düşüş dibi, 2 tepki tepesi; düşüş 0,886'da bitebilir. Yanlışsa düzeltilecek.
- Ölçülmeyenler: HTF yönü, F-06 onayı (SFP **ve** P.U/N.U aynı dipte), farklı bacakların çakışması, altın/S&P'de 1h Pazartesi.
- FT-05'in test döneminde sınanması (kurallar donunca, bir kez).
