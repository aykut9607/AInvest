# Financial IQ skorlaması v3: öneri, ölçüm ve aktarım şartnamesi

**Hazırlayan:** Ahmet (Claude ile), 24 Kasım 2026; 25 Kasım'da `WEALTH_RUNWAY` etiket kuralı düzeltildi (Bölüm 8.6).
**Okuyucular:** Ahmet, Aykut (IQ servisinin sahibi), danışman.
**Durum:** v3c-i5 24 Kasım'da kabul edildi (Bölüm 10) ve C#'a aktarıldı. Bu belgedeki v2 ölçümleri aktarımdan önce, 24 Kasım'da alındı.

Bu belgede v2'nin denetimde bulunan açıkları, bunlara önerilen v3 tasarımı ve v3'ün üretimdeki v2 ile karşılaştırması var. C# aktarımı için gereken şartname Bölüm 8'de.

| | |
|---|---|
| Prototip (v3 kuralları, referans) | `evaluation/iq_v3/scoring.py` |
| Nüfus ve problar | `evaluation/iq_v3/population.py` |
| Birim testleri (17) | `evaluation/iq_v3/test_scoring.py` |
| Değerlendirme | `evaluation/iq_eval_v3.py` → `evaluation/out/iq_v3_results.json` |
| Aktarım için altın tablo (52 profil, 6 varyant) | `evaluation/out/iq_v3_golden.json` |
| v2 ölçümleri (24 Kasım, aktarım öncesi; donmuş) | `evaluation/out/iq_v3_v2_frozen.json` |

---

## 1. Özet

- **v2'nin asıl sorunu yön değil, uçurum.** 48.789 tek girdili değişiklikte (gelir dahil, olumlu ve olumsuz) v2'de hiç monotonluk ihlali çıkmadı. Ama 1 TL'lik değişiklik skoru 100 puan oynatabiliyor. Örnekler: yatırım +1 TL ile 0 → 100, borç +1 TL ile 75 → 0. Ayrıca 104 yıllık gelir kadar borcu olan biri 75 alıyor ve 59 puana kadar kayıp uyarısız kalabiliyor.
- **v3** basamak yerine doğrusal enterpolasyon kullanıyor, TL eşiği içermiyor ve hiçbir girdiyi iki kez saymıyor. Aşırı durumları sürekli bir **ödeme gücü tavanı** ve **servet pisti** karşılıyor. Bir faktör puanının %60'ının altına düşerse uyarısı mutlaka çıkıyor.
- **Ölçülen etki (v2 → v3):**
  - ±%1 değişiklikte en büyük sıçrama 100 → 4, p99 8 → 2.
  - Eşik problarında (1 TL) en büyük sıçrama 75 → 0–1.
  - Monotonluk ihlali 0 → 0.
  - Uyarısız en düşük skor 41 → 67–73. Tasarım gereği hiçbir zaman 60'ın altına inmiyor.
  - v2 ile sıra korelasyonu (Spearman) 0,95–0,96: kullanıcıların sırası büyük ölçüde korunuyor.
