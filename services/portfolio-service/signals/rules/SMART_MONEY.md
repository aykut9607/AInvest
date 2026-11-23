# İleri düzey kural listesi: likidite ve bölgeler (v1, 24 Kasım 2026)

Görseller: [smc-visuals.html](smc-visuals.html) — üstte kuralın çizimi, altta **kodun kendi verimizde bulduğu en yeni örnek** (başarılı olana göre
seçilmedi). Uyuşmazsa kural yanlış anlaşılmıştır; doğru görselle birlikte düzeltilir. Kod: `smc_detect.py` (her nesne `known_at` taşır).

Tür: **K** kesin tanım · **R** kılavuz. Kaynak: **N** ders notu · **V** video kareleri (ses yok) · **A** Aykut · **Ö** benim sayısal tanımım · **?** onay.

## 1. Mum formasyonları
| No | Tür | Kural | Kaynak |
|---|---|---|---|
| SM-01 | K | **Pin bar:** bir fitil mumun en az %60'ı, gövde en çok 1/3'ü = reddedilme | N + Ö |
| SM-02 | K | **Engulfing:** ters renkli önceki gövdeyi tamamen kaplar = güç değişimi | N |
| SM-03 | K | **Doji:** gövde mumun en çok %10'u = kararsızlık | N + Ö |
| SM-04 | K | **Inside bar:** önceki mumun içinde = sıkışma | N |
| SM-05 | R | Aynı mum yerine göre anlam değiştirir; seviye + trend + yüksek dilim olmadan sinyal değil | N |

## 2. Arz-talep
| No | Tür | Kural | Kaynak |
|---|---|---|---|
| SM-10 | K | Güçlü hareketin başladığı **taban** (rally-base-rally, drop-base-drop). Kod: 1–3 küçük mum (gövde ≤ 0,6 ATR) + güçlü mum (≥ 1,5 ATR); bölge tabanın tamamı | N + Ö |
| SM-11 | R | Taze (hiç dönülmemiş) bölge en güçlü; hızlı oluşan ve güçlü hareket başlatan daha iyi | N |
| SM-12 | R | Giriş ilk dokunuş, stop bölgenin dışı, hedef karşı bölge ya da 2–3R; trend yönünde | N |
| SM-13 | K | **HTF CHoCH + LTF MSB:** bölgede yalnız küçük dilimde MSB yetmez; büyük dilimin karakteri de dönmeli. Videodaki örnekte LTF MSB oldu, HTF CHoCH olmadığı için bölge kırıldı | V, A onayı |

## 3. Range
| No | Tür | Kural | Kaynak |
|---|---|---|---|
| SM-20 | K | Range: üst (RH), alt (RL), **EQ = 0,5** (videoda fib 0 / 0,5 / 1). Kod: 2 tepe + 2 dip, uçlar yüksekliğin %15'i içinde, en az 20 mum | N, V + Ö |
| SM-21 | K | İşlem uçlarda, ortada değil; hedef EQ, sonra karşı uç; stop ucun dışı | N, V |
| SM-22 | K | **Deviasyon (fake-out):** uç geçilir ve hemen içeri kapanılır (kod: en çok 3 mum) → ters yön | N, V + Ö |
| SM-23 | R | Gerçek kırılım: hacim, güçlü mum, retest sonrası devam; içeri dönmeyen kapanışlar range'i bitirir | N |
| SM-24 | – | Pazartesi aralığı (FM) aynı modelin özel hali | A |

## 4. SFP
| No | Tür | Kural | Kaynak |
|---|---|---|---|
| SM-30 | K | Önceki tepenin (dibin) **fitil ucu** geçilir, aynı ya da sonraki mum geri kapanır (RULES.md 3 ile aynı) | N, V, A |
| SM-31 | K | Giriş SFP mumunun kapanışı, stop fitilin ucu, hedef karşı uç ya da 2–3R | N, V |
| SM-32 | R | HTF kilit seviyede, hacimle ve trend yönünde daha güçlü | N |

