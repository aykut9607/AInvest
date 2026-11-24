# Elliott kural listesi (v1, 23 Kasım 2026)

Derslerin kendi cümlelerimizle özeti; metin ve çizim kopyalanmadı. Görseller: [elliott-visuals.html](elliott-visuals.html)
(kendi çizimlerimiz). Bir sayım sormak için (başlangıç noktası önce):

```powershell
.\venv\Scripts\python.exe -m signals.rules.elliott_draw 100 130 115 160 125 180
# İtki: DEĞİL, E-04: 4. dalga 125 ile 1'in alanına (130) girdi   + data/reports/elliott-check.html çizimi
```

**Türler.** **K** = kesin: bozulursa o sayım elenir. **R** = kılavuz: uymazsa sayım zayıflar ama elenmez.
**Kaynak.** B1–B10 = Elliott eğitimi modül 1–10 · T = TraderLex rehberi · V = TraderLex videosu (görüntü; ses dinlenemedi) ·
A = Aykut'un kuralı. **Ölçüm:** "F" = uç fiyatlarla, "Y" = dalganın bütün yolu (fitiller), "İ" = iç yapı (alt dalga), "K" = konum.

Temel ilke: **fiyatlar bir sayımı çürütebilir, tek başına kanıtlayamaz.** En iyi sonuç "olabilir"dir. Cevap sırası: hangi kural →
hangi fiyat → hangi yorum elendi → hangi bilgi eksik → alternatif.

---

## 1. Genel (sayımdan önce)

| No | Tür | Kural | Kaynak |
|---|---|---|---|
| E-G1 | K | Tepe/dip ancak sonraki hareketle kesinleşir; son nokta kesinleşmiş sayılmaz (geleceği görmeme) | B1 |
| E-G2 | K | Etiket hareketin **bittiği** yere konur; 0 dalga değil, başlangıçtır. 5 dalga = 6 nokta; 5+3 = 9 nokta | B2 |
| E-G3 | K | Aynı sayımda tek derece: ana dalga ile alt dalga aynı sıraya yazılmaz | B2, B8 |
| E-G4 | K | Derece ≠ zaman dilimi; parçanın bütündeki yerinden anlaşılır | B2 |
| E-G5 | R | Aynı noktada iki etiket olabilir (küçük v biter, büyük 1 de biter) | B2 |
| E-G6 | K | Gözlem ile beklenti ayrı yazılır; şekil zorlanmaz | B1 |
| E-G7 | K | Bütün ölçümler aynı ölçekte (aritmetik ya da logaritmik); ortada değiştirilmez | B3 |
| E-G8 | K | Kurallar düşüşte aynadır: 1-3-5 aşağı, 2-4 yukarı; düzeltme yukarı olabilir | B2 |
| E-G9 | K | ±%3 tolerans **yalnız Fibonacci oranları** içindir; kesin kurallarda tolerans yok | A + B3 |

## 2. İtki (1-2-3-4-5)

