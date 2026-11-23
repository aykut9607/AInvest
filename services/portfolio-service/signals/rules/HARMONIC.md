# Harmonik kural listesi (v1, 23 Kasım 2026)

Görseller: [harmonic-visuals.html](harmonic-visuals.html) (kendi çizimlerimiz). Bir formasyon sormak için X A B C D (D yoksa X A B C):

```powershell
.\venv\Scripts\python.exe -m signals.rules.harmonic_draw 100 200 145 186 121.4
# Gartley: DEĞİL, H-03: B = 0.550 (olması gereken 0.618)   + data/reports/harmonic-check.html çizimi
```

**Türler.** **K** = kesin (bozulursa o formasyon değil) · **R** = kılavuz (puanı düşürür). **Kaynak.** C = S. Carney, harmonictrader.com
(23 Kas'ta formasyon sayfaları tekrar okundu) · Ö = bizim tanımımız, backtest ile ayarlanacak · M = hesapla gösterilebilir.

**Oranlar** (hepsi mutlak boy): B = AB/XA · C = BC/AB · D = AD/XA (1'den büyükse X'in ötesi) · BC uzatması = CD/BC · AB=CD oranı = CD/AB.
Yükselen: X dip, A tepe, B dip, C tepe, D dip (alım bölgesi). Düşen = ayna.

## 1. Oran tablosu (kesin kısım)

| | B (H-03) | D (H-04) | BC uzatması (H-05) | CD/AB en az (H-07) | CD/AB alışılmış (H-08, R) |
|---|---|---|---|---|---|
| Gartley | **0,618** | **0,786** (X'i geçmez) | 1,27–1,618 | – (belirgin AB=CD ister) | 1 |
| Bat | 0,382–0,5 (ideali 0,5) | **0,886** | 1,618–2,618 | 1 | 1 / 1,27 |
| Alternate Bat | ≤ 0,382 | **1,13** | en az 2,0 (üst sınır yazmıyor) | 1 | – |
| Butterfly | **0,786** | **1,27** | 1,618–2,618 | 1 | 1 / 1,27 |
| Crab | 0,382–0,618 | **1,618** | 2,24–3,618 | 1 | – |
| Deep Crab | 0,886 ve ötesi, X'i aşmaz | **1,618** | 2,24–3,618 | 1 | 1 / 1,27 |

## 2. Kurallar

| No | Tür | Kural | Kaynak |
|---|---|---|---|
| H-01 | K | C, AB'nin 0,382–0,886'sı | C (AB=CD sayfası) |
| H-02 | K | B, X'i hiçbir zaman aşmaz (**tolerans yok**) | C (Deep Crab), genel yapıldı: Ö |
| H-03 | K | B tablodaki yerinde. Formasyonun adını **önce B** belirler | C |
| H-04 | K | D tablodaki XA seviyesinde; PRZ'nin tanımlayıcı sayısıdır | C |
| H-05 | K | BC uzatması tablodaki aralıkta (Bat'ta 1,27 açıkça geçersiz) | C |
| H-06 | K | Gartley'de D, X'i geçmez (tolerans yok) | C |
| H-07 | K | CD en az AB kadar (Carney'nin en küçük şart dediği formasyonlar) | C; Alternate Bat ve Deep Crab: Ö |
| H-08 | R | Alışılmış AB=CD oranı; Gartley'de "belirgin AB=CD" | C |
| H-09 | R | Bat'ta ideal B = 0,5 | C |
| H-10 | – | Karşılıklı oranlar (C 0,618 ↔ BC 1,618; 0,786 ↔ 1,27): CD = AB ise BC uzatması zaten 1/C'dir. **Aynı bilginin iki yazılışı, iki ayrı kanıt değil** | C + M |
| H-11 | K | Tepe/dipler kesinleşmiş ve sıralı olmalı (geleceği görmeme, E-G1) | Ö |
| H-12 | K | D'den önce fiyat C'yi geçerse eski C ve planı iptal; yeni C ile baştan ölçülür | Ö |
| H-13 | K | Tolerans ±%3 göreli, yalnız oranlarda | A (Aykut); Carney sayfalarında yüzde yok |
| H-14 | K | D seviyesi geçilince formasyon başka ada çevrilmez (ör. "Bat olmadı, Alternate Bat'tır"); B'si yeni ada uyuyorsa baştan sınanır | Ö, E-61 ile aynı mantık |
| H-20 | K | Oranların tamamlanması işlem değildir: bölgede **dönüş onayı** gerekir (RULES.md 3 ve 7: LTF SFP + P.U/N.U, günlük kapanış) | A |
| H-21 | K | PRZ = D'nin XA seviyesi + ona %5 XA içinde binen BC ve AB=CD seviyeleri. Daha önce gelen AB=CD seviyesi "ön uyarı"dır, bölge değildir | Ö |
| H-22 | R | PRZ'de ne kadar çok **farklı bacaktan** (XA, BC, AB) seviye binerse o kadar iyi | C, E-72 |
| H-23 | R | Geçersizlik: Gartley X; diğerleri sonraki seviye (Bat 1,13 · Alt. Bat 1,272 · Butterfly 1,414 · Crab'ler 2,0) | Gartley C; diğerleri Ö |
| H-24 | R | İlk hedef 0,382 AD, ikinci 0,618 AD | yaygın kullanım; **Carney sayfalarında bulunamadı** |
| H-25 | R | HTF yönüyle çelişen formasyon zayıftır | Ö (E-97) |

Shark ve 5-0 bu sürümde **yok**: okunabilen sayfalarda kodlamaya yetecek sayı verilmiyor. Cypher Carney'nin formasyonu değil.

## 3. Gözden geçirmede bulunanlar

**3.1 Oranların birbirini kısıtlaması (D tam yerinde olursa, hesapla):**

| Formasyon | Sonuç |
|---|---|
| Crab | B = 0,382 ile **imkânsız** (hiçbir C, BC ≤ 3,618'i sağlamaz). B = 0,5 → C yalnız 0,855–0,886; B = 0,618 → C ≥ 0,619 |
| Alternate Bat | BC ≤ 3,618 şartı B ≈ 0,30'un altını tamamen yasaklıyordu; üst sınır kaynakta yok → **kaldırıldı** (H-05) |
| Alternate Bat, Crab | "AB=CD 1,618" D seviyesinde **tutamaz** (CD/AB en az 2,3 / 2,0); fiyat o seviyeyi D'den önce geçer → ön uyarı (H-21), uyum puanından çıkar |
| Gartley | CD ≥ AB şartı C'yi 0,729 ve üstüne itiyordu; klasik C = 0,618'de CD = 0,89 AB → **kesinden kılavuza** (H-08) |
| Deep Crab | B = 0,886 → C en fazla 0,666 |
| Bat | B = 0,382 → C ≥ 0,816; B = 0,5 → C ≥ 0,478 |

**3.2 Kod (`signals/patterns/harmonic.py`, v0)**

| Kural | Durum |
|---|---|
| H-01, 03, 04, 05 | ✅ tablo Carney ile aynı (Alternate Bat üst sınırı hariç) |
| H-02 | ❌ hata: ±%3, Deep Crab'de B'nin X'i aşmasına izin veriyor (98,5 / X = 100 kabul edildi) |
| H-05 | ⚠ Alternate Bat'ta kaynakta olmayan 3,618 üst sınırı |
| H-07/08 | ⚠ Gartley'de CD ≥ AB kesin sayılıyor |
| H-08 | ⚠ Crab/Alternate Bat uyum puanı ulaşılamaz AB=CD oranıyla ölçülüyor |
| H-12 | ❌ C geçilince plan iptal edilmiyor (dokunulan 47 kurulumun 5'i) |
| H-21/22 | ⚠ PRZ yalnız BC aralığının iki ucunu kullanıyor (Bat 2,0; Butterfly 2,0/2,24; Crab 2,618/3,14 yok) |
| H-25 | ❌ HTF yönü yok |

**3.3 Örnek neden az?** ZigZag 3 × ATR, 6 seri: 168 gelişen formasyon → 121'ine 60 mum içinde dokunulmadı → **47** kurulum (44 ayrı yapı).
k = 2'de 330, k = 1,5'te 508 gelişen formasyon var (farklı büyüklükte yapılar). Formasyon başına sonuç çıkarmaya yetmez; v0'daki
"Butterfly iyi" görüntüsü 15 kuruluma dayanıyor, **iddia edilmez**. Yeni ölçüm birden fazla ZigZag boyunda, formasyonlar
"geri çekilme (Gartley, Bat)" ve "uzatma (diğerleri)" diye birleştirilerek raporlanacak.

## 4. Elliott ile bağ (benim çıkarımım, sınanacak)

| Harmonik | Elliott'ta olası yeri | Ortak geçersizlik |
|---|---|---|
| Gartley, Bat (D, X'i geçmez) | XA itkiyse A→D = zigzag: **2. dalga sonu** (4. dalga için 0,786–0,886 fazla derin) | X = E-01 sınırı |
| Alternate Bat, Butterfly, Crab'ler (D, X'in ötesi) | genişleyen yassının C'si ya da son itki dalgası; X'ten başlayan 1-2 sayımı E-01 ile **elenmiştir** | formasyonun kendi seviyesi |

İkisi aynı yeri gösteriyorsa güçlü aday; ama ikisi de **aynı tepe/diplerden** ölçülür, bağımsız iki kanıt değildir. Gerçek ek kanıt: LTF
SFP, uyumsuzluk, kapanış.