## 5. Order block
| No | Tür | Kural | Kaynak |
|---|---|---|---|
| SM-40 | K | Güçlü hareketten önceki **son ters mum** (yükselişte son kırmızı, düşüşte son yeşil) | N, V |
| SM-41 | K | Hareket **yapıyı kırmış** olmalı (önceki tepe/dip, kapanışla). Videoda oklarla hem kırılan tepe hem alınan dip gösteriliyor | V |
| SM-42 | K | Bölge mumun tamamı (0–1), giriş **0,5** (videoda fib ile) | V |
| SM-43 | R | Kalite: test edilmemiş, FVG bırakmış, öncesinde likidite almış (sweep), HTF yönünde | N, V |
| SM-44 | K | Bölgenin ötesinde kapanış → OB bitti; ters rolüne geçer (breaker) | N |

## 6. Breaker
| No | Tür | Kural | Kaynak |
|---|---|---|---|
| SM-50 | K | Kırılan destek direnç, kırılan direnç destek olur. Videodaki çizim: **HH'yi yapan dip** kırılır, geri gelişte satılır (MSB + retest) | N, V |
| SM-51 | K | Bölge: kırılan uçtan (fitil) o mumun gövdesine kadar | A onayı |
| SM-52 | R | Giriş retest, stop bölgenin öbür tarafı, hedef sonraki yapısal seviye | N, V (R/R 1,95 örneği) |

## 7. OTE
| No | Tür | Kural | Kaynak |
|---|---|---|---|
| SM-55 | K | Son hareketin 0,62–0,79'u (ideal 0,705); 1 hareketin başı, 0 sonu | N (0,618–0,786), V (0,5 · 0,62 · 0,705 · 0,79) |
| SM-56 | R | Hedefler 0, −0,27, −0,67, −1; stop 1'in ötesi; OB / FVG / HTF seviye ile birlikte | N, V |
| SM-57 | – | Aykut'un fib listesi (0,618 · 0,66 · 0,709 · 0,786) ile aynı bölge; **ayrı kanıt sayılmaz** (FR-04). Bizde 0,618–0,786 kullanılır | A |

## 8. FVG / dengesizlik
| No | Tür | Kural | Kaynak |
|---|---|---|---|
| SM-60 | K | Yükselen: 1. mumun yükseği < 3. mumun düşüğü; düşen: 1. mumun düşüğü > 3. mumun yükseği (**fitillerle**) | N, V |
| SM-61 | R | İlk dokunuş en güçlü; %50 dolum tepki yeri; tamamen dolunca güç biter; büyük ve HTF FVG, trend yönü daha iyi | N |
| SM-62 | K | Dolum yönünde hareket "mutlaka dolar" demek değildir | Ö |

## 9. Likidite
| No | Tür | Kural | Kaynak |
|---|---|---|---|
| SM-70 | K | Tepe üstleri / dip altları stop deposudur ($); **eşit tepe/dip (EQH/EQL)** en belirgin olan. Kod: 0,25 ATR içinde | N, V + Ö |
| SM-71 | R | Önce alınır, sonra dönülür: alındıktan **sonra** giriş aranır; eşit tepe hedef olur, stop yeri olmaz | N |
| SM-72 | R | Stop belirgin seviyenin hemen ardına konmaz; ATR payı | N |
| SM-73 | R | Yükselişte dip altındaki $ alınıp devam edebilir: her süpürme trend dönüşü değildir | V |

