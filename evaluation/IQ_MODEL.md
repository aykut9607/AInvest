# Financial IQ girdi–çıktı modeli: v2 ve v3

Bu not `evaluation/iq_model.html` sayfasının yöntemini ve ana sonuçlarını özetler. Sayfa ve buradaki sayılar
`py -3 evaluation/iq_model.py` ile üretilir (tohum 42). Sayfa iki puanlayıcıyı karşılaştırır: **v2** (donmuş kopya,
`evaluation/out/scorer-v2/`) ve **v3** (depodaki Release derlemesi, v3c-i5). Her skor C# kurallarından gelir
(`FinancialIqCommandManager.CalculateScore`, `FinancialIQ.BatchScorer` aracıyla). Skor Python'da ya da tarayıcıda
yeniden hesaplanmaz; Python yalnızca girdi profillerini kurar, puanlayıcıları çağırır ve çıktıyı özetler.

## 1. Biçimsel model

Girdiler iki sürümde aynı (TL, üst sınır yok): aylık gelir *I* > 0, aylık gider *E*, aylık taksit *P*, toplam borç
*D*, nakit *C*, yatırım *V* (hepsi ≥ 0) ve sabırsızlık *S* ∈ {1, …, 5} (öz-beyan).

### 1.1 v2: basamaklı faktörler ve TL kuralları

| Simge | Tanım |
| --- | --- |
| *N* | net borç = *D* − *C* − *V* (negatifse net servet *W* = −*N*) |
| *Y* | max(*N*, 0) / (12·*I*), yıllık gelir cinsinden net borç |
| *R*, *M* | rezerv *C* + 0,5·*V*; *M* = *R* / *E* ay (*E* = 0 iken *R* > 0 → 6) |
| *p*, *s*, *e* | *P*/*I*, (*I* − *E* − *P*)/*I*, *E*/*I*; dikkat: *s* = 1 − *e* − *p* |

- F1 acil durum fonu = 25 [*M* ≥ 6], 15 [≥ 3], 8 [≥ 1], 0
- F2 borç yükü = min(g(*p*), h(*Y*)); g = 25 [*p* ≤ 0,10], 15 [≤ 0,20], 8 [≤ 0,36], 0; h = 25 [*Y* ≤ 0,5], 15 [≤ 1], 8 [≤ 3], 0
- F3 tasarruf = 25 [*s* ≥ 0,20], 15 [≥ 0,10], 8 [≥ 0], 0
- F4 gider oranı = 15 [*e* ≤ 0,40], 9 [≤ 0,60], 5 [≤ 0,80], 0
- F5 sabırsızlık = 10, 8, 5, 2, 0 (*S* = 1 … 5)

Skor = F1 + … + F5. Kurallar bu sırayla skoru belirler: (1) *I* ≥ 1.000.000 ve *Y* ≤ 1 → 100; (2) *W* ≥ 10.000.000
→ 100; (3) *I* < 1.000.000 ve *N* ≥ 100.000.000 → 0. Segment: LOW 0–40, MEDIUM 41–70, HIGH 71–100.

### 1.2 v3 (v3c-i5): doğrusal paylar, ödeme gücü tavanı, servet pisti

Şartname: `evaluation/IQ_V3_PROPOSAL.md` bölüm 8.

