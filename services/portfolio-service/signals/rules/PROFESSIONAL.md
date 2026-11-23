# Profesyonel kural listesi (v1 taslak, 24 Kasım 2026)

Görseller: [pro-visuals.html](pro-visuals.html) — üstte çizim, altta kendi verimizdeki **en yeni** örnek (başarıya göre seçilmedi; stop olanlar da var).
Kod: `pro_detect.py`; OI/funding verisi: `signals/data/derivatives.py`. Tür ve kaynak işaretleri SMART_MONEY.md ile aynı (N not · V video · A Aykut · Ö öneri).

## 1. Hacim profili
| No | Tür | Kural | Kaynak |
|---|---|---|---|
| PR-01 | K | **POC** en çok işlem gören fiyat; **değer alanı** hacmin %70'i; VAH / VAL sınırları | N, V |
| PR-02 | K | Kod: 60 dilim, her mumun hacmi aralığına eşit dağıtılır (işlem bazlı veri yok → yaklaşık); seviyeler seans bitince bilinir | Ö |
| PR-03 | R | POC çeker; VAH/VAL destek-direnç; düşük hacim düğümünden (LVN) hızlı geçilir, yüksekte (HVN) oyalanılır | N |
| PR-04 | R | Değer alanının dışına çıkıp **geri dönmek** karşı sınırı hedefler; dışarıda kabul = devam (videoda VAL altı düşüş) | V'den okumam |

## 2. NPOC
| No | Tür | Kural | Kaynak |
|---|---|---|---|
| PR-10 | K | Naked POC: seans bittikten sonra fiyatın **hiç dokunmadığı** POC; dokununca biter | N, V |
| PR-11 | R | Hedef ya da tepki yeri; HTF > LTF, yakın > uzak, hacimli seans; başka seviyeyle birlikte | N |

## 3. RSI uyumsuzluğu
| No | Tür | Kural | Kaynak |
|---|---|---|---|
| PR-20 | K | Klasik (P.U / N.U) ve gizli (Trend Devam) tanımı RULES.md 3 ile **aynı** (SERS41 RSI) | N, V, A |
| PR-21 | R | Uyumsuzluk uyarıdır, sinyal değil: mum/yapı teyidi beklenir; HTF ve kilit seviyede güçlü; trend sonunda klasik, ortasında gizli | N |
| PR-22 | K | RSI kaynağı **hep kapanış** (SERS41). Videoda "yüksek" de deneniyor, kullanılmıyor | A onayı |
| PR-23 | K | Etiket pivottan 5 mum sonra kesinleşir; giriş ondan önce yapılamaz | RULES.md |

## 4. Likidite işlemleri
| No | Tür | Kural | Kaynak |
|---|---|---|---|
| PR-25 | R | Havuzlar: tepe/dip, EQH/EQL, range uçları, trend çizgisi; süpürme → teyit (SFP/engulfing) → ters yön; hedef karşı havuz | N |
| PR-26 | – | Likidasyon haritası (Coinglass) kullanılıyor; **açık veri yok**, tahmini bir modeldir. Kodlanmadı | V |

## 5. İleri imbalance
| No | Tür | Kural | Kaynak |
|---|---|---|---|
| PR-30 | K | Durumlar: dokunulmadı · kısmi · %50 · tam doldu (tam dolunca zayıf) | N |
| PR-31 | R | En iyi giriş %50; FVG + OB birlikte, HTF yönünde, yapıyı **kıran** hareketin bıraktığı FVG | N, V |
| PR-32 | R | Zincirde ilk FVG önce dolar; diptekiler daha güçlü | N |

## 6. CVD ve emilim
| No | Tür | Kural | Kaynak |
|---|---|---|---|
| PR-40 | K | CVD = alıcı − satıcı (agresif) hacim toplamı. Fiyat ↑ CVD ↓ zayıf yükseliş; fiyat ↓ CVD ↑ zayıf düşüş | N |
| PR-41 | – | Videoda spot ile vadeli CVD ayrı izleniyor; bizde yalnız **Binance spot** var | V |
| PR-42 | K | Emilim: fiyat yerinde, delta güçlü. Kod: 12 mumda \|değişim\| ≤ aralığın %25'i, delta olağanın 2 katı | N + Ö |

