# Price action kural listesi (v1, 24 Kasım 2026)

Görseller: [pa-visuals.html](pa-visuals.html) — üstte kuralın çizimi, altta **aynı kuralın kendi verimizde kodla bulunmuş hali**. İkisi uyuşmuyorsa
kural yanlış anlaşılmıştır: Aykut doğru görseli atar, kural ve kod birlikte düzelir. Kod: `pa_detect.py` (yalnız kesinleşmiş tepe/dip, geleceğe bakmaz).

```powershell
.\venv\Scripts\python.exe -m signals.rules.pa_draw BTCUSDT 1d 2026-01-15 2026-11-21   # istediğin pencerenin yapısı → data/reports/pa-check.html
```

Tür: **K** kesin · **R** kılavuz. Kaynak: **N** ders notu · **V** video (kareler izlendi, ses yok) · **Ö** benim tanımım · **?** onay bekliyor.
Seviye: Dersler → **Orta**. İleri: [SMART_MONEY.md](SMART_MONEY.md).

## 1. Piyasa yapısı
| No | Tür | Kural | Kaynak |
|---|---|---|---|
| PA-01 | K | HH / LH: önceki tepeden yüksek / alçak tepe. HL / LL: önceki dipten yüksek / alçak dip | N |
| PA-02 | K | Yükseliş = HH + HL, düşüş = LH + LL, karışıksa yatay | N |
| PA-03 | K | **BOS:** trend yönündeki son tepenin (dibin) kırılması = devam | N, V |
| PA-04 | K | **MSB** (notta CHoCH): düşüşte **en dibi yapan son tepenin** yukarı, yükselişte **en tepeyi yapan son dibin** aşağı kırılması = dönüş. Ara tepki tepesinin kırılması yetmez | V (çizimde etiketli), N |
| PA-05 | K | MSB'den sonra HL (LH) ve yeni yönde ilk BOS = dönüşün teyidi | V |
| PA-06 | K | Kırılım, tepe/dibin çizildiği **dilimin kapanışıyla** (1D yapı → 1D kapanış); fitil kırılım değil (SFP adayıdır) | A onayı |
| PA-07 | R | HTF yapısı LTF'den üstündür (videoda "HTF > LTF") | V |
| PA-08 | R | Trende karşı işlem yok; BOS sonrası geri çekilmede giriş aranır | N |
| PA-09 | K | MSB'den önce geride kalmış eski seviyeler yeni BOS sayılmaz; yeni bir tepe/dip oluşmalı | Ö |

## 2. Trend çizgisi
| No | Tür | Kural | Kaynak |
|---|---|---|---|
| PA-10 | K | Yükselende dipler, düşende tepeler birleşir; en az 2 temas, iyisi 3+ | N, V |
| PA-11 | K | Trend çizgisi ve formasyon çizgileri **fitil** uçlarından (not "genelde gövde" diyor; Aykut fitil seçti) | A |
| PA-12 | K | Geçerli kırılım = kapanış öbür tarafta; fitille geçip dönmek sahte kırılım | N |
| PA-13 | R | Kırılımdan sonra çizgiye dönüş (retest) daha güvenli giriş | N, V |
| PA-14 | R | Her dokunuş işlem değildir; yüksek dilim çizgisi daha güçlü | N |

## 3. Yatay seviye
| No | Tür | Kural | Kaynak |
|---|---|---|---|
| PA-20 | K | Önce **aylık**, sonra haftalık, sonra günlük çizilir; her çizgi dilimiyle etiketlenir (M / W / D) | V, N |
| PA-21 | K | Seviye, mum **gövdelerinin döndüğü** yerdir (yukarı mumun kapanışı + ardından aşağı mum; tersi) | V, A onayı |
| PA-22 | R | Güçlü seviye: 2–3+ temas, yüksek dilim, yüksek hacim, yakın tarih; çizgi değil **bölge**; 5–7 ana seviye yeter | N |
| PA-23 | K | **Flip:** kırılan direnç destek, kırılan destek direnç olur | N |
| PA-24 | R | Yuvarlak sayılar ve farklı dilimlerin aynı yerde buluşması (4h + 1D) güçlendirir | N |

## 4. Formasyonlar
| No | Tür | Kural | Kaynak |
|---|---|---|---|
| PA-30 | K | **Yükselen kama:** iki çizgi yukarı, **alt çizgi daha dik**, daralır, en az 2 tepe + 2 dip. Beklenen kırılım aşağı | N, V |
| PA-31 | K | **Alçalan kama:** iki çizgi aşağı, **üst çizgi daha dik**. Beklenen yukarı; düşüş sonunda dönüş, yükselişte devam | N, V |
| PA-32 | K | **Simetrik üçgen:** tepeler alçalır, dipler yükselir. Yön önceden seçilmez; önceki trend yönü biraz daha olası; kırılım genişliğin ~%75'inde beklenir | N, V |
| PA-33 | K | **Elmas:** önce genişler, sonra daralır; nadir. Tepede aşağı, dipte yukarı; videodaki son örnekte yukarı devam etti | N, V |
| PA-34 | K | Giriş **kapanışla kırılım**; kırılım + retest en iyisi | N |
| PA-35 | R | Hedef = formasyonun en geniş yeri kadar, kırılan çizgiden. Elmasta üst–alt köşe farkı (videoda kutu ile ölçülüyor) | N, V |
| PA-36 | R | Stop: kamada son tepe/dip; üçgende karşı taraf; elmasta içeri | N |
| PA-37 | R | Formasyon boyunca hacim azalır; kırılımda hacim artışı teyit | N |
| PA-38 | K | Formasyon tamamlanmadan işlem yok; zorla görülmez | N |
| PA-39 | K | Kodun ölçütü: 5 ardışık tepe/dip, ara uçlar çizgiden yüksekliğin en çok %10'u kadar sapar, her bacak öncekinin en az yarısı, en az 15 mum, yükseklik iki çizginin de başladığı yerde | Ö |

**Uyarı (backtest için):** daralan çizgilerde kırılım yönü kısmen **geometriden** gelir (yükselen kamada alt çizgi fiyata yetişir; kodda bulunan kamaların
büyük çoğunluğu aşağı "kırılıyor"). Bu bir üstünlük değildir; ölçülecek olan kırılımdan **sonra** hedefe ulaşma oranıdır, yazı-turayla karşılaştırılarak.

## 5. Kararlar (24 Kas)
MSB/BOS çizildiği dilimin kapanışı · trend ve formasyon çizgileri fitil · aylık/haftalık seviye gövde dönüşü. Hepsi Aykut'un onayı.

## 6. Kayıt
| Ders (Orta) | Not | Video | Durum |
|---|---|---|---|
| Backtest Nasıl Yapılır | ✅ | ✅ kareler (26 dk, USDCAD replay, HTF bölge + SERS41 RSI + 2R işlemler) | RISK.md |
| Market Yapısı | ✅ | ✅ kareler (26 dk); BOS/MSB çizimi okundu | PA-01…09 |
| Trend Çizgisi | ✅ | ✅ kareler | PA-10…14 |
| Seviye Belirleme | ✅ | ✅ kareler; aylık/haftalık çizgi yerleri okundu | PA-20…24 |
| Yükselen / Alçalan Kama, Simetrik Üçgen, Elmas | ✅ | ✅ kareler | PA-30…39 |
| Makro Ekonomik Takvim | ✅ | video yok | RISK.md |