| Simge | Tanım |
| --- | --- |
| *L* | likit varlık = *C* + 0,5·*V* |
| *E*′ | gider tabanı = max(*E*; 0,1·*I*) |
| *O*, *m* | aylık çıkış *E*′ + *P*; rezerv *m* = *L* / *O* ay |
| *X*, *N*, *y* | fon hedefi üstü max(0; *L* − 6·*O*); net borç max(0; *D* − *X*); *y* = *N* / 12*I* yıl |
| *P*′, *r*, *s* | etkin taksit max(*P*; 0,035·*N*); *r* = *P*′/*I*; *s* = (*I* − *E*′ − *P*′)/*I* |
| *W*, *R* | likit net servet *L* − *D*; pist *R* = *W*⁺ / (12·*E*′) yıl |

Paylar çapalar arasında doğrusal, dışında sabit: rezerv *m* 0/3/6 ay → 0/0,6/1; taksit *r* %10/20/36/50 → 1/0,6/0,2/0;
net borç *y* 0,5/1/3/5 yıl → 1/0,6/0,2/0; tasarruf *s* −%10/0/10/20 → 0/0,2/0,6/1; sabırsızlık 1…5 → 1/0,8/0,6/0,2/0.
Servet pisti λ = min(*R*/25; 1) taksit ve tasarruf paylarını en az λ'ya kaldırır. Tavan κ, *y* 5 yıldan 15 yıla
çıkarken 1'den 0'a iner ve her faktörü çarpar. Faktör puanı = yuvarla(maks × pay × κ), yarım yukarı; maksimumlar
acil fon 30, taksit oranı 25, net borç 10, tasarruf 30, sabırsızlık 5. Skor = faktörlerin toplamı. `appliedRule`
yalnız etiket: κ < 1 → SOLVENCY_CAP; pist en az 5 yıl ve skoru pistsiz skordan yükseltiyorsa → WEALTH_RUNWAY.
Segment sınırları aynı.

### 1.3 Ölçülen bağımlılıklar

Her iki akış şeması ölçülmüş bağımlılık matrisiyle denetlendi; ikisi de uyumlu. v3 şemasındaki "gelir → acil fon"
yolu (gider tabanı) sınama örneğinde hiç işlemedi, çünkü orada gider en az gelirin %20'si.

| Girdi | v2: faktörler (en yüksek puan) | v3: faktörler (en yüksek puan) |
| --- | --- | --- |
| Gelir | borç yükü, tasarruf, gider oranı + 3 kural (65) | taksit, net borç, tasarruf (65) |
| Gider | acil fon, tasarruf, gider oranı (65) | acil fon, taksit, net borç, tasarruf (95) |
| Taksit | borç yükü, tasarruf (50) | acil fon, taksit, net borç, tasarruf (95) |
| Toplam borç | borç yükü + kurallar (25) | taksit, net borç, tasarruf (65) |
| Nakit, yatırım | acil fon, borç yükü + kurallar (50) | acil fon, taksit, net borç, tasarruf (95) |
| Sabırsızlık | sabırsızlık (10) | sabırsızlık (5) |

v3'te neredeyse her parasal girdi dört faktöre dokunuyor, ama etkileri küçük ve sürekli. Tavan (κ) bütün faktörleri
çarptığı için ayrıca bütün girdiler skora tavan üzerinden de ulaşıyor; matris tavanlı durumları dışarıda bırakıyor.

## 2. Parametreler ve dayanakları

### 2.1 v2 eşikleri

Dayanak düzeyleri ekibin YÖK/literatür araştırmasından. Her eşik iki profille sınandı: biri tam eşikte, biri 1 TL
ötesinde; hepsi koddaki yerinde çıktı. Aynı çiftlerde v3'ün skoru hiç değişmiyor.