## 7. CME gap
| No | Tür | Kural | Kaynak |
|---|---|---|---|
| PR-50 | K | Cuma kapanışı (16:00 Chicago) – Pazar açılışı (17:00) farkı. **29 Mayıs 2026'dan beri CME kripto 7/24: yeni hafta sonu gap'i oluşmuyor.** Not bunu bilmiyor | N + W (CME duyuruları) |
| PR-51 | R | Eski dolmamış gap'ler seviye olarak kalabilir; plan üretmez | Ö |

## 8. SFP planı
| No | Tür | Kural | Kaynak |
|---|---|---|---|
| PR-60 | K | HTF tepe/dip süpürülür (SFP) → LTF'de **MSB** → fib: 1 = SFP ucu, 0 = kırılımın gittiği uç → **0,618–0,66** bölgesine dönüşte giriş (kod 0,639) · **stop SFP ucunun ötesinde mesafeyle** (derste 142 $ = hareketin **%4'ü**) · hedef **0**. R/R ≈ 1,54–1,59 | V + A (görüntü) |
| PR-60a | K | Süpürülen seviye **en son tepe olmak zorunda değil**: oluştuğundan beri geçilmemiş her HTF tepe/dip sayılır (derste 4 haftalık 94.588,99). Kod: `find_open_sfps` | V |
| PR-60b | R | Küçük yapının MSB'si ilk tepkiyi, büyük dibin kırılması asıl planı verir | V |
| PR-60c | R | Kırmızı bant 0,618–0,66 ile aynı yerde. Kendi verimizde o bantta 06.01 düşüşünün bıraktığı FVG (93.423–93.548 ve 93.592–93.780) ile 05.01 yükselişinin OB'si (93.250–93.703) var. 15m'de o aralığa denk gelen 16 bölge bulundu: **çakışma kolay, güçlü kanıt değil** | M |
| PR-61 | R | 4H ve üstü, hacimli, trend yönünde, EQH/EQL süpürmesinde; stop fitil + 1 ATR; hedef 2–3R | N |
| PR-62 | – | **Notun iç tutarsızlığı:** %55–65 başarı + 1:2,5 R/R, profit factor **3,1–4,6** demektir; not 1,8–2,2 yazıyor. Veri ve dönem verilmemiş | M |

## 9. Funding ve diğerleri
| No | Kural | Kaynak |
|---|---|---|
| PR-70 | Funding nötr ±%0,01; ≥ +%0,05 aşırı long (düşüş riski), ≤ −%0,05 aşırı short (yükseliş riski). Tek başına sinyal değil | N |
| PR-71 | TOTAL / TOTAL2 / TOTAL3, BTC.D, USDT.D: sermaye rotasyonu. BTC.D ↑ altcoin zayıf; USDT.D ↑ risk kaçışı. **Veri yok**; bizim varlıklar BTC, altın, S&P | N, V |
| PR-72 | Hedge: koruma aracıdır; haber öncesi %20–80, risk geçince kapatılır. Opsiyon: çıplak satış yok. 4.4 kapsamı dışında | N |
| PR-73 | AI aracı (Kiyotakia): yardımcı, karar verici değil; her zaman teyit. Bizim "AI sadece açıklar" ilkesiyle aynı | N |

## 10. İlk ölçüm (kalibrasyon dönemi, ücretsiz, onaysız)
"Kontrol" = fiyatın **öbür yanında aynı uzaklıkta** sahte seviye. 2R hedefte yazı-tura %33.

