# Mentor bakışı: sözlük, gösterge paneli, mentorlar (v1, 24 Kasım 2026)

Görseller: [mentor-visuals.html](mentor-visuals.html). Kod: `ext_detect.py`. Metin kopyalanmadı, kendi cümlelerimizle özet.
Kaynak: **S** Sözlük (159 terim, hepsi okundu) · **G** gösterge paneli · **MV** mentor videoları (kareler, ses yok) · **Ö** öneri · **?** onay.

## 1. Sözlükten kesinleşenler
| No | Kural | Bizde |
|---|---|---|
| MB-01 | **Gerçek kırılım:** önceki tepenin/dibin **fitil ucundan** çizilen çizgiyi yeni mumun **gövdesi** keser. Fitil keserse sahte kırılım; range'de deviasyon, seviyede sweep | PA-06, SM-22, SM-30 ile **aynı** |
| MB-02 | **MSB** yapının bozulması (yön değişebilir); **BOS** devam; **CHoCH** iki swing arasında, son büyük tepe/dip kırılmadan olan **iç** karakter değişimi | SM-13 düzeltildi; sıra kararı bölüm 6 |
| MB-03 | HTF = 4h ve üstü, LTF = 1h ve altı | **4h = HTF** (Aykut, 24 Kas); RULES.md güncellendi |
| MB-04 | EQ'da işlem açılmaz, kâr alınır; premium'da short, discount'ta long aranır | SM-21 ile uyumlu |
| MB-05 | **Sıra: Likidite → Sweep → MSB → Retest → Giriş** | PR-60'ın aynısı |
| MB-06 | Deviasyon sonrası hedef önce EQ, sonra karşı uç | SM-21 |
| MB-07 | Güçlü market dengesizliğe (FVG), zayıf market likiditeye gider | kılavuz |
| MB-08 | **Golden pocket 0,618–0,66** | FR-02, PR-60 |
| MB-09 | Fiyat WO / MO üstünde mi altında mı: yön filtresi | MB-22, ölçüldü |
| MB-10 | Kaos fitili: dev fitil, küçük gövde, yüksek hacim; boşluk sonra doldurulmak istenir. Single print: aynı fikir | görsel var, ölçülmedi |
| MB-11 | VWAP / AVWAP: üstünde alıcı kârda | veri var (hacim), kodlanmadı |
| MB-12 | KMS: kârda bir kısım kapat, stop girişe; tamamı kapatılmaz | RK'ya eklenecek |
| MB-13 | Devre kesici: haftada −3R ya da üst üste 2–3 stop → dur | RK-05, RK-21 ile uyumlu |
| MB-14 | CME gap artık tarihsel (CME 7/24) | PR-50 doğrulandı |
| MB-15 | Elliott tanımları (28 terim) | ELLIOTT.md ile çelişki yok |

## 2. Gösterge paneli
| No | Kural |
|---|---|
| MB-20 | **EXT I / II = 1,114 / 1,214:** kapanmış menzilin (Pazartesi, geçen hafta, geçen ay) %11,4–21,4 ötesi; 0,886 ve 0,786'nın aynası. Banda değip dönerse **süpürme**, bandın ötesinde **kapanırsa gerçek kırılım**. Senin Pazartesi fib'in; haftalık ve aylığa da aynısı uygulanıyor |
| MB-21 | Seviyeler: WO / MO / YO açılışları, Monday H/L, PWH/PWL, PMH/PML, 200 günlük ve 50 / 100 / 200 haftalık ortalama, altın bölge. Farklı dilimlerin çakışması "kesişim": hareket sertleşir, **pozisyon küçültülür** |
| MB-22 | Yayın kuralı: WO üstündeyken short aranmaz (istisna: 200G / 200H ortalama, YO ya da test edilmiş direnç); altındayken destekler çalışılır |
| MB-23 | Önce onay, sonra emir: emir akışı (delta), uyumsuzluk, OI. Hacimli kırılım = tipik saatin 1,5 katı |
| MB-24 | Diğer göstergeler: RSI 30/70 (aşırı satım alım sinyali değil), korku-açgözlülük, opsiyon çapası, BTC.D, günlük menzilin dolması ("kovalama"), makro takvim |
| MB-25 | Hacim profili: mum içi dağılım olmadığı için hacim aralığa eşit dağıtılıyor (bizim PR-02 ile aynı yöntem) |

Doğrulama: `ext_detect.py` gösterge panelinin 24 Kasım'da gösterdiği EXT fiyatlarını kuruşuna kadar veriyor (Pazartesi 65.900,35 / 66.079,47 · 63.700,82 / 63.521,70;
haftalık 53.925,46 / 52.868,84; aylık 88.461,92 / 89.551,32), test olarak eklendi.

**Gösterge panelinin kendi yayımladığı istatistikler** (BTC, Ağu 2017 – Kas 2026):
| Seviye | Dokununca döndü | Aynı uzaklıkta rastgele çizgi | Onların yorumu |
|---|---|---|---|
| Monday low (309) | %48 | %49 | gürültü payı içinde |
| Pazartesi EXT I aşağı (286) | %49 | %49 | gürültü payı içinde |
| PWH (246) | %40 | %45 | gürültü payı içinde |
| Haftalık EXT I aşağı (165) | %52 | %48 | gürültü payı içinde |
| WO tarafı → hafta kapanışı (478 hafta) | %62 (Pzt) | %63 | yazı-turadan iyi değil |
| Hacimli / hacimsiz WO kırılımı, 24 saat sonra aynı taraf | %59 / %54 | | "fark küçük" |