| Parametre | Değer | Dayanak | Kaynak |
| --- | --- | --- | --- |
| Yatırımın rezerve sayılan payı | 0,5 | kısmi | Basel III LCR likidite iskontosu benzetmesi |
| Rezerv ≥ 6 ay | 25 | kısmi | 6 aylık fon önerisi |
| Rezerv ≥ 3 ay | 15 | güçlü | Greninger ve ark. 1996 (156 uzmanlı Delphi) |
| Rezerv ≥ 1 ay | 8 | dayanaksız | – |
| Taksit/gelir ≤ %10, ≤ %20 | 25, 15 | güçlü | Greninger ve ark. 1996 |
| Taksit/gelir ≤ %36 (eşik değeri) | 8 | kısmi | 28/36 kuralı (Fannie Mae) |
| Taksit/gelir > %36 kırılgan bant | 0 + uyarı | güçlü | Greninger ve ark. 1996 |
| Net borç ≤ 0,5 / 1 / 3 yıllık gelir | 25 / 15 / 8 | dayanaksız | – |
| Tasarruf ≥ %20 / ≥ %10 / ≥ 0 | 25 / 15 / 8 | kısmi / güçlü / dayanaksız | 50/30/20; Greninger; – |
| Gider/gelir ≤ %40, ≤ %60 / ≤ %80 | 15, 9 / 5 | dayanaksız / kısmi | – |
| Sabırsızlık eşlemesi | 10/8/5/2/0 | dayanaksız | tek maddelik öz-beyan |
| Ağırlıklar | 25/25/25/15/10 | uzman görüşü | ekip kararı |
| LOW ≤ 40 / HIGH ≥ 71 | | kısmi / dayanaksız | FinHealth (<40 kırılgan, ≥80 sağlıklı) |
| Üç TL kuralı | | dayanaksız | incelenen literatürde emsali yok |

### 2.2 v3 çapaları

Her çapa, tam çapanın üstünde duran bir profille puanlayıcıdan okundu. Ölçülen puanların hepsi pay × maksimuma
eşit, örneğin rezerv 3 ay → 18 (= 0,6 × 30).

| Çapa / mekanizma | Pay | Dayanak | Ölçülen (v3) |
| --- | --- | --- | --- |
| Rezerv 0 / 3 / 6 ay | 0 / 0,6 / 1 | yargı / güçlü / kısmi | 0 / 18 / 30 |
| Taksit/gelir %10 / 20 / 36 / 50 | 1 / 0,6 / 0,2 / 0 | güçlü / güçlü / güçlü / yargı | 25 / 15 / 5 / 0 |
| Net borç 0,5 / 1 / 3 / 5 yıl | 1 / 0,6 / 0,2 / 0 | dayanaksız (v2 eşikleri); 5 yargı | 10 / 6 / 2 / 0 |
| Tasarruf %20 / 10 / 0 / −10 | 1 / 0,6 / 0,2 / 0 | kısmi / güçlü / yargı / yargı | 30 / 18 / 6 / 0 |
| Sabırsızlık 1…5 | 1 / 0,8 / 0,6 / 0,2 / 0 | dayanaksız | 5 / 4 / 3 / 1 / 0 |
| Likit pay 0,5 | | kısmi (Basel LCR 2B) | nakit 105 bin = yatırım 210 bin: 18 / 18 |
| Yalnız fon hedefi üstü borçtan düşer | | kısmi (6 ay) | hedef üstü 0 / 0,6 / 1,2 Mn: net borç 5 / 6 / 10 |
| Faiz tabanı %3,5 / ay | | yargı | taksit 5 bin ya da 42 bin: aynı puan 3 / 3 + uyarı |
| Gider tabanı %10 | | yargı | gider 0 = gider 10 bin: skor 100 / 100 + uyarı |
| Tavan κ: 5 / 10 / 15 yıl | 1 / 0,5 / 0 | yargı (%36 ile 14 / 42 yıl) | skor 35 / 18 / 0 |
| Pist λ: 0,5 / 12,5 / 25 yıl | 0,02 / 0,5 / 1 | kısmi (Bengen 1994) | tasarruf 12 / 15 / 30 |
| Ağırlıklar | 30/25/10/30/5 | uzman görüşü | `factorMaximums` |

## 3. Yöntem

- **Bağımlılık matrisi.** Geniş bir örnekte (600 profil; borç ve taksit birbirinden bağımsız çekildi, böylece her
  yapısal bağ sınanıyor) her girdi yarıya indirildi ve 1,5 katına (+ yarım aylık gelir) çıkarıldı (7.626 sınama).
  Hücre: faktör puanının değiştiği sınama payı. Skoru bir kuralın belirlediği (v2) ya da tavanın ölçeklediği (v3)
  durumlar hariç; v3'ün servet pisti dahil, çünkü yalnız iki faktörü kaldırıyor. *Etkin ağırlık* = cov(faktör, skor)
  / var(skor), Sobol nüfusunda; toplamı 1. v3'ün maksimumları `factorMaximums`'tan, v2'ninki gözlenen en yüksek puanlardan.