| Soru | Sonuç |
|---|---|
| NPOC mıknatıs mı? (günlük, 1.458 POC) | 7 günde %80 dokunuldu; **kontrol %78**. 30 günde %89 / %89. POC'un önce gelmesi %51. **Mıknatıs etkisi yok** (1 günde %55 / %52) |
| Haftalık POC (246) | 7 günde %62, kontrol %64 |
| CME gap dolumu (≥ %0,5, 234 gap) | 7 günde %71, 30 günde %83, 1 yılda **%94**. Notun "%90+"ı doğru ama **kontrol de %93**: fiyat yakın her seviyeye eninde sonunda gider |
| SFP 4h / 1h / 1d | %36 (485) / %33 (2.168) / %28 (297). Stop + 1 ATR: %33 / %32 / %30 |
| SFP, EQH/EQL süpürmesi | %35 (327; 30–40) |
| SFP planı (PR-60, derstekinin aynısı; R/R 1,59 → yazı-tura %39) | 1h SFP → 15m MSB **%35** (1.156; 33–38), 4h → 15m %35 (333; 30–40), 1d → 15m %25 (60; 16–37). Büyük yapı yönü fark etmiyor. **Onaysız hali yazı-turanın altında** |
| RSI uyumsuzluğu | 1h %33 (704), 4h %33 (160), 1d %32 (148); aynı dipte SFP ile 1h %36 (273; 30–41), 4h %34 (65) |
| RSI 4h, büyük yapı yönünde | %43 (n **40**; 29–58), ters yönde %30 (120) |
| CVD uyumsuzluğu (BTC) | 1h %35 (684), 4h %31 (149) |
| FVG %50 girişi | %24 (2.488); FVG + OB yan yana %28 (468; 24–32). İlk dokunuştan (%32) **kötü** |
| OI / fiyat çeyrekleri (1.247 gün) | Not "OI↑ fiyat↑ güçlü" diyor; ertesi gün yukarı **%43** (38–48), genel %50. Diğerleri %51–54 |
| Funding | negatifken 3 gün sonra yukarı %60 (n 162; 52–67), genel %55; en yüksek %10'da %50 (86). ≤ −%0,05 yalnız 12 kez: eşik bu veride neredeyse hiç oluşmuyor |
| Emilim → 24 saat | %51 (341): yok |

**Kendi hatam (önemli ders):** ilk denemede "SFP eşit tepe/dip" **%43** (n 728) çıktı. Sebep geleceğe bakmaydı: eşit tepenin ikinci ucu SFP'nin kendisiydi ve ancak
fiyat döndükten sonra "tepe" oluyordu (o alt grup tek başına %60). Çift süpürmeden **önce** tamamlanmış olma şartıyla %35. Videolarda ve elle backtest'te de aynı
tuzak vardır: grafiğe sonradan bakınca yalnız dönen süpürmeler "eşit tepe" görünür.

**Okuma:** tek tek kurallar yazı-turadan ayrılmıyor. Hipotez olarak not edilenler: büyük yapı yönü (RSI 4h, arz-talep), RSI + aynı dipte SFP, negatif funding'de
yükseliş, OI↑ fiyat↑ günlerinden sonra zayıflık. ~50 karşılaştırma yapıldı; birkaçı şansla böyle çıkar. Birleşik ölçümde ve dokunulmamış dönemde sınanacak.

## 11. Dersteki işlem kendi verimizde (PR-60 doğrulaması)
| | Ders (Aykut'un görüntüsü) | Kod (Binance verimiz) |
|---|---|---|
| Süpürülen tepe | 94.588,99 | 94.588,99 (9 Aralık) |
| SFP ucu (1) | 94.789,08 | 94.789,08 (5 Ocak) |
| 0 | 91.264,6 | 91.262,9 |
| Giriş | 93.505,5 (0,636) | 93.516 (0,639) |
| Stop | 94.930,8 | 94.930 |
| Kırılan seviye | ~93.264 (görüntüden okuma) | 93.138 (2 × ATR ZigZag) |

İşlem 06.01.2026 21:15 UTC'de doldu; dip 89.311'e indi, hedef geldi. **Not:** Ocak 2026 dokunulmamış test dönemindedir; bu tek örnek kuralı anlamak için kullanıldı,
kural buna göre ayarlanmadı (0,639 ve %4 doğrudan dersten). Önceki hata: kod yalnız en son tepeyi izlediği için bu işlemi bulmuyordu.

## 12. Kayıt
| Ders (Profesyonel) | Not | Video |
|---|---|---|
| Hacim-Fiyat · NPOC · RSI Uyumsuzlukları · Likidite İşlemleri · İleri Imbalance · CVD · CME Gap · Total · SFP Backtest · Kiyotakia | ✅ | ✅ kareler |
| Funding & Likidasyon Haritası · Hedging · Opsiyon | ✅ | video yok |

**Dersler tamam:** Başlangıç 5, Orta 9, İleri 13, Profesyonel 13 = 40 ders.

Kaynak (PR-50): CME Group duyuruları 19.02.2026 ve 01.06.2026 ("24/7 Cryptocurrency Futures and Options").