## 10. Kilit seviyeler
| No | Tür | Kural | Kaynak |
|---|---|---|---|
| SM-80 | K | Önceki gün / hafta / ay (ve çeyrek) yüksek-orta-düşük; Pazartesi yüksek-orta-düşük; gün / hafta / ay / çeyrek açılışı | V (gösterge ekranı) |
| SM-81 | R | Öncelik: HTF > LTF, kesişim > tek, taze > test edilmiş; az seviye | N |
| SM-82 | R | Yuvarlak sayı, ATH/ATL, eski döngü seviyeleri, MA, VWAP | N |
| SM-83 | K | Seviye yalnız **kapanmış** dönemden hesaplanır (Pazartesi, Salı 00:00 UTC'den sonra) | FM-01 |

## 11. Power of 3
| No | Tür | Kural | Kaynak |
|---|---|---|---|
| SM-90 | K | Birikim (aralık) → manipülasyon (bir uç süpürülür) → dağıtım (ters yönde asıl hareket) | N, V |
| SM-91 | R | Asya birikim, Londra manipülasyon, New York dağıtım. Saatler UTC 00–08 / 08–13 / 13–21 (TSİ 03–11 / 11–16 / 16–24) | N, A onayı |
| SM-92 | R | Manipülasyon HTF bölgesine denk gelmeli (videoda mor bölgeler); haber gününde dikkat; her gün olmaz | V, N |
| SM-93 | – | Aykut: "Pazartesi manipülasyon günü" aynı fikrin haftalık hali | A |

## 12. Open interest
| No | Kural | Kaynak |
|---|---|---|
| SM-95 | OI↑ fiyat↑ güçlü yükseliş · OI↑ fiyat↓ güçlü düşüş · OI↓ fiyat↑ zayıf yükseliş (short kapanışı) · OI↓ fiyat↓ zayıf düşüş | N |
| SM-96 | Yüksek OI + aşırı pozitif/negatif funding = kalabalık; tersi riski | N |
| SM-97 | Yatay fiyatta OI sıçraması = büyük hareket yakın | N |
| SM-98 | **Veri (24 Kas indirildi):** Binance public data, BTC perp OI (2020-09-01'den, saatlik) ve funding (2020-01'den, 8 saatlik); `signals/data/derivatives.py`. Ölçüm: PROFESSIONAL.md 10 | Ö |

## 13. İlk ölçüm (kalibrasyon dönemi; BTC + altın + S&P, 1D + 4h; ücretsiz, onaysız)
Bölgeler: dersin girişi, stop bölgenin ötesi, hedef **2R** (yazı-tura %33). Aynı mumda stop önce.

| Kural | n | Başarı (%95) | Not |
|---|---|---|---|
| FVG ilk dokunuş | 2.610 | %32 (31–34) | yazı-turadan farksız; trend yönü de fark etmiyor |
| Order block 0,5 | 768 | %33 (30–37) | FVG + sweep birlikte %35 (30–41) |
| Breaker | 319 | %35 (30–40) | |
| Arz-talep | 546 | %33 (29–37) | **büyük yapı yönünde %37,5 (32–43), yapıya karşı %27 (22–33)** |
| SFP 4h | 485 | %36 (31–40) | büyük yapı yönünde %36 |
| SFP 1D | 297 | %28 (23–33) | onaysız günlük SFP zayıf |
| Range deviasyonu → EQ | 80 | %29 (20–39) | yazı-tura %31 |
| PO3 (BTC 1h) → karşı uç | 827 | %27 (24–30) | yazı-tura %33; 1.112 günün %26'sında karşı uca gidildi |

**Okuma:** tek başına hiçbiri yazı-turadan anlamlı ayrılmıyor. En belirgin iz **yön**: arz-talepte büyük yapı (3 × ATR) yönünde olmak 10 puan fark
yaratıyor (OB'de 4 puan, SFP'de 2, FVG'de yok). 24 karşılaştırma yapıldı, birkaçının şansa böyle çıkması beklenir: **hipotez**. "HTF > LTF" kuralı
(PA-07, E-97) birleşik ölçümde ilk sınanacak şey.

## 14. Kararlar (24 Kas)
HTF CHoCH + LTF MSB birlikte · breaker bölgesi fitilden gövdeye · PO3 saatleri · OI/funding indirildi. Hepsi Aykut'un onayı.

## 15. Kayıt
| Ders (İleri) | Not | Video |
|---|---|---|
| Price Action · Arz-Talep · Range · SFP · Breaker · Order Block · OTE · FVG · Kilit Seviyeler · PO3 · Open Interest · Likidasyon | ✅ | ✅ kareler (9'ar kare + yakın çekimler) |
| Risk Analizi (İleri) | ✅ → RISK.md | Başlangıç'taki videonun aynısı (1136 sn) |