- **Tek girdi taramaları.** 8 demo kişisi (`infra/seed/seed_demo_users.py`) etrafında her girdi 401 noktada taranır.
  İkinci tur, skorun 2 puan ya da fazla sıçradığı aralıkları tam sayı TL'lerle yeniden tarar (v2'nin basamakları);
  v3'ün 1 puanlık doğrusal adımları inceltilmez.
- **Uçurum metriği.** Örnek nüfusun 2.048 profilinde her parasal girdi ±%1 değiştirilir; profil başına ölçü
  max |Δskor|. Ayrıca 28 sınama çiftinde (eşikler ve elle kurulmuş uçurum örnekleri) 1–2 TL'lik değişikliğin etkisi.
- **Isı haritaları.** (a) tasarruf oranı × rezerv ayı; (b) gelir × net servet. Kural ve etiket bölgeleri çerçeveli;
  sayfada v2, v3 ve fark (v3 − v2) görünümleri var.
- **Sobol indeksleri.** Saltelli örneklemesi: bağımsız tekdüze A, B (N = 1.024, d = 7) ve AB<sub>i</sub>;
  puanlayıcı başına 9.216 puanlama. Birinci derece Saltelli 2010, toplam Jansen 1999; %95 aralıkları 300 bootstrap.
- **Örnekleme dağılımları.** Yedi bağımsız değişken; tutarlar gelirle çarpılarak TL'ye çevrilir.

  | Değişken | Dağılım |
  | --- | --- |
  | Gelir düzeyi | %90 log-tekdüze 15.000–150.000; %10 log-tekdüze 150.000–2.500.000 |
  | Gider / gelir | tekdüze 0,20–1,10 |
  | Borç / yıllık gelir | %44 borçsuz (TBB: yetişkinlerin ~%56'sının kredisi var); %52 log-tekdüze 0,05–2,5; %4 log-tekdüze 2,5–40 |
  | Geri ödeme vadesi → taksit | borçluda vade log-tekdüze 6–240 ay; aylık faiz vadeyle %4'ten %1,5'e iner (kısa tüketici kredisi → uzun konut kredisi); taksit = annüite, en fazla gelirin %60'ı. Borçsuzların %10'unda borçsuz taksit (gelirin %2–12'si; nüfusun %4,4'ü) |
  | Nakit / aylık gelir | %15 sıfır; %82 log-tekdüze 0,1–24; %3 log-tekdüze 24–240 |
  | Yatırım / aylık gelir | %40 sıfır; %57 log-tekdüze 0,5–48; %3 log-tekdüze 48–600 |
  | Sabırsızlık | 1–5 eşit olasılıklı |

  Taksit ayrı bir değişken değil, borçtan ve vadeden türetiliyor. Bu yüzden Sobol tablosunda **taksit satırı vadenin**
  (geri ödeme yoğunluğunun) etkisini ölçer, **borç satırı taksitin büyüklüğünü de içerir**. Faiz tabanı yalnız vadenin
  ya da gelirin %60'ını aşan borç servisinin onu bağlayıcı yaptığı profillerde devreye giriyor (%16,3; öneri
  belgesinin kalibre nüfusunda %17,1). Gelir düzeyinin indeksi, oranlar sabitken gelir düzeyinin etkisidir.
- **Örnekleme değişikliği (25 Kas).** İlk sürümde borç ve taksit bağımsız çekiliyordu; faiz tabanı profillerin
  %35'inde bağlıyor, %22,6'sında borçsuz taksit vardı. Örnekleme yukarıdaki gibi bağlandı. **v2'nin nüfus
  sayıları (Sobol, uçurum payları, segmentler) da bu yüzden değişti; v2'nin kuralları değişmedi.**
