# 4.4 "AInvest görüşü" — kural tanımı (taslak v0, 23 Kasım 2026)

Bu dosya kodun neyi, nasıl aradığını tanımlar. Kod bu dosyaya uyar; bir kural değişirse önce burası değişir.
Kural seti IQ gibi **sürümlü** olacak: her kuralın puanı backtest'teki gerçek başarı oranından gelir (kalibrasyon),
"7/10" gibi güven metni de oradan. Bu ilk sürümde puanlar yok; önce tespit (detector) kodu yazılıyor.

**İlke:** formasyon tek başına sinyal değildir. Elliott ve harmonik **nerede** bakılacağını (bölge), SFP + uyumsuzluk +
kapanış **ne zaman** dönüldüğünü söyler. Her plan bir **geçersizlik seviyesi** taşır. Her zaman ana + alternatif model.

Varlıklar: BTCUSDT, altın (GC=F), S&P (ES=F), hepsi USD. Veri ve temizlik: `signals/data/` (CLAUDE.md 5.8b).

## 1. Zaman dilimleri
| Rol | Dilimler |
|---|---|
| HTF (yön, bölge, dönüş kapanışı) | 1M, 1W, 3D, 1D, 12h, 6h, 4h (25 Kas) |
| LTF (onay: SFP, uyumsuzluk) | 2h, 1h, 45m, 30m, 15m |

Altın/S&P'de 15–45m yalnızca son ~60 gün var; uzun backtest'te LTF onayı bu varlıklarda 1h ile yapılır (o da ~2 yıl; öncesi için onay ölçülemez).

## 2. Tepe/dip
- **Pivot** (TradingView `ta.pivothigh/pivotlow` mantığı): bir mum, solundaki `L` ve sağındaki `R` mumdan daha yüksek
  (düşük) ise tepe (dip). Varsayılan L = R = 5. Pivot ancak sağdaki R. mum kapanınca **kesinleşir** (bilinir).
  Kullanım: SFP'nin süpürdüğü "son dip/tepe", uyumsuzluk.
- **ZigZag (ATR)**: son dipten beri görülen en yüksekten fiyat `k × ATR(14)` kadar dönünce o en yüksek tepe olur
  (tersi dip için). Tepe-dip her zaman sırayla gelir. Varsayılan k: HTF ana yapı 3, alt yapı 1,5 (sonra ayarlanacak).
  Kullanım: Elliott dalgaları, harmonik X-A-B-C-D, Fibonacci bacakları.
- **Geleceği görmeme:** her tepe/dip iki zaman taşır: oluştuğu mum ve kesinleştiği mum. Replay ve backtest bir noktayı
  ancak kesinleştiği mumdan sonra kullanabilir.

## 3. LTF onayı
**SFP** (likidite süpürme), hangi dilimde bakılıyorsa o dilimin mumlarıyla:
- Boğa, tek mum: mum son kesinleşmiş dibin altına iner, aynı mum dibin **üstünde kapanır**.
- Boğa, iki mum: mum dibin altında kapanır, **hemen sonraki mum** dibin üstünde kapanır.
- Ayı: tersi (son tepenin üstü). Bir dip/tepe en fazla bir SFP üretir; altında/üstünde kapanıp ertesi mum geri
  dönmezse gerçek kırılım sayılır ve o seviye düşer.
- **Açık seviye SFP'si** (PR-60a): en son tepe değil, oluştuğundan beri geçilmemiş **her** tepe/dip (`find_open_sfps`); HTF planında bu kullanılır.

**Uyumsuzluk** — SERS41 RSI Divergence göstergesinin (© SERS41, MPL-2.0) birebir karşılığı, aynı dilimde:
- RSI 14 (Wilder, kapanış). Dip/tepe **RSI üzerinde** pivotla (5/5) bulunur; fiyat o mumların low/high'ından okunur.
  İki pivot arası 5–60 mum.
- **P.U** fiyat LL + RSI HL · **N.U** fiyat HH + RSI LH · **Trend Devam** (gizli): boğa fiyat HL + RSI LL,
  ayı fiyat LH + RSI HH. Etiket pivottan R mum sonra kesinleşir.
- **CVD** (yalnız BTC): mum başına delta = 2 × alıcı hacmi − toplam hacim, birikimli toplam. Aynı uyumsuzluk mantığı
  RSI yerine CVD ile.

**Güçlü LTF onayı** = aynı dipte/tepede SFP + P.U/N.U. Aynı yapı 4h/1D/1W'de oluşursa HTF sinyalidir (derin düzeltme).

## 4. Fibonacci
> Aykut'un dört aracı, kurallar ve ölçüm: [rules/FIBONACCI.md](rules/FIBONACCI.md). Aşağısı v0 kodunundur.

