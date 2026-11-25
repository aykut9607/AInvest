# Çakışan kurallar (25 Kasım 2026; 469 kuralın hepsi tarandı)

Kural numarası silinmez (aynı kural yeniden eklenmesin diye), ama **elenen kural puan almaz**. Üç karar türü:
**ELENDİ** = mantıkla ya da kendi kararımızla yanlış · **KOŞUL** = ikisi de doğru, farklı durumlarda · **ÖLÇ** = veri karar verecek
(parite ve dilim başına; `rule-tests.html`). Kitap kuralları (BK) henüz ölçülmedi, yalnız çakışmaları yazıldı.

## Elenenler
| Kural | Yerine | Neden |
|---|---|---|
| RULES.md "1. uzayan: [5] = [1]" | E-14 | [3] < [1] iken [5] = [1] olursa 3 en kısa kalır, E-03 bozulur (matematik) |
| RULES.md "B ≥ 0,786 ise zigzag değil" | E-31, E-33 | kesin sınır B'nin başı geçmemesi; 0,786 yalnız şüphe |
| RULES.md "iptal yalnız kapanışla" (Elliott kesin kuralları için) | E-94, E-102 | kesin kural fitille bozulur, sayım bozulunca plan da bozulur. Harmonik ve seviyelerde kapanış kalır |
| BK-162 (stopsuz), BK-181 (tepkide çık) | RK-05 | stopsuz işlem yok |
| BK-81'in "kademeli gir" kısmı | BK-31, BK-179 | zarardakine ekleme yok |
| BK-193'ün %1 stop'u | BK-75 | BTC'nin ortanca günlük aralığı %3,2, altın %1,5, S&P %1,1 (son 1000 gün): %1 stop gürültünün içinde |
| BK-133 ve BK-89'un "kazandıkça büyüt" kısmı | RK-01, RK-22, BK-55, BK-221 | risk yüzdesi sabit; hesap büyüdükçe tutar kendiliğinden büyür |
| BK-156 (kendi görüşüyle yarı yarıya) | BK-134, BK-136, BK-185 | karar kodda, elle müdahale yok |
| BK-120 (2–3 gün kapanış) | PA-06 | kararımız: kendi diliminin tek kapanışı |
| BK-211'in yarım aralık stop'u | BK-75, BK-210 | yazarın basitleştirilmiş örneği; VIX tablosu kalır |
| BK-87, BK-183, BK-222 | BK-215 | 3, 1 ve 9 örnek: ölçülemez |
| BK-176'nın tepe satışı | BK-223, BK-167 | kitabın kendisi de tehlikeli diyor |