- **En ucuz +10 puan.** Her kişi ve girdi için olumlu yönde aday ızgarası ve iki inceltme turu; sonuç 1 TL'ye kadar
  kesin. ★ = yüzde olarak en küçük parasal değişiklik.

Toplam: iki puanlayıcı, 211.373 puanlama, 6 süreç, yaklaşık 16 saniye.

## 4. Sonuçlar: v2 → v3

| Ölçü | v2 | v3 |
| --- | --- | --- |
| 1–2 TL'lik sınama çiftlerinde en büyük \|Δskor\| | 100 | 0 |
| ±%1 tek girdi: en büyük \|Δskor\| | 95 | 3 |
| ±%1 ile skoru oynayan / ≥ 5 puan oynayan profil | %10,3 / %9 | %40,9 / %0 |
| Ortalama skor | 60,3 | 66,5 |
| LOW / MEDIUM / HIGH | %26,7 / %34,9 / %38,4 | %20,1 / %28 / %51,9 |
| Sabırsızlık 5 → 1 kazancı | 10 | 5 |
| Faiz tabanı bağlıyor / taksit var borç yok / tavan | – / – / <%0,1 (EXTREME_DEBT) | %16,3 / %4,4 / %3,2 |

v3'te skor daha sık ama çok daha az oynuyor: ±%1'lik değişikliklerin hepsi en fazla 3 puan. Bu örnek nüfusta v3
daha cömert (HIGH %51,9); nüfusun %44'ü borçsuz ve onlar taksit ve net borç puanını tam alıyor. Örnek nüfus Türkiye
payına kalibre değil; kalibre nüfusta v3c-i5'in HIGH payı %26,3 (öneri belgesi, bölüm 6).

### Sobol indeksleri (birinci derece / toplam)

| Değişken | v2 | v3 |
| --- | --- | --- |
| Borç (taksiti de büyütür) | 0,38 / 0,41 | 0,61 / 0,67 |
| Gider | 0,27 / 0,35 | 0,14 / 0,18 |
| Nakit | 0,05 / 0,11 | 0,06 / 0,12 |
| Yatırım | 0,07 / 0,13 | 0,06 / 0,10 |
| Vade (taksiti belirler) | 0,02 / 0,05 | 0,002 / 0,05 |
| Sabırsızlık | 0,02 / 0,02 | 0,01 / 0,004 |
| Gelir düzeyi | 0,09 / 0,12 | 0 / 0 |

- Gelir düzeyinin etkisi v2'de yalnız TL kurallarından geliyordu; v3'te TL eşiği olmadığından sıfır.
- Borç iki sürümde de en etkili değişken; taksit borçtan türetildiği için borcun indeksi taksitin büyüklüğünü de
  taşıyor. v3'te daha da baskın, çünkü borç dört faktöre (taksit, net borç, tasarruf ve tavanla hepsine) ulaşıyor.

### Etkin ağırlık (nominal)

- v2: acil fon %19,9 (%25), borç yükü %27 (%25), tasarruf %35,5 (%25), gider oranı %14 (%15), sabırsızlık %3,5 (%10).
- v3: acil fon %26,2 (%30), taksit %29,2 (%25), net borç %6 (%10), tasarruf %37,9 (%30), sabırsızlık %0,8 (%5).

### Demo kişileri ve en ucuz +10 puan

| Kişi | v2 skor / en ucuz +10 | v3 skor / en ucuz +10 |
| --- | --- | --- |
| Zayıf | 8 / gelir +2.000 TL (+%6,7) | 27 / gelir +3.247 TL (+%10,8) |
| Orta | 62 / gider −10.000 TL (−%33,3) | 71 / gider −18.800 TL (−%62,7) |
| Güçlü | 88 / gider −3.000 TL (−%37,5) | 87 / gider −4.419 TL (−%55,2) |
| Gizli borç | 63 / gider −7.667 TL (−%47,9) | 22 / gider −8.244 TL (−%51,5) |
| Çok yüksek gelir | 100 (VERY_HIGH_INCOME) / – | 53 / gider −79.167 TL (−%8,8) |
| Çok yüksek servet | 100 (VERY_HIGH_WEALTH) / – | 84 (WEALTH_RUNWAY) / gider −4.625 TL (−%15,9) |
| Aşırı borç | 0 (EXTREME_DEBT) / borç −9.904.001 TL (−%8,3) | 0 (SOLVENCY_CAP) / borç −109.184.002 TL (−%91) |
| Gelişim (son) | 92 / – | 97 / – |