- Oranlar: 0,382 · 0,5 · 0,618 · 0,786 · 1 · 1,272 · 1,414 · 1,618 · 2,618 · 3,618 · 4,618 (+ harmoniklerde 0,886, 1,13, 2,0, 2,24, 3,14).
- Retracement (A→B): B − r × (B − A). Trend-based extension (0-1-2): 2 + k × (1 − 0).
- **Tolerans ±%3 göreli** (0,786 → 0,762–0,810). Bölge = birden çok seviyenin üst üste bindiği aralık.

## 5. Elliott
> Numaralı tam kural listesi (kesin / kılavuz, kaynak, çelişkiler, kod durumu): [rules/ELLIOTT.md](rules/ELLIOTT.md),
> görseller: `rules/elliott-visuals.html`. Aşağıdaki özet v0 kodunun kullandığıdır; kod değişince güncellenir.

**Kesin kurallar** (bozulursa aday elenir):
1. Dalga 2, dalga 1'in başlangıcını geçemez.
2. Dalga 3, 1-3-5 içinde en kısa olamaz (diyagonaller dahil).
3. Dalga 4, dalga 1'in tepesine giremez (diyagonal hariç).
4. Üçgen 2. dalgada olamaz (4, B, X'te olur).
5. Zigzag'da B, A'nın başlangıcını geçemez.

**İtki tipleri ve hedefler** ([n] = n. dalganın fiyat boyu):
| | 3. uzayan | 5. uzayan | 1. uzayan |
|---|---|---|---|
| Tanı | [3] ≥ 1,618 [1] | [1] ≈ [3] | [1] en uzun, [3] ≈ [5] |
| [2] | [1]'in 0,382/0,5/0,618'i | aynı | aynı |
| [4] | [3]'ün 0,236–0,382'si (ideal 0,382) | aynı | aynı |
| [5] hedefi (4'ten) | = [1] veya 0,618 [3] | 1,618 × (0→3), alt. 1,618 [1] | 0,618 [3] … [3] ([5] = [1] olamaz: 3 en kısa kalır, E-14) |
| Not | [3] > 2,618 [1] → güdük 5 riski (~0,618 [1], yeni tepe yok) | | |

- Dalga 3 hedefi: 0-1-2 trend extension (1 · 1,618 · 2,618). Dalga 5 bölgesi: 2-3-4 extension (0,618 · 1 · 1,618) +
  "[5] = [1]" (+ 5. uzayanda 1,618 × (0→3)); bindikleri yer bölge.
- **Alternasyon:** 2 sert/kısa ise 4 yatay/uzun (fiyat ve süre).

**Düzeltmeler**
| Yapı | Kural / oran |
|---|---|
| Zigzag 5-3-5 | B = A'nın 0,382 (en sık) / 0,5 / 0,618'i; **B ≥ 0,786 ise şüpheli, yassıya da bak** (kesin sınır: B, A'nın başını geçmez); C ≈ A veya 1,618 A |
| Flat 3-3-5 | B = A'nın %90–138,2'si; C = A'nın %100–161,8'i; normal: B ≈ A başı, C ≈ A; genişleyen flat tepe geçişlerinde |
| Üçgen 3-3-3-3-3 | daralan; D genelde B'yi geçmez; E kısa/sahte kırılım olabilir; çıkış trend yönünde sert |
| W-X-Y, W-X-Y-X-Z | karmaşık yapı: **plan üretilmez**, netleşmesi beklenir |
| Diyagonal | 5 dalga, alt dalgalar çoğunlukla 3'lü, 4 ile 1 çakışır, daralan kanal, 5 çizgiyi aşabilir; trend sonunda dönüş işareti |

**İşlem bölgeleri:** güvenli: 2. ve 4. dalga bitişi (B/X sonları). Riskli: 3'ün ortası, 5'in sonu. 5. dalga tepesinde
ters yön (short) planı bu yüzden en sıkı onayı ister: bölge + LTF SFP + N.U + HTF kapanış; güdük 5 veya bitiş diyagonali
ek puan.

## 6. Harmonik (Carney, harmonictrader.com)
> Numaralı kurallar, gözden geçirme bulguları ve görseller: [rules/HARMONIC.md](rules/HARMONIC.md). Aşağıdaki tablo v0 kodunundur.

| Formasyon | B (XA) | D (XA) | BC uzatması | AB=CD | Geçersizlik (XA) |
|---|---|---|---|---|---|
| Gartley | 0,618 | **0,786** | 1,27–1,618 | ≈ 1,0 | 1,0 (X) |
| Bat | < 0,618 (tercihen 0,382–0,5) | **0,886** | 1,618–2,618 (1,27 olamaz) | ≥ 1,0, genelde 1,27 | 1,13 |
| Alternate Bat | ≤ 0,382 | **1,13** | 2,0–3,618 | 1,618 | 1,272 |
| Butterfly | **0,786** (zorunlu) | **1,27** | 1,618–2,618 | 1,0–1,27 | 1,414 |
| Crab | 0,382–0,618 | **1,618** | 2,24–3,618 | 1,27 / 1,618 | 2,0 |
| Deep Crab | **0,886** (X'i geçmez) | **1,618** | 2,24–3,618 | genelde 1,27 | 2,0 |

Hepsinde: C = AB'nin 0,382–0,886'sı; CD ≥ AB. PRZ = D'yi tanımlayan XA seviyesi + BC uzatması + AB=CD'nin bindiği aralık.
Geçersizlik seviyeleri Carney'nin değil, bizim önerimiz (backtest ile ayarlanacak). Shark, 5-0, Cypher ilk sürümde yok.

Kanıt notu: hakemli çalışma yok; blog backtest'leri karışık (ES 15m 2020–2024: Butterfly en iyi, Gartley umut verici,
Bat yazı-tura, Crab zararlı; aynı formasyon altında farklı sonuç). Puanlar bu yüzden kendi backtest'imizden gelecek.

## 7. Dönüş onayı (kapanış) ve geçersizlik
- **HTF:** bölgeye ilk dokunuştan sonraki 5 günlük mum içinde günlük kapanış bölgenin dönüş tarafında (tepede bölgenin
  altında, dipte üstünde). Haftalık kapanış da öyleyse ek puan.
- **LTF:** 1h ve altında SFP + P.U/N.U (SFP kapanışı kendi mumunda).
- **İptal:** Elliott kesin kuralı **fitille** bozulur ve plan biter (E-94, E-102); öbür geçersizlikler kapanışla. Planda ayrıca mikro geçersizlik ve
  "key level" (modelin teyit edildiği seviye) yazılır.

## 8. Çıktı (plan)
Piyasa görüşü (ör. "spot alım için uygun değil, short için uygun") + varlık başına koşullu plan: izlenecek HTF bölgesi,
yön, aranacak LTF onayı, geçersizlik / mikro geçersizlik / key level, ana ve alternatif model, onay puanı (≥ 70 → işlem
planı) ve backtest'ten gelen güven metni + "YTD" uyarısı. Rakamları kod üretir; AI servisi yalnızca açıklar.

## 9. Backtest ve puanlama raporu (her kural için yayımlanır)
Her kuralın puanı ve "7/10" gibi güven metni bu tablodan gelir; tablo kodla üretilir ve tekrar üretilebilir
(aynı `manifest.json` → aynı sonuç). Görüşmede ve tezde bu tablo gösterilir.

| Sütun | Anlamı |
|---|---|
| Kural / kombinasyon | ör. "Elliott 5. dalga bölgesi + 1h SFP + N.U + günlük kapanış" |
| Varlık, dilim | BTCUSDT 1D/1h, GC 1D/4h, ... |
| Dönem | **kalibrasyon** (in-sample, kural ve puan seçilir) ve **dokunulmamış test** (out-of-sample, sadece raporlanır) ayrı |
| Örnek sayısı | kaç kez oluştu (az örnek → güven metni "yetersiz veri") |
| Başarı oranı | hedefe geçersizlikten önce ulaşma payı, %95 güven aralığıyla |
| Ortalama getiri / risk | R katı (hedef/stop), en kötü seri |
| Karşılaştırma | aynı dönemde: işlem yapmamak, al-tut, rastgele giriş |
| Veri kaynağı | Binance public data / Yahoo (yfinance), indirme tarihi, SHA-256 (manifest) |
| Kural kaynağı | Frost & Prechter, Carney, TraderLex, kullanıcı eğitimi (hangi madde) |

Yöntem: walk-forward (zamanda ileri giden pencereler), geleceği görmeme (her nokta kesinleştiği mumdan sonra),
işlem maliyeti dahil. Kalibrasyon tablosu → kural puanı; toplam onay puanı ≥ 70 → plan; puan kovasının gerçek başarı
oranı → güven metni.

## Kaynaklar
- R. N. Elliott; A. J. Frost & R. R. Prechter, *Elliott Wave Principle* (kesin kurallar, oran kılavuzları).
- TraderLex, *Elliott Dalga Teorisi Temelli Trade Kılavuzu* (kullanıcının eğitim materyali; metin kopyalanmadı).
- S. M. Carney, harmonictrader.com ve *Harmonic Trading* cilt 1–3 (harmonik oranlar).
- SERS41, *RSI Divergence* (TradingView, MPL-2.0) — uyumsuzluk mantığı.
- anupshinde.com, "Backtesting the four classical harmonic patterns" (2026); liberatedstocktrader.com testleri.