## Koşula bağlananlar
| Çakışma | Hangisi ne zaman |
|---|---|
| FM-03a (0,5 üstü güçlü) ↔ MB-04 / SM-21 (premium'da short) | trend varken FM-03a, range içindeyken MB-04 / SM-21 |
| PA-08 (trende karşı işlem yok) ↔ SFP, harmonik, 5. dalga, BK-177 dönüşleri | trend = HTF. HTF'ye karşı dönüş en sıkı onayı ister (RULES.md 5) |
| MB-22 (WO üstünde short yok) ↔ FM-04 / SM-21 üst süpürme short'u | istisna: 200G/200H, YO, test edilmiş direnç; ölçümle doğrulanacak |
| PA-06 BOS ↔ RULES.md iki mumluk SFP | kapanış BOS sayılır; hemen sonraki mum geri kapanırsa "başarısız kırılım" olur (BK-168) |
| SM-22 (3 mum) ↔ RULES.md SFP (2 mum) | tek seviyede en çok 2, range sınırında en çok 3 mum |
| FR-04 (0,60–0,73) ↔ SM-57 / F-03 (0,618–0,786) ↔ MB-08 (0,618–0,66) | tek bölge, **tek puan**; alt bantlar ayrı ayrı ölçülür ama toplanmaz |
| H-13 (±%3 göreli) ↔ F-04 (1'in üstünde ±0,03) | harmonikte H-13, trend fibde F-04 |
| BK-02 ↔ BK-06 (VWAP altı) | önce büyük yapı (BK-06), sonra VWAP |
| BK-08 (yuvarlak sayıda işlem yok) ↔ BK-194 / PA-24 | seviyede beklenir; ilk aşımda BK-194 |
| BK-160 (yeni tepe → yeniden gir) ↔ BK-220 (24 saat yok) | yeni sinyal serbest; aynı kurulum 24 saat bekler |
| BK-70 (haber pivotu) ↔ RK-42 (olay günü işlem yok) | pivot yalnız seviye; işlem ertesi gün |
| BK-11 (%100 geri alınana dek trend) ↔ FT-05 | FT-05 planı iptal eder, trendi PA-04 bitirir |
| SM-95 ↔ SM-96 (OI) | SM-95 değişime, SM-96 düzeye bakar |
| BK-73 (hacimli tutulan destek = emilim) ↔ BK-166 / BK-202 (hacim + ilerlemeyen fiyat = dağıtım) | destekte emilim, tepeden sonra dağıtım |
| E-42 ↔ BK-28 (düzensiz yassıda C 1,62–2,62) | hedef 1–1,62; 2,62 istisna |
| RK-01 %1–2, BK-54 / BK-134 / BK-143 %1, BK-89 %1–3, BK-142 %5 | en sıkısı: %1 |
| RK-05, RK-21, MB-13, BK-155, BK-165, BK-220 durma kuralları | hangisi önce dolarsa |
| BK-215 (en az 30) ↔ RK-31 (en az 100) | 30 ölçüm alt sınırı, 100 puan için hedef |

## Veri karar verecek
| Çakışma | Test |
|---|---|
| Taze seviye güçlü (SM-11, SM-43, SM-81) ↔ çok temaslı güçlü (PA-22, BK-71) ↔ çok test kırılmayı getirir (BK-144, BK-72) | `body_*_1 / _2 / _4`, `sd`, `ob` |
| Onaysız dokunuş (SM-12, SM-42, PR-31) ↔ onay şart (F-06, H-20, MB-23, SM-71) | `fr_*` ↔ `zone_*` |
| Kırılımda hemen gir (BK-163, BK-186) ↔ retest bekle (PA-13, PA-34) | `bos` ↔ `break_retest` |
| Kırılım devam eder (BK-101, BK-144) ↔ kırılım tuzaktır (BK-74, SM-22) ↔ BK-130 | `bos`, `range_break`, `sfp`, `deviation` |
| Rejim tanımı: PA-02/04 ↔ BK-40 ↔ BK-206 ↔ BK-207 ↔ BK-08 | ölçülene kadar HTF yapısı (PA) esas |
| Yön filtreleri: MB-09 / MB-22, BK-02, BK-45, BK-171, FM-03a aynı anda ters söyleyebilir | `bias_w`, `bias_m`, `monday_half`; ölçülene kadar HTF yapısı esas |
| PR-40 (fiyat ↓ CVD ↑ zayıf düşüş) ↔ PR-42 (emilim) | `cvd_*`, `absorption` |
| E-96 (3'ün ortasından kaçın) ↔ BK-157, BK-177 (momentumla gir) | sonraki tur |
| BK-104 (direnen de düşer) ↔ BK-172, BK-199, BK-132 (güçlü kalan güçlüdür) | çok varlık verisi gelince |
| BK-44 (RSI 75/25) ↔ BK-80 (en uç %5) ↔ MB-24, BK-161 (işe yaramaz) | kitap turunda |
| Hedefe ulaşınca çık (SM-12, PA-35, MB-12) ↔ hedef yok (BK-103, BK-151, BK-170) ↔ başa baş stop (BK-117) | çıkış turunda |
| BK-77 (simetri tepeden) ↔ BK-173 (önceki osilatör tepesinden) | kitap turunda |
| Yalnız BTC'de çalışan FM modeli ↔ BK-148 (tek piyasada çalışana güvenme) | puan parite başına olduğu için kural yasak değil, ama "hipotez" etiketi taşır |
| PR-60 (R/R 1,54) ve BK-212 (1,8) ↔ RK-03 (en az 1:2) | karar (25 Kas, Aykut): RK-03 alt sınırı 1:1,5; ikisi de geçer |