v3 demo skorları öneri belgesindeki v3c-i5 değerleriyle birebir aynı. v3'te +10 puan, v2'deki basamak atlamalarına
göre daha büyük ama kademeli değişiklik istiyor. Aşırı borç kişisi tavandan ancak borcun %91'i kapanınca çıkıyor.

## 5. Sınırlar

- **Örnek nüfus sentetik.** Sobol, etkin ağırlık ve segment payları seçilen dağılıma bağlı. Borç ile taksit artık
  vadeyle bağlı, ama faiz oranı–vade ilişkisi, %60 servis sınırı ve borçsuz taksit payı varsayım. Türkiye payına
  kalibre nüfus için `iq_eval_v3.py`'ye bakın.
- **Sobol indeksleri varyansa dayanır**; basamaklı bir fonksiyonda uçurumları göstermez. Bu yüzden uçurum metriği
  ve taramalar ayrıca verildi.
- **Akış şemaları elle çizildi**; ölçülmüş matrisle denetleniyor. Başka bir faktör düzeni eklenirse şeması yoktur.
- **Servet pisti etiketi** artık yalnız pist en az 5 yıl olduğunda yazılıyor; örnek nüfusta %2,3, ısı haritası (a)'da
  hiç yok (orada nakit en çok 12 aylık gider). Skorlar bu değişiklikten etkilenmedi.
- **"En ucuz"** göreli değişikliktir; aylık (kalıcı) ve tek seferlik değişiklikler aynı ölçekte değildir.
- **Donmuş v2 kopyası** `evaluation/out/scorer-v2/` altında ve git dışında; yoksa bölüm 6'daki gibi yeniden derlenir.

## 6. Yeniden üretme

```powershell
py -3 evaluation/iq_model.py                      # v2 (evaluation/out/scorer-v2) ve v3 (depodaki Release)
py -3 evaluation/iq_model.py --scorer v3=services/financial-iq-service/src/FinancialIQ.BatchScorer   # yalnız v3
```

`--scorer ETİKET=YOL` bir DLL ya da proje klasörü alır ve tekrarlanabilir. Her puanlayıcı Release derlenmiş olmalı.
Faktör düzeyindeki bölümler her puanlayıcının kendi faktör anahtarlarını kullanır.

**Donmuş v2 puanlayıcısını yeniden kurmak** (`evaluation/out/` git dışında olduğu için başka bir makinede yoktur;
üretici bu durumda aynı talimatı yazar):

```powershell
git worktree add ../AInvest-v2 a03d197
dotnet build ../AInvest-v2/services/financial-iq-service/src/FinancialIQ.BatchScorer -c Release
py -3 evaluation/iq_model.py --scorer v2=../AInvest-v2/services/financial-iq-service/src/FinancialIQ.BatchScorer --scorer v3=services/financial-iq-service/src/FinancialIQ.BatchScorer
```

Ya da `../AInvest-v2/services/financial-iq-service/src/FinancialIQ.BatchScorer/bin/Release/net10.0` klasörünün
içeriğini `evaluation/out/scorer-v2/` altına kopyalayın; sonra düz `py -3 evaluation/iq_model.py` yeter.

Ara dosyalar `evaluation/out/iq_model_*.json` (git dışı); özet `evaluation/out/iq_model_summary.json` (depoda).
Seçenekler: `--seed`, `--sobol-n`, `--bootstrap`. Canlı deneme:
`services/ai-rag-service/venv/Scripts/python evaluation/playground.py` → `http://127.0.0.1:8090`.