- **Önerimiz: v3c-i5.** v3b düzeninde (gider oranı yok, borç ikiye ayrılmış), ağırlıkları kanıtın gücüne göre: Rezerv 30, Taksit 25, Net borç 10, Tasarruf 30, Sabırsızlık 5.
  - Gider oranının çift sayımını kaldırıyor. YÖK raporu da bunu açık olarak işaretlemişti.
  - Kendi beyanı olan sabırsızlığın ağırlığını yarıya indiriyor. Bu, danışmanın 2. notuyla (beyana dayanma) uyumlu.
  - Kalibre nüfusta LOW payı %24,9, Eurostat'ın "beklenmedik harcamayı karşılayamaz" payı %25,1. HIGH payı %26,3, Findex'in "2 aydan uzun idare eder" payı %22,3.
  - Bedeli: mobil ve AI'daki faktör tabloları değişir. AI ve sözleşme v3 için zaten değişmek zorunda olduğundan ek maliyet küçük.
  - Faktör anahtarlarına hiç dokunmak istenmezse **v3a** (v2'nin 5 anahtarı ve maksimumları aynen) yedek seçenek. v3a uçurumları da kapatıyor, ama gider oranının çift sayımı sürüyor, hatta artıyor.

---

## 2. v2'de bulunan açıklar (denetim, kısaca)

| # | Açık | v2'deki örnek (gelir/gider/taksit/borç/nakit/yatırım/sabırsızlık) |
|---|---|---|
| G1 | Kural uçurumları (100 puana kadar) | 30k/6M/1M/0/0/9.999.999/5 için yatırım +1 TL: 0 → 100. 40k/16k/4k/100.095.999/96k/0/1 için borç +1: 75 → 0 |
| G2 | 100 kuralları nakit akışına bakmıyor | Gelir 1M, gider 2M → 100, uyarı yok |
| G3 | Borç cezası 25 puanla sınırlı | 40k/16k/4k/50M/96k/0/1 → 75 HIGH (net borç ≈ 104 yıllık gelir) |
| G4 | Nakit/yatırım iki kez sayılıyor (rezerv + borçtan düşme) | 96k borç alıp nakit tutmak: 70 → 95 |
| G5 | Ucuz oyun | Sabırsızlık beyanı 10 puan. Gider 0 + 0,01 TL nakit → 100 |
| G6 | Basamak uçurumları | 10k/4000/4000/0/24k/0/1 için gider +1: 75 → 49 |
| G7 | Gider oranı tasarrufu tekrar sayıyor | gider/gelir = 1 − tasarruf − taksit/gelir; gider 65 puanı yönetiyor |
| G8 | Rezerv paydasında taksit yok | 20k/5k/7k/0/30k → 78 HIGH (çıkış 12k sayılsa 61) |
| G9 | Borç tutarlılığı yok | Taksit faizi karşılamıyor ama skor 95+. Borç 0'ken taksit kabul (demo verisi) |
| G10 | Uç durumlar | Gider 0 ve nakit 0 → rezerv 0, nakit +1 TL → tam puan. Gelir 1 TL → HIGH. Gelir 0 reddediliyor |
| G11 | Uyarı ile puan tutarsız | Uyarısız 59 puana kadar kayıp, uyarısız en düşük skor 41 |
| G12 | Sabit TL eşikleri | %30 enflasyonla her yıl anlamı kayıyor |
| G14 | Eski değerlendirme eksik | Gelir hiç değişmiyor, olumsuz değişiklik yok, borç taksite bağlı, kural bölgesi yok, sıçrama ölçüsü yok |

---

## 3. v3 tasarımı

### 3.1 İlkeler
1. **Basamak yok, doğrusal enterpolasyon var.** Her faktör, bir çapa tablosundan okunan 0–1 arası bir paydır. Faktör puanı maksimum × pay ile bulunur ve her faktör ayrı ayrı tam sayıya yuvarlanır. Skor yuvarlanmış faktörlerin toplamıdır; böylece AI servisinin "faktörler skora eşit" kontrolü geçerli kalır.
2. **Çapa merdiveni.** Her faktörde dört basamak var: literatürdeki *ideal* eşik → %100, *yeterli* → %60 (uyarı çizgisi), *kırılgan* → %20, *çöküş* → %0. Güçlü dayanaklı eşikler korundu: 3 aylık fon, taksit ≤%10/≤%20, tasarruf ≥%10, %36 kırılganlık (Greninger vd. 1996, Delphi). Kısmen dayanaklı olanlar da korundu: 6 ay, tasarruf %20 (50/30/20), %36 (28/36 kuralı).
3. **Likit varlık tek tanım:** nakit + yatırımın %50'si (Basel LCR 2B kesintisi). Bu tanım rezervde, borçtan düşmede ve serveti ölçmede aynen kullanılıyor. Likit varlık önce acil fon hedefini doldurur (6 aylık çıkış). Yalnızca hedefin üstündeki kısım borçtan düşülür, böylece aynı lira iki kez sayılmaz (G4).
4. **Rezerv paydası = gider + taksit** (G8).
5. **Borç servisi en az faiz kadar.** Etkin taksit = max(taksit, %3,5 × net borç). Oran, IQ servisindeki `DebtPayoffRules` varsayımıyla aynı. Taksit faizi karşılamıyorsa borç büyüyor demektir. Bu durumda uyarı çıkar, ceza da etkin taksit üzerinden taksit oranına ve tasarrufa yansır (G9). Girdi asla reddedilmez.
6. **TL eşiği yok** (G1, G2, G12). Yerlerine iki sürekli mekanizma geldi:
   - **Ödeme gücü tavanı (κ):** net borç 5 yıllık gelirden 15 yıllık gelire çıkarken bütün faktörler 1'den 0'a doğrusal ölçeklenir. Gerekçe: gelirin %36'sı (kırılganlık sınırı) faizsiz ödense bile 5 yıllık borç ~14 yılda, 15 yıllık borç ~42 yılda kapanır. 42 yıl çalışma ömrünü aşar.
   - **Servet pisti (λ):** likit net servet (likit varlık − borç), yıllık giderin kaç katı? 25 yıl = %4 kuralı (Bengen 1994), yani finansal bağımsızlık. λ = pist/25 (en fazla 1). λ nakit akışı faktörlerini (tasarruf, taksit, v3a'da gider) en az λ × maksimuma kaldırır. Rezervi kaldırmaz, çünkü pist yarım yılı geçince rezerv zaten tam puandadır. Borç alıp nakit tutmak pisti değiştirmez, çünkü borç servetten düşülüyor.
   - `appliedRule` artık yalnızca açıklama etiketi: `SOLVENCY_CAP`, `WEALTH_RUNWAY` ya da `null`. Skoru kural koymuyor; skor her zaman faktörlerin toplamı. `WEALTH_RUNWAY` yalnızca pist en az 5 yıl olduğunda ve kaldırma gerçekten puan kazandırdığında yazılır (Bölüm 8.6). Kaldırmanın kendisi 0 yıldan başlar; bu eşik skoru etkilemez.
7. **Uyarı = puan.** Bir faktör maksimumunun %60'ının altındaysa (tavan öncesi puanla) uyarısı her zaman çıkar. %60 ve üstündeyse hiç çıkmaz. Tavanın götürdüğü puanı "Extreme total debt" uyarısı açıklar. Sonuç: uyarısız profil en az 60 alır ve bir faktör uyarısız en fazla maksimumunun %40'ını kaybeder (G11).
8. **Gider tabanı:** gelirin %10'undan düşük gider %10 sayılır ve veri kalitesi uyarısı çıkar. Gider 0'dan kaynaklanan sıfıra bölme uçurumunu (G10) ve "gider 0 + 0,01 TL nakit → 100" oyununu (G5) kapatır.

### 3.2 Varyantlar
| Varyant | Faktörler (maksimum) | Not |
|---|---|---|
| **v3a** | CashReserveMonths 25, DebtToIncomeRatio 25 (= min(taksit, net borç)), SavingsRate 25, ExpenseRatio 15, Impatience 10 | v2'nin anahtarları ve maksimumları aynen |
| **v3b** | CashReserveMonths 25, InstallmentToIncome 20, NetDebtToIncome 20, SavingsRate 25, Impatience 10 | Yol haritasındaki ayrım |
| **v3c** | CashReserveMonths 30, InstallmentToIncome 20, NetDebtToIncome 10, SavingsRate 30, Impatience 10 | v3b düzeni, ağırlıklar kanıtın gücüne göre |
| -i5 ekli | Sabırsızlık 5. Boşalan 5 puan v3a/v3b'de rezerve, v3c'de taksite gidiyor | **v3c-i5**: 30 / 25 / 10 / 30 / 5 |

v3b ölçüldükten sonra v3c'ye geçildi. Faiz tabanı altında net borç neredeyse hiç bağlayıcı değil: kalibre nüfusun %93,9'u net borç payını tam alıyor ve v3a'da net borç kısmı hiçbir profilde min()'i belirlemiyor. Bu yüzden v3b'nin 20 net borç puanı fiilen bedava. v3b'de ortalama skor 59,8'e, LOW payı %10'a çıkıyor (Bölüm 6). Net borcun eşikleri (0,5/1/3 yıl) zaten dayanaksızdı. v3c bu faktörü 10'a indirip puanı en güçlü dayanaklı iki faktöre (rezerv, tasarruf) veriyor.

---

## 4. Açık → çözüm → ölçülen etki

v3a / v3c-i5 değerleri `iq_v3_results.json`'dan (`regressionProbes`, `thresholdProbes`, `warnings`, `gaming`).

| # | v3'teki çözüm | v2 | v3a | v3c-i5 |
|---|---|---|---|---|
| G1 | TL kuralları yok; tavan ve pist sürekli | G1a 0→100, G1b 0→100, G1c 75→0, G1d 0→75 | 4→4, 0→0, 0→0, 0→0 | 14→14, 10→10, 0→0, 0→0 |
| G1 | Eşik problarında (TL kuralları dahil) 1 TL'nin en büyük etkisi | 75 | 1 | 0 |
| G2 | Nakit akışı yüksek gelirde de sayılıyor | gelir 1M, gider 2M: 100. Demo `richincome`: 100 | 31; 42 | 38; 53 |
| G2 | Servet, giderin kaç yılını karşıladığıyla ölçülüyor | 10M servet, aylık 6M gider: 100. Demo `richwealth`: 100 | 39; 75 (`WEALTH_RUNWAY`) | 48; 84 (`WEALTH_RUNWAY`) |
| G3 | Ödeme gücü tavanı | 75 HIGH | 0 (`SOLVENCY_CAP`) | 0 (`SOLVENCY_CAP`) |
| G4 | Yalnız hedefin üstü borçtan düşer | 70→95 | 71→92 | 68→93 |
| G4 | Nüfusta, taksit aynı kalırsa: ortalama / p90 / max kazanç | 9,2 / 15 / 15 | 6,3 / 11 / 15 | 7,9 / 14 / 18 |
| G4 | Nüfusta, 24 ay %3,5 taksitle: ortalama / p90 / max | −5,4 / 7 / 15 | −4,7 / 3 / 12 | −3,9 / 4 / 14 |
| G5 | Sabırsızlık 5→1 kazancı | 10 | 10 | 5 |
| G5 | Gider tabanı (gider 0 + 0,01 TL nakit) | 100 | 75 + "Expenses look too low" | 70 + aynı uyarı |
| G6 | Basamak yok | 75→49; 90→70 | 69→69; 91→91 | 67→67; 100→100 |
| G7 | v3a'da gider oranı duruyor; v3b/v3c'de kalktı. Gider~tasarruf puan korelasyonu | 0,76 | 0,87 (daha da artıyor) | yok (faktör kalktı) |
| G8 | Payda gider + taksit | 78 HIGH | 65 MEDIUM | 64 MEDIUM |
| G9 | Faiz tabanı + uyarı | Örnek 40k/12k/1k/100k/120k/0/2: 98 | 98 + "Installment below interest" | 99 + aynı uyarı |
| G9 | Aynı mekanizma, büyük borçta | Demo `highdebt`: 63 | 37 | 22 |
| G9 | Borçsuz taksit | sessiz | "Installment without debt" | aynı |
| G10 | Gider 0, nakit 0 → nakit +1 TL | 70→95 | 71→71 | 68→68 |
| G10 | Çok küçük tutarlar | gelir 1 TL: 90 | 93 (sınırlama, Bölüm 9) | 92 |
| G11 | Uyarı = puan | Uyarısız en düşük skor 41. Uyarısız en çok faktör kaybı 17 | 72; 10 (= maksimumun %40'ı) | 67; 12 (= 30'un %40'ı) |
| G12 | TL eşiği yok | 3 TL kuralı | Bütün tutarlar ×1,3 → döküm birebir aynı (birim testi) | aynı |
| G14 | Yeni değerlendirme | — | Bölüm 5 | — |

**Bilerek bırakılan iki kalıntı:**
- **G4, borç alıp nakit tutmak:** v3'te borçla alınan nakit rezerve sayılmaya devam ediyor. Bu, Greninger'in likidite oranındaki brüt likit varlık tanımı ve gerçek bir likidite. Ama artık borçtan düşülmüyor. Bedel taksit ve faiz tabanından geliyor: taksit dürüst bildirilirse ortalama kazanç negatif (−3,9 / −4,7), p90'da +3..+4.
- **G9, küçük borç:** faiz tabanının cezası gelire göre küçük kalıyorsa skor neredeyse değişmiyor (98). Kullanıcı yine de uyarıyı görüyor.

---

## 5. Değerlendirme yöntemi

```powershell
py -3 evaluation/iq_eval_v3.py                 # 2000 kalibre + 100 stres profili, seed 42, ~30 sn
py -3 evaluation/iq_eval_v3.py --calibrate     # yalnız nüfus / Türkiye karşılaştırması
cd evaluation; py -3 -m unittest discover -s iq_v3 -t . -v   # 17 test
```

- v2 skorları her zaman üretim kodundan geldi: `FinancialIqCommandManager.CalculateScore`, derlenmiş `FinancialIQ.BatchScorer` (Release) üzerinden. 24 Kasım'da tek çağrıda 62.982 profil skorlandı. v2'nin Python kopyası yok.
- **25 Kasım'dan beri BatchScorer v3c-i5'in C# aktarımını çalıştırıyor.** Betik, skorlayıcının yazdığı sürümü okuyor:
  - Sürüm v2 ise v2 sütununu canlı ölçüyor.
  - Sürüm v3 ise v2 sütununu `iq_v3_v2_frozen.json`'dan alıyor (24 Kasım ölçümleri; L1/L2 problarında v2 değeri yok). Ayrıca C# çıktısını Python v3c-i5 ile profil profil karşılaştırıyor (`csharpPortCheck`).
  - 25 Kasım sonucu, 63.026 profilde: skor, segment, faktörler ve uyarılarda **0 fark**. 702 `appliedRule` farkının hepsi bu düzeltme: C# eski kuralla `WEALTH_RUNWAY` yazıyor, prototip artık pisti 5 yılın altında olan bu profillerde `null` yazıyor.
- v3 skorları `iq_v3/scoring.py`'den. Bütün hesap `decimal` ile yapılıyor (C# `decimal` ile aynı mantık).

### 5.1 Nüfus (Türkiye paylarına kalibre)
2000 "çekirdek" profil, `realism_check.py`'nin satırlarına göre ayarlandı. Değerlendirmede kullanılan v2 nüfusunun aksine:
- gelir geniş bir aralıkta değişiyor (lognormal, medyan 40.000 TL, σ 0,72);
- borç taksitten bağımsız çekiliyor: kalan vade ve aylık faiz rastgele (%2–4,5), borç taksitlerin bugünkü değeri. Borcu olup taksiti olmayanlar ve taksiti olup borcu olmayanlar da var;
- nakdi düşük gelirlilerde daha kırılgan;
- yatırım sahipliği gelirle artıyor.

| Gösterge | Türkiye | Çekirdek nüfus | (Eski v2 nüfusu) |
|---|---|---|---|
| Beklenmedik harcamayı karşılayamayanlar (vekil: nakit < 1 ay gider; üst sınır) | %25,1 | %32,5 | %9 |
| 2 aydan uzun idare edenler, yalnız nakit | %22,3 | %22,4 | %79 |
| Aynısı, nakit + yatırım (üst sınır) | %22,3 | %42,1 | %95 |
| Tasarruf edenler (kaba) | %41,2 | %45,5 | %71,7 |
| Taksiti olanlar | %56,4 | %55,4 | %100 |
| Borçlananlar (kaba) | %64,7 | %64,2 | %100 |
| Borçlu başına ortalama borç | 156.000 TL | 149.181 TL | 545.919 TL |
| Gelirin alt %20 / üst %20 payı | %6,4 / %48 | %5,6 / %45,7 | %7,0 / %32,7 |
| S80/S20 | 7,5 | 8,2 | 4,7 |
| Hanehalkı tasarruf oranı (taksitin tamamı harcama sayılırsa; alt uç) | %14,3 | %10,4 | %17,9 |
| Karşılayamayanlar: düşük gelirli / diğerleri | 4,0 kat | 4,0 kat | 0,5 kat |

Nüfusu en çok etkileyen varsayımlar, hepsi `population.py`'nin başında:
- borcu olup taksiti olmayanlar: taksitsizlerin %24'ü;
- kalan vadenin medyanı 32 ay;
- yatırımcı oranı %15 + %40 × gelir sırası;
- sabırsızlık dağılımı: %12 / 22 / 32 / 20 / 14. Bunun için veri yok.

Ayrıca 100 **stres** profili var: çok yüksek gelir, büyük servet, aşırı borç, gizli borç (küçük taksit, büyük bakiye). Kalibre payları bozmasın diye ayrı tutuldular; v2'nin kural bölgelerini çalıştırıyorlar (v2: VERY_HIGH_INCOME 15, VERY_HIGH_WEALTH 13, EXTREME_DEBT 6).

### 5.2 Problar
- 11 demo profili: `seed_demo_users.py` ve playground hazır ayarları.
- 17 denetim örneği (G1–G10).
- 31 eşik çifti: v2'nin her basamağı, v3'ün her kırılma noktası (gider tabanı, faiz tabanı, tavan 5/15 yıl, pist 25 yıl) ve 3 TL kuralı. Her çiftte bir girdi 1 TL oynatılıyor.

### 5.3 Ölçüler
1. **Sıçrama:** tek bir girdi ±%1 değişince (girdi 0 ise +1 TL) skordaki mutlak değişim; en büyüğü, p99 ve p99,9.
2. **Monotonluk:** ±%1, ±%20, 0 → +1 TL, 0 → gelirin %10'u ve sabırsızlık ±1, hem olumlu hem olumsuz yönde, gelir dahil. Toplam 48.831 kontrol (v2: 48.789; L1/L2 probları sonradan eklendi). Olumlu değişiklik skoru düşürürse ya da olumsuz değişiklik yükseltirse ihlal sayılıyor.
3. **Oyun:** sabırsızlık 5→1; 3 aylık gider kadar borç alıp nakit tutmak (taksit aynı ya da 24 ay %3,5 annüite); gideri %10 eksik bildirmek.
4. **Uyarı tutarlılığı.**
5. **Spearman sıra korelasyonu.**
6. **Segment payları** (41/71 ve FinHealth 40/80).
7. Demolar yan yana.

---

## 6. Sonuçlar (çekirdek 2000 profil; sıçrama ve monotonluk bütün temel profillerde)

| Ölçü | v2 | v3a | v3b | v3c | v3a-i5 | v3c-i5 |
|---|---|---|---|---|---|---|
| ±%1 sıçrama: en büyük / p99 / p99,9 | **100** / 8 / 25 | 4 / 2 / 2 | 4 / 1 / 2 | 4 / 2 / 2 | 4 / 2 / 3 | 4 / 2 / 2 |
| Eşik probu (1 TL), en büyük | **75** | 1 | 1 | 0 | 1 | 0 |
| Monotonluk ihlali (v2 / 48.789; v3 / 48.831) | 0 | 0 | 0 | 0 | 0 | 0 |
| Sabırsızlık 5→1 kazancı | 10 | 10 | 10 | 10 | 5 | 5 |
| Borç alıp nakit tut, taksit aynı (ort / p90 / max) | 9,2 / 15 / 15 | 6,3 / 11 / 15 | 6,4 / 12 / 15 | 8,4 / 14 / 18 | 8,4 / 14 / 18 | 7,9 / 14 / 18 |
| Aynısı, 24 ay taksitle | −5,4 / 7 / 15 | −4,7 / 3 / 12 | −3,2 / 4 / 12 | −2,0 / 6 / 14 | −2,9 / 5 / 14 | −3,9 / 4 / 14 |
| Gideri %10 eksik bildir (ort / p90 / max) | 4,6 / 13 / **25** | 5,1 / 11 / 14 | 3,9 / 10 / 12 | 4,7 / 12 / 14 | 5,2 / 11 / 15 | 4,7 / 12 / 14 |
| Uyarısız en düşük skor | 41 | 72 | 69 | 67 | 73 | 67 |
| Uyarısız en çok faktör kaybı | 17 | 10 | 10 | 12 | 12 | 12 |
| Spearman, v2 ile | 1 | 0,959 | 0,953 | 0,953 | 0,951 | 0,948 |
| Ortalama skor | 42,3 | 46,9 | 59,8 | 53,5 | 46,0 | 55,1 |
| LOW / MEDIUM / HIGH (41/71) | 51,9 / 37,7 / 10,4 | 46,6 / 38,3 / 15,2 | 10,1 / 60,8 / 29,1 | 29,4 / 47,0 / 23,5 | 48,2 / 37,6 / 14,2 | **24,9** / 48,8 / **26,3** |
| FinHealth <40 / 40–79 / ≥80 | 51,0 / 46,3 / 2,7 | 43,9 / 50,1 / 6,0 | 8,2 / 76,2 / 15,5 | 26,3 / 62,5 / 11,3 | 46,6 / 47,1 / 6,4 | 22,4 / 63,3 / 14,2 |

Karşılaştırma için Türkiye payları: beklenmedik harcamayı karşılayamayanlar %25,1 (Eurostat 2025), 2 aydan uzun idare edebilenler %22,3 (Findex 2025). Bunlar doğrulama değil, kabaca bir tutarlılık kontrolü: vekil ölçüler ve sentetik nüfus kullanıldı.

- v3'ün en büyük sıçraması (4), gelirin 1 TL olduğu G10b probunda +1 TL yatırımdan geliyor; orada 1 TL bir aylık gelire eşit. Bütün eşik problarında ve tek adımlı denetim örneklerinde 1 TL skoru en fazla 1 oynatıyor (birim testi).
- v3b ölçüldüğü haliyle fazla cömert: LOW payı %10, ortalama +17,5. Neden: bedava net borç puanı ve kırılgan nüfusun çoğunu cezalandıran gider oranının kalkması.
- v3c-i5'in HIGH payı (%26,3) Findex'in %22,3'ünden biraz yüksek. HIGH sınırı FinHealth'teki gibi 80 olsaydı pay %14,2 olurdu (Bölüm 10).
- Mekanizmaların sıklığı (çekirdek, `v3Diagnostics`):
  - faiz tabanı %17,1'de bağlıyor; çoğunlukla taksitsiz borç ve düşük faizli uzun krediler;
  - gider tabanı %0;
  - tavan %0 (stres katmanında 36 profil);
  - fazla likidite borçtan %2,3'te düşüyor.

### 6.1 Demolar
| Demo | v2 | v3a | v3b | v3c | v3c-i5 |
|---|---|---|---|---|---|
| low | 8 LOW | 19 LOW | 33 LOW | 24 LOW | 27 LOW |
| medium | 62 MEDIUM | 67 MEDIUM | 74 HIGH | 70 MEDIUM | 71 HIGH |
| high | 88 HIGH | 88 HIGH | 88 HIGH | 86 HIGH | 87 HIGH |
| highdebt | 63 MEDIUM | 37 LOW | 24 LOW | 26 LOW | 22 LOW |
| richincome | 100 HIGH (VERY_HIGH_INCOME) | 42 MEDIUM | 55 MEDIUM | 48 MEDIUM | 53 MEDIUM |
| richwealth | 100 HIGH (VERY_HIGH_WEALTH) | 75 HIGH (WEALTH_RUNWAY) | 81 HIGH | 79 HIGH | 84 HIGH (WEALTH_RUNWAY) |
| extremedebt | 0 LOW (EXTREME_DEBT) | 0 LOW (SOLVENCY_CAP) | 0 | 0 | 0 LOW (SOLVENCY_CAP) |
| trend 1→4 | 8 → 37 → 62 → 92 | 19 → 44 → 74 → 94 | 33 → 56 → 80 → 97 | 24 → 49 → 77 → 96 | 27 → 51 → 79 → 97 |

- `medium` ve `high` demolarında borç 0 iken taksit var. v3 bunlara "Installment without debt" uyarısı veriyor; demo verisinin düzeltilmesi önerilir.
- `highdebt`: 2M borca karşı 2k taksit, %3,5'lik faizin (70k) çok altında.

---

## 7. Öneri ve bedeli

**Öneri: v3c-i5** (Rezerv 30, Taksit 25, Net borç 10, Tasarruf 30, Sabırsızlık 5). Gerekçeler:
1. Uçurumları kapatma, monotonluk ve uyarı tutarlılığında bütün v3 varyantları eşit. Fark yöntemde.
2. v3c-i5 gider oranının çift sayımını kaldırıyor (G7). v3a'da gider~tasarruf puan korelasyonu 0,76'dan 0,87'ye çıkıyor; gider oranı v3a'da tasarrufun pürüzsüz bir kopyası. Ekibin YÖK raporu da "gider oranı çift sayım yapıyor, %40/%60 eşikleri dayanaksız" diyor; v3a bu tespitle çelişir.
3. Ağırlıklar kanıtın gücünü izliyor: dayanaksız eşikli net borç 10, en güçlü dayanaklı rezerv ve tasarruf 30.
4. Sabırsızlık 5: kendi beyanından gelen bedava kazanç 10'dan 5'e iniyor. Sıralama neredeyse değişmiyor (v3c ile Spearman 0,994). Danışmanın "beyana değil veriye dayan" notuyla uyumlu.
5. Kalibre nüfusta segment payları Türkiye'nin kırılganlık paylarına en yakın varyant bu (LOW %24,9 / %25,1).

**Bedeli:** borç alıp nakit tutma kazancı v3a'dan biraz yüksek (rezervin ağırlığı 30). Gideri eksik bildirme kazancı v3a ile aynı düzeyde.

**Yedek: v3a.** Faktör anahtarlarına ve maksimumlarına dokunulmasın denirse (mobil `FACTORS`, AI `FACTORS` aynen kalır). Sabırsızlık 10 kalmalı, yoksa maksimumlar değişir ve v3a'nın tek avantajı gider. Bu durumda G7 açık kalır ve LOW payı %46,6 olur.

### 7.1 Uyumluluk maliyeti
| Bileşen | Her v3'te | Ek olarak yalnız v3b/v3c'de |
|---|---|---|
| `contracts/schemas/` | Yeni `factor-breakdown.v3.schema.json`: `version: "v3"`, `appliedRule ∈ {null, SOLVENCY_CAP, WEALTH_RUNWAY}`, yeni uyarı metinleri, isteğe bağlı `factorMaximums`. İki onay gerekir | Faktör anahtarları `InstallmentToIncome`, `NetDebtToIncome`; `DebtToIncomeRatio` ve `ExpenseRatio` yok |
| AI (`services/ai-rag-service`, Ahmet) | **IQ'dan önce çıkmalı.** `schemas/explain.py`: `applied_rule` bir `Literal` ve v3 etiketini reddedip 422 döner, bu da web ve mobilde "Explain"i bozar. "Kural skoru belirler" kontrolü (`RULES[...][0] != score`) v3 etiketleri için kalkmalı. `core/domain.py`: `WARNINGS`'e 8 yeni metin, `RULES`'a iki yeni etiket. `services/alerts.py` ve `services/facts.py` v2 tanımlarını kullanıyor (rezerv = nakit / gider, %36, %80); v3'te rezerv paydası gider + taksit ve uyarı çizgileri %60, aksi halde Asistan skorla çelişir | `FACTORS` tablosu (anahtar, Türkçe ad, maksimum), istemlerdeki faktör adları. Sürüme göre doğrulama (v2 sonuçları geçmişte duruyor) |
| Mobil (`apps/mobile`, Aykut) | `RULE_TEXT`'e iki etiket. Yoksa "How this score was set" kartı boş görünür. `types.ts` `AppliedRule` | `ResultScreen.tsx` `FACTORS` anahtar ve maksimumları. En iyisi `factorMaximums`'tan okumak (yoksa v2 tablosu) |
| Web (Ahmet) | Döküm ekranı henüz yok; `factorMaximums`'tan okuyacak şekilde yazılmalı | — |
| IQ servisi (Aykut) | Bölüm 8. `ScoringRuleSnapshots.V3` + migration (v3 satırı, aktif) | — |
| Seed / belgeler | `seed_demo_users.py`'deki beklenen skorlar, README, CLAUDE.md 5.4/8.2 | — |
| Geçmiş | `iq_history`'de v2 ve v3 skorları karışır (`scoring_version` kolonu var). Trend açıklaması sürüm değişimini söylemeli | — |

**Sıra:** sözleşme onayı → AI hem v2'yi hem v3'ü kabul eder hale gelir → mobil → IQ servisi v3'ü yayınlar → demo hesaplar yeniden hesaplanır.

---

## 8. Aktarım şartnamesi (C#)

Bu bölüm mekanik bir aktarım için yazıldı. Referans `evaluation/iq_v3/scoring.py`, doğrulama `evaluation/out/iq_v3_golden.json`.

### 8.1 Girdi ve ön koşul
- `I` = MonthlyIncome, `E` = MonthlyExpenses, `P` = MonthlyDebtPayment, `D` = TotalDebt, `C` = CashReserve, `V` = InvestmentAmount, `K` = ImpatienceLevel.
- **Doğrulama v2 ile aynı kalır:** `I > 0`, diğer tutarlar `≥ 0`, `K ∈ {1..5}`. `I > 0` olduğu için aşağıdaki hiçbir payda sıfır olamaz: `O ≥ 0,1·I`, `12·I`, `12·Eeff ≥ 1,2·I`. Sonsuz ya da özel durum yok.
- Bütün aritmetik `decimal`. Sabitler: `0.5m`, `0.10m`, `6m`, `0.035m`, `12m`, `0.6m`.

### 8.2 Ölçüler (bu sırayla)
```
L     = C + V * 0.5                       // likit varlık
Eeff  = max(E, I * 0.10)                  // gider tabanı
O     = Eeff + P                          // aylık çıkış
m     = L / O                             // rezerv, ay
X     = max(0, L - O * 6)                 // acil fon hedefinin (6 ay) üstündeki likit varlık
N     = max(0, D - X)                     // net borç
y     = N / (I * 12)                      // net borç, yıllık gelir cinsinden
Peff  = max(P, N * 0.035)                 // borç servisi en az faiz kadar
r     = Peff / I                          // taksit oranı
s     = (I - Eeff - Peff) / I             // tasarruf oranı
e     = Eeff / I                          // gider oranı (yalnız v3a)
W     = L - D                             // likit net servet
R     = W > 0 ? W / (Eeff * 12) : 0       // servet pisti, yıl
lam   = Lin(R, RUNWAY_YEARS)              // λ
kappa = Lin(y, SOLVENCY_CAP)              // κ
```

### 8.3 Doğrusal tablo ve çapalar
`Lin(x, T)`, `T = [(x0,s0) … (xn,sn)]` artan `x` sırasıyla tanımlı:
- `x <= x0` ise `s0`;
- değilse ilk `i` için `x <= x(i+1)` ise `s(i) + (x - x(i)) * (s(i+1) - s(i)) / (x(i+1) - x(i))`. İşlem sırası tam olarak bu: önce çarpma, sonra bölme;
- hiçbiri tutmazsa `sn`.

Payların tablosu varyanttan bağımsız; yalnız maksimumlar değişir.

| Tablo | Çapalar (değer → pay) | Dayanak |
|---|---|---|
| `RESERVE_MONTHS` (m) | 0 → 0; 3 → 0,6; 6 → 1 | 3 ay güçlü, 6 ay kısmi |
| `INSTALLMENT_RATIO` (r) | 0,10 → 1; 0,20 → 0,6; 0,36 → 0,2; 0,50 → 0 | %10/%20 güçlü, %36 Greninger/28-36; 0,50 yargı |
| `NET_DEBT_YEARS` (y) | 0,5 → 1; 1 → 0,6; 3 → 0,2; 5 → 0 | v2'nin eşikleri, dayanaksız; 5 yargı |
| `SAVINGS_RATE` (s) | −0,10 → 0; 0 → 0,2; 0,10 → 0,6; 0,20 → 1 | %10 güçlü, %20 kısmi; 0 ve −0,10 yargı |
| `EXPENSE_RATIO` (e, yalnız v3a) | 0,40 → 1; 0,60 → 0,6; 0,80 → 0,2; 1,00 → 0 | v2'nin eşikleri, dayanaksız |
| `IMPATIENCE` (K) | 1 → 1; 2 → 0,8; 3 → 0,6; 4 → 0,2; 5 → 0 | Merdiven; 3 = nötr, uyarı yok |
| `SOLVENCY_CAP` (y) | 5 → 1; 15 → 0 | %36 ile faizsiz geri ödeme 14 / 42 yıl |
| `RUNWAY_YEARS` (R) | 0 → 0; 25 → 1 | %4 kuralı (Bengen 1994) |

### 8.4 Faktör payları ve puanlar
```
shRes  = Lin(m, RESERVE_MONTHS)
shInst = max(Lin(r, INSTALLMENT_RATIO), lam)
shNd   = Lin(y, NET_DEBT_YEARS)
shSav  = max(Lin(s, SAVINGS_RATE), lam)
shExp  = max(Lin(e, EXPENSE_RATIO), lam)          // yalnız v3a
shImp  = Lin(K, IMPATIENCE)
```
| Düzen | Faktör → pay |
|---|---|
| v3a | CashReserveMonths = shRes, **DebtToIncomeRatio = min(shInst, shNd)**, SavingsRate = shSav, ExpenseRatio = shExp, Impatience = shImp |
| v3b / v3c | CashReserveMonths = shRes, InstallmentToIncome = shInst, NetDebtToIncome = shNd, SavingsRate = shSav, Impatience = shImp |

**Maksimumlar:**
- v3a 25/25/25/15/10;
- v3b 25/20/20/25/10;
- v3c 30/20/10/30/10;
- v3a-i5 30/25/25/15/5;
- v3b-i5 30/20/20/25/5;
- **v3c-i5 30/25/10/30/5**.

Anahtar sırası yukarıdaki gibi; `factors` ve `factorMaximums` bu sırayla yazılır.

```
points[f] = Round(Max[f] * share[f] * kappa)       // önce Max*share, sonra *kappa
Round(x)  = Math.Round(Math.Round(x, 6, MidpointRounding.AwayFromZero), 0, MidpointRounding.AwayFromZero)
score     = Σ points[f]
segment   = score >= 71 ? "HIGH" : score >= 41 ? "MEDIUM" : "LOW"     // değişmedi
```
- Önce 6 haneye yuvarlama, bölmenin son hanesindeki gürültüyü emiyor. Örneğin `low` demosunda ExpenseRatio kağıt üstünde tam 2,5: Python'da ve C#'ta aynı şekilde 3'e yuvarlanır.
- `x ≥ 0` olduğundan AwayFromZero = yarımı yukarı. Banker's rounding (C#'ın varsayılanı) **kullanılmamalı**: 12,5 → 12 olur.

### 8.5 Uyarılar (sıra sabit; tekrar yok)
`pre[f] = Round(Max[f] * share[f])`, κ'sız. "Zayıf": `pre < 0.6 * Max`.
- v3a'da taksit ve net borç alt parçaları ayrı değerlendirilir: `instPre = Round(25 * shInst)`, `ndPre = Round(25 * shNd)`, eşik 0,6 × 25 = 15.
- v3b/v3c'de kendi faktörleri değerlendirilir.

| # | Koşul | Metin | Tür | v2'de |
|---|---|---|---|---|
| 1 | rezerv zayıf | `Low cash reserve` | faktör | aynı metin (v2: < 3 ay; v3'te payda gider + taksit) |
| 2 | taksit zayıf ve `r > 0.36` | `High debt burden` | faktör | aynı anlam ve eşik |
| 2 | taksit zayıf ve `r <= 0.36` | `Elevated debt burden` | faktör | **yeni** |
| 3 | net borç zayıf ve `y > 3` | `High total debt` | faktör | aynı anlam ve eşik |
| 3 | net borç zayıf ve `y <= 3` | `Elevated total debt` | faktör | **yeni** |
| 4 | tasarruf zayıf ve `s < 0` | `Negative savings rate` | faktör | aynı |
| 4 | tasarruf zayıf ve `s >= 0` | `Low savings rate` | faktör | **yeni** |
| 5 | (v3a) gider zayıf ve `e > 0.80` | `Overspending relative to income` | faktör | aynı anlam ve eşik |
| 5 | (v3a) gider zayıf ve `e <= 0.80` | `High expense ratio` | faktör | **yeni** |
| 6 | sabırsızlık zayıf (K ≥ 4) | `High impatience` | faktör | aynı |
| 7 | `kappa < 1` (y > 5) | `Extreme total debt` | tavan | metin aynı, anlam: tavan devrede |
| 8 | `N > 0 && P < N * 0.035` | `Installment below interest` | tutarlılık | **yeni** |
| 9 | `E < I * 0.10` | `Expenses look too low` | veri kalitesi | **yeni** |
| 10 | `P > 0 && D == 0` | `Installment without debt` | veri kalitesi | **yeni** |
| 11 | `D > 0 && P > D` | `Installment exceeds total debt` | veri kalitesi | **yeni** |

**Değişmez kural (test edilmeli):** κ = 1 iken her faktör için `points < 0.6 * Max` ⇔ o faktörün uyarılarından biri listede. κ < 1 iken `Extreme total debt` her zaman listede.

### 8.6 `appliedRule` (yalnız etiket; 25 Kasım'da düzeltildi)
1. `kappa < 1` → `"SOLVENCY_CAP"`. Öncelik değişmedi.
2. Değilse `R >= 5` (pist en az 5 yıl, yani `lam >= 0.2`) **ve** skor, aynı hesabın `lam = 0` ile yapılmış skorundan büyükse → `"WEALTH_RUNWAY"`.
   - Faktörleri bir kez de λ = 0 ile hesapla ve toplamları karşılaştır.
   - Sabit: `WEALTH_RUNWAY_LABEL_MIN_YEARS = 5m`.
   - Koşul `R` üzerinden yazıldı, λ'nın bölmesine bağlı değil; `R = 5` tam sınırda etiket verir.
3. Değilse `null`.

**Neden değişti:** eski kural `lam > 0` ile yetiniyordu. Birkaç aylık nakit (yılın bir kesri kadar pist) tasarrufu negatif bir profili yuvarlamayla 1 puan kaldırınca etiket yazılıyordu. Etiketin açıklaması ("likit servet giderleri yıllarca karşılar") o durumda yanlıştı.
- Örnek L1: 30k gelir, 20k gider, 30k taksit, nakit 2 aylık çıkış (100k), pist 0,42 yıl. v3c-i5 skoru 26 (kaldırmasız 25); etiket artık `null`.
- **Skorlar değişmez:** kaldırma (λ) 0 yıldan başlamaya devam ediyor; yalnız etiket değişiyor.
- **Sayılar:**
  - 63.026 profillik değerlendirme kümesinde v3c-i5 `WEALTH_RUNWAY` sayısı 1.031'den 329'a indi.
  - Çekirdek + stres + demoda 36'dan 12'ye indi: çekirdek 12 → 0, yüksek gelir 9 → 0, varlıklı 14 → 11, demo `richwealth` 1 → 1.
  - Altın tablonun mevcut 50 satırında etiket değişen yok. L1 (`null`) ve L2 (30 yıllık pist, `WEALTH_RUNWAY`) eklendi.
- 5 yıl seçimi: tam kaldırmanın (25 yıl, %4 kuralı) beşte biri. Daha temiz bir koşul aranırsa: "kaldırma, en az bir faktörü maksimumunun %20'si kadar yukarı taşıyor" aynı amaca hizmet eder; ama faktöre bağlı olduğu için açıklaması daha zor. Önerilen koşul `R >= 5`.

### 8.7 Döküm (JSON)
```json
{
  "version": "v3",
  "factors": { "CashReserveMonths": 30, "InstallmentToIncome": 25, "NetDebtToIncome": 10, "SavingsRate": 19, "Impatience": 0 },
  "factorMaximums": { "CashReserveMonths": 30, "InstallmentToIncome": 25, "NetDebtToIncome": 10, "SavingsRate": 30, "Impatience": 5 },
  "warnings": ["High impatience"],
  "appliedRule": "WEALTH_RUNWAY"
}
```
Bu örnek `richwealth` demosunun v3c-i5 sonucu. Faktörler skora eşit (84), skor faktörlerin toplamı.

### 8.8 IQ servisinde yapılacaklar
- `ScoringRules.cs`:
  - mevcut `ScoreScale` (basamak) yanına `LinearScale(Measure, Anchors[(Value, Share)], Warning…)` gibi bir tür;
  - Bölüm 8.3'ün tabloları ve sabitleri;
  - `ScoringVersion = "v3"`.
  
  `ScoringRuleDocument` belgeyi aynı tablolardan üretmeye devam etmeli; IQ kural tablosu görseli de buradan.
- `FinancialIqCommandManager.CalculateScore`: Bölüm 8.2 → 8.6. TL kuralları (`GetAppliedRule`, `VeryHigh…`, `ExtremeNetDebt`) kalkar.
- `ScoringRuleSnapshots.V3` + migration `AddScoringRulesV3`: v3 satırı eklenir, `is_active` v3'e geçer. `ScoringRuleDocumentTests` yeni snapshot'ı bekler. v1/v2 satırlarına dokunulmaz.
- **Altın test:**
  - `iq_v3_golden.json` → `profiles[]`; her satırda `input`, `intermediates` (6 haneye yarımı yukarı yuvarlanmış), ve her varyant için `score`, `segment`, `factors`, `warnings` (sıralı), `appliedRule`;
  - seçilen varyantın sütunu birebir tutmalı;
  - `intermediates` hata ayıklama için: ilk farklı ölçü hangi formülün yanlış aktarıldığını gösterir.
- BatchScorer değişmez. v3 aktarıldıktan sonra `iq_eval_v3.py` v2 yerine C# v3'ü de skorlayabilir: altın tablonun nüfus ölçeğinde tekrarı.

---

## 9. Sınırlamalar
- **Ölçekten bağımsızlık:** TL eşiği olmadığından gelir 1 TL ile 100.000 TL aynı oranlarla aynı skoru alır (G10b: 93).
  - Bilinçli bir seçim (G12).
  - İstenirse yıllık güncellenen bir asgari ücret referansıyla yalnızca *uyarı* eklenebilir.
- **Gelir 0** hâlâ kabul edilmiyor (v2 doğrulaması). Emekli gibi geliri olmayanlar ileride servet pistiyle skorlanabilir. Bunun için paydaların sıfır durumları tanımlanmalı.
- **Kendi beyanı:** gideri eksik bildirmek her zaman puan kazandırır (%10 eksik → ortalama +4–5). Sabırsızlık beyanı 5 (ya da 10) puan değerinde. Veri kalitesi uyarıları doğrulama yapmaz, yalnızca işaretler.
- **Borç alıp nakit tutmak** rezervi artırır (Bölüm 4). Taksit dürüst bildirilirse ortalamada zarar ettirir.
- **%3,5 faiz tabanı** bütün borçlara uygulanıyor. Konut kredisi gibi düşük faizli uzun borçlarda fazla katı olabilir. Kalibre nüfusun %17'sinde bağlıyor; çoğunlukla taksiti bildirilmemiş borç.
- **Yargıya dayanan çapalar:**
  - net borç 0,5/1/3/5 yıl;
  - gider oranı 40/60/80/100;
  - tasarruf −%10;
  - tavan 5/15 yıl;
  - pist 25 yıl (ABD verisinden %4 kuralı);
  - gider tabanı %10;
  - ağırlıklar (uzman yargısı).
- **Nüfus sentetik:** yalnızca marjinal paylara kalibre, ortak dağılım bilinmiyor.
  - Taksitsiz borç payı, vade dağılımı, yatırım ve sabırsızlık dağılımı varsayım.
  - Tasarruf oranı ölçüsünün alt ucu %10,4, Türkiye %14,3.
  - Segment karşılaştırması bir tutarlılık kontrolü; doğrulama değil.
- **Sonuçla doğrulama yok:** skorun temerrüt ya da finansal sıkıntıyı ne kadar öngördüğü ölçülmedi. Bunun için TÜİK GYKA mikroverisi gerekiyor.
- **Python `Decimal` (28 anlamlı hane) ile C# `decimal` (28 ondalık hane)** son hanede ayrışabilir. 6 haneli ön yuvarlama ve altın tablo bunu karşılıyor.

## 10. Kararlar ve açık konular (ekip ve danışman)
**24 Kasım'da kullanıcı onayladı:**
- **v3c-i5**;
- segment sınırları **41/71** kalıyor;
- sabırsızlık ağırlığı **5**;
- yüksek gelire ayrıca bonus **yok**.

Aşağıdaki 1–3. maddeler bu onayla kapandı; geri kalanlar açık.

1. ~~**Varyant:** v3c-i5 (öneri) mi, v3a mı?~~ → v3c-i5.
2. ~~**Sabırsızlık ağırlığı:** 5 mi, 10 mu?~~ → 5.
3. ~~**Segment sınırları:** 41/71 mi, HIGH 80'den mi?~~ → 41/71 kalıyor. HIGH 80'den başlasaydı v3c-i5'te HIGH payı %26,3'ten %14,2'ye inerdi.
4. **Faiz tabanı:** %3,5 bütün borçlara mı uygulanacak, yoksa formda borç türü mü sorulacak?
5. **Gider tabanı (%10) ve gelir 0:** emekliler/varlıkla geçinenler için gelir 0 kabul edilsin mi?
6. **Geçmiş:** v2 sonuçları v3 ile yeniden hesaplansın mı, yoksa trendde sürüm kırılması mı gösterilsin?
7. **Sözleşme:** `factor-breakdown.v3.schema.json` için iki onay. AI'nın v3'ü kabul etmesi IQ'dan önce çıkmalı.
8. **Repo:** `evaluation/out/iq_v3_results.json` ve `evaluation/out/iq_v3_golden.json` `.gitignore`'da istisna yapılmalı; altın tablo C# testinin girdisi.
9. **Demo verisi:** `medium` ve `high` demolarında borç 0 iken taksit var; düzeltilsin mi?