| No | Tür | Kural | Ölçüm | İhlalde cevap | Kaynak |
|---|---|---|---|---|---|
| E-01 | K | 2, 1'in başlangıcına ulaşmaz (tam %100 de geçersiz) | Y | "2 (x) 1'in başlangıcını (y) geçti; bu 1-2 etiketi biter. Sonradan yükselmesi düzeltmez." | B2, B3, T, V, A |
| E-02 | K | 3, 1'in sonunu geçer | F | "3 (x) 1'in sonunu (y) geçemedi." | B3 |
| E-03 | K | 3, 1-3-5 içinde fiyat mesafesi olarak **en kısa olamaz** (en uzun olması şart değil) | F | "[1]=…, [3]=…, [5]=…: 3 en kısa." | B2, B3, T, V |
| E-04 | K | 4, 1'in fiyat alanına girmez; **bütün yolu** sayılır (fitil dahil), değmek de ihlal | Y | "4 (x) 1'in sonuna (y) girdi. Diyagonal için ayrıca E-20…E-26 gerekir." | B2, B3, T, V, A |
| E-05 | K | İç yapı 5-3-5-3-5: 1-3-5 ilerletici beşli, 2-4 düzeltici | İ | "n. dalganın içi beşli/düzeltici değil." | B2, B3, T, V |
| E-06 | K | **3 mutlaka itkidir** (diyagonal olamaz). 1 ve 5 diyagonal olabilir | İ | "3 diyagonal görünüyor; sayım elenir." | B3, B4 |
| E-07 | K | 4, 3'ün tamamını geri alamaz (E-04'ün doğal sonucu; diyagonalde ayrıca E-23) | Y | | B3, B4 |
| E-08 | K | Alt dalgalar da kendi içinde aynı kurallara uyar (fraktal) | İ | "Ana sayım tamam ama 3'ün içinde E-04 bozuk." | B2, B10, V |
| E-09 | K | 2. dalganın tamamı üçgen olamaz (karmaşık 2'nin **içinde** üçgen parçası olabilir) | İ+K | | B5, B10 |

**Kılavuzlar**

| No | Tür | Kılavuz | Kaynak |
|---|---|---|---|
| E-10 | R | 2 = 1'in 0,382 / 0,5 / 0,618'i | T, A |
| E-11 | R | 3 ≈ 1,618 × [1] (2'nin sonundan). Genelde en uzun 3'tür | T, A |
| E-12 | R | 4 = 3'ün 0,236–0,382'si (ideali 0,382) | T, A |
| E-13 | R | 5 = [1] ya da 0,618 × [3] (4'ün sonundan); Aykut: 2-3-4 uzatmasında çoğunlukla 0,618 / 1 / 1,618 | T, A |
| E-14 | R | **Uzama:** biri (bazen birden fazlası) uzar. 3 uzarsa 5 ≈ 1. 1 uzarsa [3] ≈ [5]. 5 uzarsa [1] ≈ [3], [5] = 1,618 × (0→3) ya da 1,618 × [1]. **1 uzadığında [5] = [1] hedefi kullanılmaz:** [3] < [1] iken [5] = [1] olursa 3 en kısa kalır (E-03); üst sınır [5] ≤ [3] | B3, T, hesap |
| E-15 | R | **Alternasyon:** 2 ile 4 biçim, derinlik, süre ya da karmaşıklıkta farklıdır (derinlik: 2'yi 1'e, 4'ü 3'e oranla) | B3, T |
| E-16 | R | [3] > 2,618 × [1] ise güdük 5 riski | T |
| E-17 | R | **Güdük 5:** 3'ün sonunu geçmez ama içi tamamlanmış beşlidir; bitmemiş hareketi "güdük" diye kapatma | B3 |
| E-18 | R | Dalga karakteri / hacim: 3 en güçlü, 5'te zayıflama olağan | B3, T |
| E-19 | R | 3'ten 5'e RSI N.U (aynı derecede) = ivme kaybı; **zamanlama değildir** | B7 |

## 3. Diyagonal

| No | Tür | Kural | Ölçüm | Kaynak |
|---|---|---|---|---|
| E-20 | K | Konum: **öncü** = itkinin 1'i ya da zigzagın A'sı (içi 5-3-5-3-5); **bitiş** = itkinin 5'i ya da zigzag/yassının C'si (içi 3-3-3-3-3). 3. dalga olamaz | K+İ | B4 |
| E-21 | K | 2, 1'in tamamını geri almaz | Y | B4 |
| E-22 | K | 3, 1'in sonunu geçer | F | B4 |
| E-23 | K | 4, 3'ün tamamını geri almaz (2'nin sonunu aşmaz) | Y | B4 |
| E-24 | K | Daralan modelde [1] > [3] > [5]; 3 en kısa olamaz | F | B4 |
| E-25 | R | 4'ün 1 ile örtüşmesi diyagonalin özelliğidir ama **tek başına yeterli değildir** | F | B4, B10 |
| E-26 | K | 1–3 ve 2–4 çizgileri yakınsar, yapı kesişmeden önce biter | F+zaman | B4 |
| E-27 | R | 5 çizgiyi aşabilir (throw-over, 1–3 çizgisine göre); güdüklük 3'ün sonuna göre. İkisi ayrı ölçüdür | B4 |
| E-29 | R | Diyagonalden sonra trend sürebilir ya da dönebilir; trend sonunda dönüş uyarısıdır | T |
| E-28 | R | Genişleyen diyagonal daha seyrek; kontrolü otomatik yapılmıyor | B4 |

Kontrol sırası: konum → ana dalgalar → iç yapı → fiyat kuralları → çizgiler.

## 4. Zigzag (5-3-5)

| No | Tür | Kural | Ölçüm | Kaynak |
|---|---|---|---|---|
| E-31 | K | B, A'nın başlangıcını geçmez | Y | B5, T |
| E-32 | K | A itki (seyrek öncü diyagonal), B düzeltici, C itki ya da bitiş diyagonali | İ | B5 |
| E-33 | R | B = A'nın 0,382 (en sık) / 0,5 / 0,618'i; **0,786 ve üstü şüpheli**, yassıya bak | F | T |
| E-34 | R | C genelde A'nın sonunu geçer; C = A, 0,618 A ya da 1,618 A (B'nin sonundan) | F | B5, B6, T |

Üst derecede 3 parça, altında 5+3+5 = 13 parça: çelişki değil, derece farkı (B2).

## 5. Yassı (3-3-5)

| No | Tür | Kural | Ölçüm | Kaynak |
|---|---|---|---|---|
| E-40 | K | A düzeltici (üçgen olmaz), B düzeltici, **C beşli**. İlk ayırt edici: A'nın içi üçlü mü, beşli mi? C üçlüyse yassı bitmemiştir | İ | B5, B10 |
| E-41 | – | Tip: **normal** (B başa yakın, C, A'nın sonuna yakın/biraz ötesi) · **genişleyen** (B başı aşar, C, A'yı açıkça geçer) · **kaçan** (B başı aşar, C, A'ya ulaşmaz) | F | B5 |
| E-42 | R | B = A'nın %90–138'i; C = A'nın %100–162'si (ders örnekleri %170'e kadar çıkıyor) | F | T, B5 |
| E-43 | R | Kaçan yassı bitmemiş C'ye bahane değildir | İ | B5 |
| E-44 | K | B'nin yeni tepe yapması "düzeltme bitti" demek değildir | – | B5, B10 |

## 6. Üçgen (3-3-3-3-3, A-B-C-D-E)

| No | Tür | Kural | Ölçüm | Kaynak |
|---|---|---|---|---|
| E-50 | K | Konum: 4, B, X ya da birleşik düzeltmenin son parçası; 2'nin tamamı olamaz. D ve E oluşmadan üçgen tamam değildir | K+İ | B5, B10, T |
| E-51 | K | Sınırlar A–C ve B–D; daralanda yakınsar (genişleyen türü de var, otomatik bakılmıyor) | F+zaman | B5 |
| E-52 | K | Daralanda C, A'yı; D, B'yi; E, C'yi geçmez. B'nin başlangıcı aşması serbest | Y | B5 çizimleri + T; ders açık yazmıyor, karar 11.7 |
| E-53 | R | E çizgiye değmek zorunda değil; kısa ya da sahte kırılım olabilir | F | B5, B10, T |
| E-55 | R | Üçgende B genelde A'nın başlangıcını geçmez (geçerse kaçan üçgen; uyarı) | T |
| E-56 | R | E'den sonra çıkış çoğunlukla hızlı, sert ve önceki trend yönünde | T |
| E-54 | K | Beş parça + daralma üçgeni itki yapmaz: üçgen **karşı** yönde/yatay, bitiş diyagonali **ana** yönde ilerler | K | B10 |

## 7. Karmaşık düzeltme (W-X-Y, W-X-Y-X-Z)

| No | Tür | Kural | Kaynak |
|---|---|---|---|
| E-60 | K | W, Y (Z) kendileri düzeltmedir; X onları bağlayan düzeltmedir | B5, V |
| E-61 | K | ABC bozuldu diye sonradan W-X-Y denmez | B5 |
| E-63 | R | Birleşik yapı (ör. W zigzag + Y yassı) **yatay** ilerler: X, W'nin b'sini; Y ise W'nin sonunu geçmek zorunda değil | T (grafik) |
| E-62 | K | Tür belli değilse "düzeltme sürüyor, tür belirsiz" yazılır; **plan üretilmez** | B5, T |

## 8. Fibonacci ölçümü (Elliott içinde; ayrıntı Fibonacci bölümünde)

| No | Tür | Kural | Kaynak |
|---|---|---|---|
| E-70 | K | Önce kural, sonra oran. Oran uyuyor diye bozuk sayım kurtulmaz | B6 |
| E-71 | K | Hangi uzaklık, hangi noktadan: 3 → 2'den, 5 → 4'ten, C → B'den; **giriş fiyatından değil** | B6, B9, B10 |
| E-72 | R | Aynı bacaktan türeyen seviyeler bağımsız kanıt değildir | B6 |
| E-73 | R | 0,786 ≈ √0,618; 0,5 altın oran değil. Zaman izdüşümü ayrı birimdir | B6 |
| E-74 | R | Dalganın herhangi bir Fibonacci oranına denk gelmesi zorunlu değildir (ör. %40 düzeltme geçerli) | B10 |

## 9. Çizgiler ve göstergeler

| No | Tür | Kural | Kaynak |
|---|---|---|---|
| E-80 | R | Kanal 1: 1–3 çizgisi, paraleli 2'den (4 için). Kanal 2: 2–4 çizgisi, paraleli 3'ten (5 için; 3 çok dikse 1'den) | B7 |
| E-81 | R | Zigzag kanalı: A başı – B sonu, paraleli A sonundan | B7 |
| E-82 | K | Kanala değmemek/kırmak sayımı bozmaz: **çizgi kırılması uyarı, kural kırılması eleme** | B7, B10 |
| E-83 | K | Destek/direnç bölgesi hiçbir dalga kuralını gevşetmez | B7 |
| E-84 | R | Bayrak (4) = ABC, flama (4) = üçgen; OBO: sol omuz 3, baş 5, sağ omuz B, boyun 4–A. Boyun kırılması "C bitti" değildir | B7 |

## 10. Süreç, geçersizlik, işlem

| No | Tür | Kural | Kaynak |
|---|---|---|---|
| E-90 | K | 7 adım: büyük resim → başlangıç → derece → iç yapı → kurallar → alternatif → güncelleme | B8 |
| E-91 | K | Her zaman **ana + alternatif**; her değişiklik gerekçesiyle kaydedilir | B8, T |
| E-92 | K | Geçersizlik dereceye bağlıdır: küçük 1-2'nin bozulması büyük sayımı otomatik bitirmez | B8, B10 |
| E-93 | K | 5-3-5 iç sıra iki anlama gelebilir: (1)-(2)-1 ya da A-B-C; ikisi de yazılır | B8, B10 |
| E-94 | K | Kesin kural ihlalinde **fitil yeter**, kapanış beklenmez | B7 |
| E-95 | K | Sayımın geçersizliği ≠ işlem stopu; ikisi ayrı yazılır | B9, B10 |
| E-96 | R | Güvenli bölge: **2 ve 4'ün sonu** (tecrübeliye B/X). Kaçın: 3'ün ortası, 5'in sonu | T |
| E-97 | R | Önce trend: HTF yön, LTF giriş. Planda geçersizlik, mikro geçersizlik, key level | T |
| E-98 | K | Giriş koşulu ölçülebilir (ör. "1h kapanış, düzeltmenin b tepesinin üstünde"); girişte R/R yeniden hesaplanır | B9, B10 |
| E-99 | K | Tek kazanç/kayıp yöntemi ne kanıtlar ne çürütür; elenen işlem kazananlara yazılmaz; kayma ayrıca ikinci kez sayılmaz | B9, B10 |

---

| No | Tür | Kural | Kaynak |
|---|---|---|---|
| E-100 | R | Korelasyon kontrolü: BTC ↔ ETH; altın ↔ gümüş ↔ platin (petrol ↔ altın); S&P ↔ Nasdaq ↔ DJI; DXY ↔ döviz. Korelasyonun bozulması erken uyarıdır (**veri bugün yok**) | T |
| E-101 | R | Haber kaynaklı anormal hareket ve mikro dilim gürültüsü doğrudan sayıma katılmaz | T |
| E-102 | K | Sayım bozulduysa o sayıma dayanan işlem planı da bozulmuştur | T |

## 11. Kaynaklar çelişince — kararlar (23 Kas; Aykut seçimi bana bıraktı)

| # | Konu | Eğitim | TraderLex / önceki kural | Karar |
|---|---|---|---|---|
| 1 | Zigzagda derin B | yalnız başlangıcı geçemez | 0,786+ zigzag değil | **Kesin değil, uyarı** (E-33). Kod bugün eliyor |
| 2 | İhlal: fitil mi, kapanış mı | kesin kuralda fitil | RULES.md 7: iptal kapanışla | Sayım **fitille** elenir; **dönüş onayı** günlük/haftalık kapanışla kalır. İkisi ayrı şey |
| 3 | Yassıda C üst sınırı | örneklerde %170'e kadar | %161,8 | Kılavuz; eleme yok |
| 4 | 4'ün derinliği | oran zorunlu değil | ≈ 0,382 | Kılavuz (uyum puanı) |
| 5 | 3'ün en uzun olması | şart değil | Aykut: genelde en uzun | Kılavuz (E-11) |
| 6 | Güvenli giriş | giriş filtresi ister | 2/4 sonu; 5'in sonu riskli | Yeni backtest **2/4 sonlarını** sınasın |
| 7 | Daralan üçgende C>A, D>B, E>C (E-52) | açık yazmıyor | D genelde B'yi geçmez | **Kesin**; D = B (yatay/bariyer üçgen) ayrı türdür, daralan sayılmaz |

**TraderLex grafiklerinin kendi metniyle çeliştiği yerler** (8 grafiğin hepsi tek tek incelendi; çelişince **metin** alındı, çizimden ölçüm yapılmadı):

| Grafik | Çelişki | Alınan |
|---|---|---|
| 5 uzayan | not kutusu "1 en büyük, [3] ≈ [5]" diyor (1 uzayandan kalma) | [1] ≈ [3], 5 en uzun |
| 5 uzayan | "[5]" oku 0 çizgisinden 5'e çizilmiş | [5], 4'ün sonundan ölçülür |
| 3 uzayan | "[5] = [1]" oku 4'ten değil 0 çizgisinin altından başlıyor | 4'ün sonundan |
| 1 uzayan | 2, çizimde 0 seviyesine inmiş; 3, 1'den uzun çizilmiş | E-01 ve "1 en uzun" |
| 1 uzayan (metin) | [5] = [1] | E-14: 3'ü en kısa bırakır, kullanılmaz |
| Diyagonal | "3 en kısa olmak zorunda değildir" | metin: 3 hiçbir zaman en kısa olamaz (E-24) |
| Diyagonal | örtüşme "kural" gibi yazılmış | özellik, tek başına kanıt değil (E-25, eğitim) |
| Zigzag | "C ≈ A" örneğinde B çizgileri %61,8'de bitiyor | aralık 0,382–0,618 |

## 12. Bugünkü kodun durumu (`signals/patterns/elliott.py`)

Derslerdeki 18 itki/diyagonal örneğinin hepsinde tarayıcının "geçerli/geçersiz" kararı ders cevabıyla aynı. Eksikler:

| Kural | Durum |
|---|---|
| E-01, 02, 03, 04 (uçlar) | ✅ |
| E-04 (yol/fitil) | ⚠ yalnız ZigZag noktaları; arada küçük fitil kaçabilir |
| E-05, 06, 08 (iç yapı) | ❌ hiç bakılmıyor |
| E-14 | ⚠ hata: [1] ≈ [3] iken [1] biraz uzunsa "5 uzar" yerine "1 uzar" diyor |
| E-20, 26 (diyagonal konum, yakınsama) | ❌ |
| E-33 | ⚠ kılavuz olması gerekirken eliyor |
| E-40 (A üçlü mü beşli mi) | ❌; kaçan/genişleyen ayrımı da yok |
| E-50…54 üçgen, E-60…62 W-X-Y | ❌ |
| E-91 (ana + alternatif) | ⚠ aday listesi var, backtest yalnız en iyisini kullanıyor |
| E-96 (2/4 sonu girişi), E-97 (HTF yön) | ❌ v0 backtest'i dersin "kaçın" dediği 5. dalga bölgesini ölçtü |

`signals/rules/elliott_check.py` (bu listeyle aynı numaralar) yalnızca sorulan sayımı yargılar ve çizer; tarayıcıya ve backtest'e
henüz bağlı değil.

## 13. Kayıt

| Ders | Okunan | Not |
|---|---|---|
| Elliott eğitimi 1–10 | metin, sorular, bütün gizli cevaplar | M10'daki 24 soru dahil |
| TraderLex Elliott rehberi | 14 bölüm metni + 8 grafiğin hepsi (3/5/1 uzayan, zigzag, üçgen, yassı, diyagonal, W-X-Y) | Grafik dosyaları kopyalanmadı; kendi çizimlerimiz var |
| TraderLex "Understanding the Elliott Wave Chart" (4:03) | kareler | Ses dinlenemedi, altyazı yok; altındaki 2 yorum bilgi içermiyor |