Yani **eğitimi veren ekip de** seviyelerin tek başına yazı-turadan ayrılmadığını yazıyor; bizim ölçümlerle (FIBONACCI 5, SMART_MONEY 13, PROFESSIONAL 10) aynı. Görüşmede güçlü bir dayanak.

## 3. Mentorlar (kareler; ses yok, sözleri bilinmiyor)
| Mentor | Görülen yöntem |
|---|---|
| Mentor 1 (25 dk) | Grafik kısmı: 30 dk'da hareketin fib'i, yalnız **0,34–0,382 ve 0,618–0,66**; 0,618–0,66'ya inen fitil işaretleniyor, oradan long, stop bölgenin altı, hedef önceki tepe (örnekte R/R 6,8) |
| Mentor 2 (25 dk) | Günlük ve uzun dilim fib (0,34 / 0,382 / 0,5 / 0,618 / 0,66), hacim profili, döngü tepesi-dibi; 15 dk'da aynı fib |
| Mentor 3 (8 dk) | SERS41 RSI (P.U / N.U), trend çizgileri, flip seviyeleri, seans hacim profili / NPOC, range 0–0,5–1 |

Üçünün ortak paydası: HTF bölge + **0,618–0,66** + LTF tepki. FR-02 ve PR-60 ile uyumlu.

## 4. Ölçüm (BTC kalibrasyon 2017-08 – 2024-02)
| Soru | Sonuç | Yazı-tura |
|---|---|---|
| Pazartesi EXT süpürmesi → 0,5 (1h / 4h) | %46 (220) / %52 (207) | %46 / %53 |
| Haftalık EXT süpürmesi → 0,5 (1h / 4h) | %30 (86) / %37 (82), bir kısmı hafta bitince açık | %32 / %37 |
| Pazartesi EXT kırılımı → 1,618, stop uç (1h / 4h) | %54 (181) / %55 (157) | %51 / %58 |
| **Haftalık EXT kırılımı → 1,618, stop uç (4h)** | **%65 (134; 57–72)** | **%50** |
| Haftalık EXT kırılımı (1h) | %60 (143; 52–68) | %45 |
| Aylık EXT kırılımı (1h / 4h) | %68 (31) / %66 (32) | %40 / %42 |
| WO üstünde gün kapanışı → hafta sonuna yukarı | %48–52 (genel yukarı %52–55) | etki yok |

**İlk belirgin bulgu, kontrolleriyle** (haftalık menzilin ötesinde 4h kapanış, ilk kapanış şartı, n 168):
- %62 (54–69) karşı %50; ort. **+0,28 R**, taraf başına %0,1 ücretle **+0,21 R**. Dönemin ilk ve ikinci yarısında da %62.
- Yukarı %66 (98), aşağı %56 (70): iki yönde de var, yukarıda daha güçlü (BTC'nin genel yükselişi payı olabilir).
- **1,214'e özgü değil:** menzil ucunu (0,0) geçince de %59, 1,3'te %57, 1,4'te %60. Bulgu "haftalık kırılım BTC'de devam eder" (ivme), bant değil.
- Günlük kapanışla zayıf (%58 / %57). **Altın ve S&P'de yok** (%53 / %60; %51 / %55).
- Kalibrasyonda çok şey denendi; **test döneminde bir kez** sınanmadan kullanılmaz.

Bunun anlamı: şimdiye kadar ölçtüğümüz "dönüş" kurallarının hiçbiri tek başına çalışmadı; BTC'de çalışan ilk şey **kırılım yönünde devam**. Dönüş planları HTF kırılımına
karşıysa puan kaybetmeli (hipotez).

## 5. Kurallarda değişenler
- **FM-05:** "−0,618 / 1,618 ötesi kırılım" yerine **bandın (1,214 / −0,214) ötesinde kapanış gerçek kırılım** (MB-20).
- **SM-13:** "htf CHOCH, LTF MSB" = LTF'de MSB olan hareket HTF'de yalnız CHoCH'tur; büyük dönüş için HTF MSB gerekir. (Önceki okumamızla sonuç aynı.)
- **SM-80:** EXT bandı Pazartesi'nin yanında hafta ve aya da uygulanır; 200G / 50-100-200H ortalamalar eklendi.
- **SM-91:** seanslar borsaların yerel saatinden (yaz/kış saati dahil): Asya TR 03–11 · Londra 08:00 Londra'dan ABD açılışına · New York 09:30–16:00 New York. ABD açılışı TR'de **yazın 16:30, kışın 17:30**.

## 6. Kararlar (24 Kas)
1. **CHoCH → MSB (Aykut kararı bana bıraktı):** CHoCH, yapı içindeki **son küçük** tepenin/dibin kapanışla kırılmasıdır (erken uyarı, korunan seviye hâlâ duruyor);
   MSB **korunan** tepenin/dibin kırılmasıdır (dönüş). Aynı dilimde önce CHoCH, sonra MSB olur. Sözlükteki "MSB önce gelir" cümlesini **önem sırası** olarak
   okudum: LTF'deki MSB, HTF'de yalnız CHoCH'tur. CHoCH tek başına plan üretmez. Kod: `choch_breaks`, görsel `pa-visuals.html`.
2. **4h = HTF.** LTF = 1h ve altı.
3. **Seanslar:** Türkiye saati (UTC+3) gösterilir, yaz/kış farkı koddan gelir (`smc_detect.sessions`).

## 7. Kayıt
Sözlük 159/159 terim · gösterge panelinin ana panelleri ve seçilmiş seviye açıklamaları (Monday low, Pazartesi EXT I, PWH, WO, haftalık EXT I) · mentor videoları 3/3 (9'ar kare, ikisinde yakın çekim).
Temel analiz terimleri (25) şirket analizi içindir, 4.4 kapsamı dışında.
