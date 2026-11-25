# Risk, psikoloji, backtest ve takvim kuralları (v1 taslak, 24 Kasım 2026)

Kaynak: Dersler → **Başlangıç** (5 ders) + Orta'dan Backtest ve Makro. N = not, V = video kareleri, M = hesap, Ö = öneri.
Grafik kuralı olmadığı için görsel yok; formüller örnekle doğrulandı.

## 1. Risk
| No | Kural | Kaynak |
|---|---|---|
| RK-01 | İşlem başına risk hesabın en çok **%1–2**'si | N |
| RK-02 | Miktar = (hesap × risk %) / \|giriş − stop\|. Örnek: 10.000 × %1 / 2.000 = 0,05 BTC. (Komisyon ve kayma paydaya eklenir: E-98) | N + B9 |
| RK-03 | R/R en az 1:1,5 (25 Kas, Aykut; derslerde 1:2), iyisi 1:3 | N |
| RK-04 | Başabaş oranı = 1 / (1 + R/R): 1:1 → %50, 1:2 → %33, 1:3 → %25. Notla uyumlu (1:2'de %40 kârlı, 1:1'de %40 zararlı) | N + M |
| RK-05 | Stop'suz işlem yok; günlük kayıp sınırı %2–3, haftalık %5–6; ulaşınca dur | N |
| RK-06 | Kaybı geri almak daha çok kazanç ister: −%10 → +%11, −%50 → +%100 | V + M |
| RK-07 | Risk sabitken işlemler R ile toplanır (videoda ardışık işlemler toplam 14R) | V |
| RK-08 | Kaldıraç: başlangıç 3–5×, tecrübeli 5–10×, 20× üstü yok; izole marjin | N |
| RK-09 | Likidasyon ≈ giriş × (1 ∓ 1/kaldıraç). **Yaklaşık:** gerçekte bakım marjini yüzünden daha yakındır | N + M |

**Düzeltme:** notta "%10 riskle 10 kayıp = −%100" yazıyor; sabit tutarla öyle, **kalan hesabın %10'u** ile 10 kayıp −%65'tir (0,9¹⁰ = 0,349). %1'de −%9,6.

## 1b. İleri risk
| No | Kural | Kaynak |
|---|---|---|
| RK-10 | Aynı yöne giden varlıklar tek risk sayılır (BTC long + ETH long = iki kat) | N |
| RK-11 | Oynaklık (ATR) artınca miktar küçülür | N |
| RK-12 | Kelly = (kazanma % × ort. kazanç − kaybetme % × ort. kayıp) / ort. kazanç; pratikte %25–50'si. Küçük örnekten Kelly hesaplanmaz | N + M |
| RK-13 | Düşüş: %10 normal, %20'de miktar yarıya, %30'da dur | N |

## 2. Psikoloji (kontrol listesi)
| No | Kural |
|---|---|
| RK-20 | İşlemden önce 5/5: tanımlı ve test edilmiş kurulum · R/R ≥ 1:1,5 · kesin stop · kaybı kabul · plan içinde (FOMO değil) |
| RK-21 | Günde en çok 3 işlem; üst üste 2 kayıptan sonra o gün bitti; kayıptan sonra en az 1 saat ara |
| RK-22 | Kazanırken de aynı kurallar; süreç sonuçtan önemli; günlük tutulur |

## 3. Backtest (bizim yöntemle karşılaştırma)
| No | Ders | Bizde |
|---|---|---|
| RK-30 | Kural net ve ölçülebilir olmalı | ✅ numaralı kurallar |
| RK-31 | En az 100 işlem ya da 1 yıl; ideali 200+ ve 2–3 yıl, yükseliş/düşüş/yatay | ⚠ harmonikte 47; yetersizse "sonuç çıkmaz" yazılıyor |
| RK-32 | Profit factor 1,5+ iyi; en büyük düşüş %20'den az | ❌ rapora eklenecek (bugün: başarı, ort. R, en kötü seri) |
| RK-33 | Geleceği bilme ve aşırı uydurma yok; az parametre | ✅ kesinleşme indeksi, kalibrasyon / dokunulmamış test |
| RK-34 | Spread ve kayma dahil | ⚠ ücret var, kayma yok |
| RK-35 | İleri test (canlı izleme) | ❌ backtest'ten sonra |

Notta %60+ başarı için "gerçekten mi?" deniyor; bizim ölçümlerde **yazı-tura karşılığı** hep yanına yazılır.

## 4. Makro takvim
| No | Kural |
|---|---|
| RK-40 | Birinci derece olaylar: **FOMC** (yılda 8), **CPI** (ay ortası), **NFP** (ayın ilk Cuması) |
| RK-41 | Piyasayı rakam değil **beklentiden fark** oynatır. Şahin/yüksek enflasyon → düşüş, güvercin/düşük → yükseliş (genelleme, kesin değil) |
| RK-42 | Olay günü yeni işlem yok; açık işlem küçültülür ya da korunur |
| RK-43 | Bizde: takvim verisi yok (Market Data'ya Faz 5'te eklenebilir). Plan çıktısına "olay günü" uyarısı; E-101 ile uyumlu |

## 5. Kayıt
| Ders (Başlangıç) | Not | Video |
|---|---|---|
| Temel TradingView | ✅ | ✅ kareler, arayüz turu (kural yok) |
| İleri TradingView | ✅ | ✅ kareler, fib ayarları ve şablon (kural yok). Önerilen düzen: 1W+1D+4H eğilim, 4H+1H+15M giriş |
| Kaldıraçlı İşlemler | ✅ | ✅ kareler, borsa ekranı |
| Risk Analizi | ✅ | ✅ kareler, pozisyon aracı |
| Trade Psikolojisi | ✅ | video yok |
| Risk Analizi (İleri) | ✅ | Başlangıç'taki videonun aynısı |
