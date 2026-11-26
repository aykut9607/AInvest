# Book data: kitaplardan çıkan kurallar (v1, 24 Kasım 2026)

Ayrı kategori; **hiçbiri ölçülmedi**, backtest sonra. Fikirler kendi cümlelerimizle; kitap metni ve görseli kopyalanmadı.
Görseller: [book-visuals.html](book-visuals.html). Kod: `book_detect.py`.
**Tür:** T = testi yapılabilir grafik kuralı · F = filtre · D = davranış/risk. **Ö** = sayı bizim, kitapta yok.

## 1. VWAP (Terence V. Gronowski, *The VWAP Strategy*, 2019)
| No | Tür | Kural |
|---|---|---|
| BK-01 | T | VWAP = Σ(fiyat × hacim) / Σ hacim, her gün 00:00'da başlar; **çizgi değil bölge**. Başlangıç saati sonucu değiştirir (bizde 00:00 UTC, Ö; kitap Avrupa gece yarısı ve ABD gece yarısı) |
| BK-02 | F | VWAP **sinyal vermez**, yön filtresidir: üstünde long, altında short aranır |
| BK-03 | F | VWAP'a yakınken işlem yok; fiyat–VWAP kesişimi işlem sebebi değil (tuzak bölgesi). Yakın = 0,5 sapma (Ö) |
| BK-04 | T | Ters yön yalnız **en az 1, tercihen 2 standart sapma** uzaktayken ve 5m'de çift tepe/dip + yeni trend oluşunca |
| BK-05 | T | VWAP'a doğru işlemde hedef VWAP'a **varmadan**; giriş–VWAP arası en az 2R (kitap: 10 puan stop için 30 puan yer), yoksa işlem yok |
| BK-06 | F | Büyük yapı önce: yükseliş trendinde VWAP altına iniş long fırsatı olabilir, düşüş trendinde short |
| BK-07 | F | Nakit ve vadeli VWAP'ı farklıysa hacmi büyük olan esas |
| BK-08 | F | **Yatay piyasa listesi:** fiyat VWAP / POC / değer alanında · ilk saatin aralığında · ADX < 25 · simetrik üçgen · iç ve dış mumlar · EMA10–EMA20 sürekli kesişiyor · yuvarlak sayıda. Yataysa işlem yok |
| BK-09 | F | Değer alanı çok darsa işlem yok (kitapta Dow 100, DAX 40 puan; bizde ATR'ye oranlanmalı, Ö) |
| BK-10 | T | Açılış aralığı: ABD açılışının ilk saati. Aralığın ve önceki gün H/L'nin üstü/altı başarının arttığı bölge; açılıştan önceki saatler ve ilk 15 dakika kaçınılır |
| BK-11 | T | Trend çizgisi kırılımı göstergelerden önce haber verir; Elliott itkisi aranır. Trend %100 geri alınana kadar bitmiş sayılmaz (0,618 dönüşte işlemde kalınır) |
| BK-12 | D | Önce kâğıt üstünde kanıt; tek piyasada uzmanlaş; iyi işlemlerden oyun kitabı çıkar |

**Dikkat:** kitap istatistik vermiyor, seçilmiş 2019 örnekleri gösteriyor. Kriptoda kapanış yok; "gün" 24 saat. Altın/S&P gün içi verimiz kısa (15m ~60 gün), BTC 2017'den.

## 2. Borsaya Başlayanlar İçin Altın Kurallar (Murat Bayhan, 2000)
| No | Tür | Kural |
|---|---|---|
| BK-20 | T | Aroon (14): Up 70–100'de kalıyor ve Down 0–30 → güçlü yükseliş; tersi düşüş; paralel hareket → sıkışma; kesişme → yön değişimi |
| BK-21 | T | CCI ±100 dışı aşırı; +100 üstünde alım yok; CCI / momentum / stokastik / RSI / Ultimate **uyumsuzluğu** erken uyarı (RSI bizde var) |
| BK-22 | T | 200 günlük EMA ve **21 haftalık EMA**: kapanış üstünde al, altında sat (yalnız trendde; tepeyi dibi yakalamaz) |
| BK-23 | T | MACD (12, 26, 9): tetik kesişimi; sıfır üstü yükseliş. **Yatayda** sık yanlış, stokastik 20/80 yatayda iyi → önce rejim belirlenir |
| BK-24 | F | Osilatör sinyali fiyat onayıyla beraber; gösterge kendi trend çizgisini / desteğini kırabilir (RSI formasyonu, hatalı salınım) |
| BK-25 | T | **Kırılım + hacim:** yüksek hacimle kırılıp dönüşte hacim azalırsa gerçek; düşük hacimle kırılıp dönüşte artarsa tuzak (boğa / ayı). Pencere 20 mum (Ö). Kırılan direnç destek olur (PA ile aynı) |
| BK-26 | F | Yükseliş her gün azalarak sürüyorsa momentum zayıflıyor; sert yükselişten sonra geri çekilme %60'ı bulabilir (0,618 ile uyumlu) |
| BK-27 | T | **Elliott osilatörü** = EMA5 − EMA35: 3. dalga tepesi > 5. dalga tepesi; 4. dalgada sıfıra yaklaşır |
| BK-28 | T | Zigzag: A beş dalga; B genelde %50, **en çok %75**; C = 1 / 1,62 / 2,62 × A. Düzensiz yassı: B = 1,15–1,25, C = 1,62–2,62. Üçgen çoğunlukla 4. dalgada, 3'ün yönüne kopar; B'deyse A'nın yönüne. 2 basitse 4 karmaşık |
| BK-29 | F | İyimserlik anketi > %85 düşüş, < %25 yükseliş belirtisi (anket verimiz yok; funding benzer rol oynar) |
| BK-30 | F | Olumlu habere rağmen yükselemeyen düşer, olumsuz habere rağmen düşmeyen yükselir |
| BK-31 | D | Risk önceden sınırlı · zararı kes · **zarardaki işleme ekleme yok**, ekleme yalnız kârda ve azalarak · emin değilsen işlem yok · çoğunluğa uyma · plan seans içinde değişmez · seri hatada ara ver |
| BK-32 | F | Dibi/tepeyi yakalamaya çalışma: dönüş **kendini kanıtlasın** (bizdeki kapanış + LTF onayı) |
| BK-33 | F | Portföy: eşit ağırlık, sinyal bozulana kadar tut, açıkta kalan pay başka varlığa kaydırılmaz (Portfolio Service fikri) |
| BK-34 | F | Çoklu gösterge süzgeci (fiyat > EMA21, MACD > tetik, RSI ve CCI kendi ortalamasının üstünde, Aroon yukarı, hacim artıyor…) **aday listesidir**, tek başına al değil |

**Çelişkiler:** BK-28'de B sınırı %75; bizde derin B zaten kesin değil **uyarı** (E-33), öyle kalır. BK-22 ile BK-11 farklı çıkışlar: ikisi de ölçülür.
BK-34'teki göstergelerin çoğu aynı bilgiyi (son kapanışlar) ölçer; 12 onay 12 bağımsız kanıt **değildir**.

## 3. Akıllı Borsacı (H. Kürşat Keskin)
Temel analiz ve sözlük bölümleri alınmadı (4.4 ile ilgisi yok).
| No | Tür | Kural |
|---|---|---|
| BK-40 | F | Rejim: dipten **%20 yükseliş** boğa, tepeden **%20 düşüş** ayı piyasası. Evreler: toplama (ilgi az) → alım dalgası (hacim artar) → doygunluk (hacim yüksek ama alıcı azalır) |
| BK-41 | T | Kanal / takoz: üst ya da alt çizgi **kapanışla** kırılınca yön; temkinli giriş bir sonraki **haftalık** mumun teyidini bekler |
| BK-42 | T | Kırılım hedefi = kanalın **en derin yeri** kadar (PA'daki formasyon yüksekliğiyle aynı); çift tepe/dip, üçgen ve OBO'da da yükseklik h |
| BK-43 | F | Desteğe / dirence **yaklaşınca** işlem, tam noktada değil; kâr hedefin biraz altında alınır |
| BK-44 | T | RSI **75 / 25** (9 ya da 14); yalnız **kapanıştan** sonra sinyal; yeni zirvede RSI ve hacim azalıyorsa dönüş işareti (bizde RSI = kapanış, uyumlu) |
| BK-45 | T | 50–100–200 günlük ortalama: fiyat ortalamanın hangi tarafındaysa trend o yönde; kapanışla öbür tarafa geçerse yön değişimi ihtimali artar |
| BK-46 | T | Bollinger: daralma durgunluk; karar yalnız **bant kırılınca**; orta çizgi trendde destek/direnç |

## 4. Trading Psikolojisi (Warren Ramsey, 2020)
1.–3. bölümler kişisel gelişim (alınmadı); 4. bölümün tamamı okundu.
| No | Tür | Kural |
|---|---|---|
| BK-50 | F | Dow: ana trend > 1 yıl, ara trend **3 hafta – 3 ay**, küçük trend < 3 hafta. Ara düzeltme ana hareketin **1/3 – 2/3**'ü (0,382–0,618 ile uyumlu) |
| BK-51 | F | Trend, **tersine döndüğü kanıtlanana kadar** sürer (MSB ilkesiyle aynı); hacim ikincil teyit |
| BK-52 | F | Birbirine bağlı piyasalar teyit etmeli; ayrışırsa dönüş uyarısı (bizde BTC–S&P karşılaştırması, SMT fikri) |
| BK-53 | T | Üç evre: birikim (yatay) → katılım (en uzun, en hızlı) → dağıtım (aşırı, momentum zayıflar) |
| BK-54 | D | İşlem başına %1; küçük hata zinciri: çıkış planı yok · aşırı kaldıraç · zarardakine ekleme · başkasının sinyali · trende karşı tepe/dip avı · sıkıntıdan işlem |
| BK-55 | D | Kazanç serisinden sonra da miktar **artırılmaz**; öfke, yorgunluk, kaygıda işlem yok. "Çok istiyorsan miktar büyüktür" |
| BK-56 | D | Kârın büyük kısmı az sayıda işlemden gelir: günlük tut, en pahalı **tekrarlanan hatayı** bul ve onu kaldır |

## 5. Karar Verme (Nofsinger, Patterson, Shank; akademik makale)
39 öğrencilik deney; hormon ölçümü bizi ilgilendirmiyor, davranış bulguları ilgilendiriyor. **Küçük örnek.**
| No | Tür | Bulgu → bizde |
|---|---|---|
| BK-60 | D | Hedefine ulaşmış kişiler bile **sıralamayı görünce** riski artırdı (beklenen getiri %6,5 → %7,6) → uygulamada kullanıcılar arası sıralama / "diğerleri" karşılaştırması gösterilmez |
| BK-61 | D | Riski hedefe göre ölç: **fazla risk** = seçilen beklenen getiri − hedef için gereken getiri. Portfolio önerisinin gerekçesine uygun |
| BK-62 | F | Çeşitlendirme ölçüsü: **ağırlık karelerinin toplamı** (Herfindahl); küçük = dağınık. Portfolio Service'te doğrudan kullanılabilir |
| BK-63 | D | Stres yükselince risk azalıyor ama **portföy yoğunlaşıyor** ve kaybedene ekleniyor; başarı bir sonraki riski artırıyor (geri besleme) → soğuma süresi hem kayıptan hem büyük kazançtan sonra |

## 6. Alpha Trader (Brent Donnelly, 2021)
En dolu kitap: yazar profesyonel döviz trader'ı ve **"grafik tahmin aracı değildir"** diyor; rastgele stratejiyle RSI/MACD/momentumu karşılaştırıp fark bulmayan
bir çalışmaya (Biondo ve ark., 2013) dayanıyor. **Bizim ölçümlerimizle aynı sonuç.** Teknik analizi giriş, stop ve vazgeçme için kullanıyor.
| No | Tür | Kural |
|---|---|---|
| BK-70 | T | **Haber pivotu:** büyük haberden önceki **son** fiyat ve boşluğun öbür ucu referans seviyesi. Fiyat pivota geri dönerse piyasa haberi reddetti; pivot tutarsa destek/direnç, stop pivotun ötesi |
| BK-71 | T | Destek/direnç **bölgedir**; birden çok kez tutulmuş olmalı, önemli tepe/dip (60 gün, 1 yıl), kırılınca rol değiştirir |
| BK-72 | F | Güçlü trend önemli desteğin üstünde kalır; destekten **zayıf** sıçrayıp sonra kırarsa trend yorulmuştur |
| BK-73 | T | Yüksek hacimle tutulan destek "emilim" (yükseliş); yüksek hacimle kırılan destek gerçek kırılım (BK-25 ile uyumlu) |
| BK-74 | T | **Sapan dönüşü:** herkesin izlediği seviyenin yanlış kırılıp geri alınması en iyi dönüş işareti (bizdeki SFP) |
| BK-75 | T | **Stop mesafesi:** en az **1**, normalde **1,5 ortalama günlük aralık**; çok izlenen seviyenin ardında yarım günlük aralık daha. Daha yakın stop gürültüyle vurulur |
| BK-76 | T | **Yuvarlak sayı:** günlük tepe/dipler 00 ve 50'de yığılıyor. Satış stopu yuvarlak sayının **altına**, alış stopu **üstüne**; alış emri yuvarlak sayının biraz üstünde |
| BK-77 | T | Simetri: çıkış kadar iniş, hem fiyat hem **süre** (M / W bacakları); tek başına sebep değil, 3–4 sebebe eklenir |
| BK-78 | T | Dönüş tetikleri (yalnız önceden görüş varsa): yükselen kama / bitiş diyagonali (kapanış kırılımı, stop tepe), trend sonunda bir-iki **doji**, aşırı hareketten sonra **çekiç** (kapanışta giriş) |
| BK-79 | T | Ortalamalar 55 / 100 / 200 (saatlik): 200 ve eğim trend; üçü düzse yatay, üçü yukarıysa güçlü. Yukarı kesişimden sonra hızlı ortalamaya **geri çekilmede** al, stop yavaşın altı |
| BK-80 | T | **RSI 70/30 yerine kendi geçmişinin en uç %5'i**; kalan ödül azaldığı için pozisyon azaltma noktası (kitaptaki örnek n = 10, küçük) |
| BK-81 | T | **Sapma:** fiyatın 100 saatlik ortalamaya uzaklığı, yine en uç %5. Düşüşte daha uca gider, kademeli gir. Aşırı alım tek başına satış sebebi **değil** |
| BK-82 | F | Duygu/konumlanma çoğu zaman fiyatı takip eder; yalnız **çok uçtan dönmeye başlayınca** ters sinyal. İyimser ama azalıyor + boğa → ayı; kötümser ama azalıyor + ayı → boğa (funding/OI'ye uyar) |
| BK-83 | F | İyi habere rağmen yükselmeyen / kötü habere rağmen düşmeyen piyasa dönüşe yakın (BK-30 ile aynı, ikinci kaynak) |
| BK-84 | F | Olay: olaya **pozisyonsuz** gir; olay bitince olaydan önce beklenen hareket sonuçtan bağımsız gerçekleşebilir |
| BK-85 | F | İlişkili piyasa süzgeci: altın ↔ ABD reel faizi, gümüş; S&P ↔ VIX. Korelasyon **günlük değişimlerden** hesaplanır ve değişkendir. VIX ile hisse birlikte yükseliyorsa uyarı |
| BK-86 | T | Takvim: S&P 16 Eylül – 9 Ekim zayıf, sonra yıl sonu güçlü (1990–2020); ay başı/sonu ve saat başı dönüşleri. **Çoğu mevsimsellik rastgeledir** |
| BK-87 | F | Balon sönümü ~%85 (BTC 2018 %84, Nasdaq %84, 1929 %86): %80–85 düşüşte dip aranabilir (seçilmiş örnekler) |
| BK-88 | F | Piyango işlemi: "az risk, çok kazanç" kalabalıktır; gerçekleşen kayıp planın kat kat üstü olur (boşluk). Beklenen değer **gerçek** stopla hesaplanır |
| BK-89 | D | Risk = önce para tutarı, sonra stop, **miktar en son** çıkar (RK-02). Aynı anda açık işlemler tek risk bloğu (RK-10). Serbest sermayenin %1–3'ü; kazandıkça artır, kaybettikçe azalt |
| BK-90 | D | R/R işlem boyunca değişir; yolda "artık kötü" diye kesilmez, stop sistemli çekilir (12–24 saatte bir). Plan ancak **önceden yazılmış** koşulla değişir: zaman, seviye, haber, ilişkili piyasa |
| BK-91 | D | Önce karşı tez: "yanılıyorsam nasıl görünür?" Giriş, stop, hedef ve gözden geçirme koşulu birlikte yazılır |
| BK-92 | D | Kalıp bulununca: gözlem → **mantıklı neden** → veri → kabul/ret. Nedeni açıklanamayan kalıp elenir (bizim yöntem) |
| BK-93 | D | Başarı %50 civarında sabit, fark **ort. kazanç / ort. kayıp** oranından gelir. Aynı strateji bir yıl 50 bin, öbür yıl 150 bin getirebilir (varyans) → tek dönemlik sonuçla kural övülmez |
| BK-94 | F | Saatlik hacim profili: S&P açılış ve kapanışta, altın Londra girişi + ABD verisi + COMEX kapanışı (13:30 New York) çevresinde yoğun; az hacimde sinyal zayıf |
| BK-206 | T | **Rejim testi 1:** son 10 günde yeni 20 günlük zirve/dip yapıldıysa o yönde trend, yapılmadıysa aralık |
| BK-207 | T | **Rejim testi 2 (100/200 saatlik):** fiyat ikisinin üstünde ve 100 > 200 → yukarı; ikisinin altında ve 100 < 200 → aşağı; öbür bütün durumlar aralık. Günlükte 20 > 50 > 100 sırası |
| BK-208 | T | Rejim değişimi **tahmin edilmez**, kanıtı beklenir: aralıkta dönüş, trendde yönle birlikte; tek stile bağlanılmaz |
| BK-209 | F | **Kriz rejimi** (VIX > 40; 1990'dan beri günlerin %2,2'si): miktar küçülür, stop genişler, aşırı alım/satım ve sapma sinyalleri **geçersiz** (BK-80, BK-81'e istisna) |
| BK-210 | T | Stop alt sınırı: gün içi işlemde ortalama günlük aralığın (5/10/20 gün) en az **1/3'ü**, salınımda en az **1 tam** aralık (BK-75 ile uyumlu) |
| BK-211 | T | Oynaklık ayarı: stop = beklenen günlük aralığın yarısı, hedef = 2 × stop; miktar = risk / stop. VIX'e göre ertesi günün S&P aralığı: < 12 %0,5 · 12–15 %0,7 · 16–20 %1,1 · 21–30 %1,6 · 31–40 %2,3 · > 40 %3,9 |
| BK-212 | T | Örnek yerleşim: stop iki önemli tepenin, günlük aralığın %25'inin **ve** yuvarlak sayının ötesinde; hedef büyük destekten biraz **önce** |
| BK-213 | T | **Trend takibinin kazancı azaldı** (Winton; Sharpe 1984–93 / 94–03 / 2004–13): hızlı 1,85 / 0,85 / 0,00 · orta 1,54 / 1,18 / 0,70 · yavaş 0,95 / 0,94 / 0,38 → backtest **dönemlere bölünür**, yavaş yön daha dayanıklı |
| BK-214 | T | **Arksinüs yasası:** rastgele yürüyüşte de tepe/dip dönemin başında ve sonunda yığılır → "haftanın ucu Pazartesi", "günün ucu açılışta" gibi bulgular **rastgele yürüyüşle** karşılaştırılmadan kural olmaz |
| BK-215 | D | Örnek sayısı 30'dan azsa güvenilmez; eşikle oynayarak sonuç aranmaz; **kaç kalıp denendiği** rapora yazılır (hayatta kalma yanlılığı) |
| BK-216 | D | Rapora **medyan** da yazılır; birkaç uç gün ortalamayı bozar. S&P'nin doğal yukarı eğilimi (gün %53,4, hafta %56,7, ay %60,1; 1946–2020) yazı-tura karşılaştırmasına katılır |
| BK-217 | D | **Planlanan R ile gerçekleşen R** karşılaştırılır; erken kapatma ve stop kaydırma 1'e 2 planı 1,3'e 0,8 yapar ("yavaş kanama") |
| BK-218 | D | Kaybın üç nedeni vardır: yöntemin üstünlüğü yok, plana uyulmadı, varyans. %50 isabette 200 işlemde 7'lik kayıp serisi neredeyse kesin; seri görünce kural değiştirilmez |
| BK-219 | D | Yüksek R tek başına iyi değildir: %5'lik ihtimal abartılır, %85'lik küçümsenir. Puan **olasılık × sonuç** ile verilir |
| BK-220 | D | Süreç/sonuç ayrımı: stopu kaydırıp kurtulan işlem **kötü** işlemdir. Stop olunca 24 saat aynı işlem yok; aynı anda en fazla 3 pozisyon (ters gidince korelasyon artar) |
| BK-221 | D | Çok kazanınca da çok kaybedince de 1–3 gün risk yarıya; birikmiş kârın bir kısmı taban yapılır, altına inilmez |
| BK-222 | T | **Salı dönüşü:** S&P Perşembe ve Cuma düşüp Pazartesi %5'ten fazla düşerse Salı ortalama +%3,3 (1932–2020, yalnız **9** olay; BK-149 ve BK-183 ile birlikte ölçülür) |
| BK-223 | T | **Balon:** short açılmaz; 100 günlük ortalamanın üstünde tutulur, günlük kapanış altına inince çıkılır (kitapta BTC 2017). Tepe işareti: iyi habere yükselmemek |
| BK-224 | F | Altın, hissenin sert düştüğü haftalarda güvenilir liman **değil**; likidite krizinde birlikte düşer |
| BK-225 | F | Boşluk riski: kapalı saat, veri açıklaması, sabitlenmiş fiyat kalkması. "Hiç olmadı" olamaz demek değil → kaldıraç sınırı |

**Bizim için sonuç:** 4.4'ün dili "al/sat" değil **koşullu plan**; güven metni ölçümden. Bu kitap o kararı destekliyor (görüşmede söylenebilir).

## 7. Bir Borsa Spekülatörünün Anıları (Edwin Lefèvre, 1923)
| No | Tür | Kural |
|---|---|---|
| BK-100 | F | Önce **genel koşul** (boğa/ayı), sonra tek varlık; asıl kâr küçük dalgadan değil ana hareketten gelir |
| BK-101 | T | Fiyat **en az direnç** yönünde gider. Dar aralıkta yön tahmin edilmez; aralığın **kırılması** beklenir, kırılınca o yönde girilir (örnekte aralık üstünde **kapanış** sonrası) |
| BK-102 | T | **Deneme pozisyonu + piramit:** küçük ilk alım, kâra geçtikçe ekleme; kâra geçmiyorsa yanlıştır, çıkılır. Ekleme yalnız kârdayken (BK-31 ile aynı) |
| BK-103 | D | Doğruyken **yerinde oturmak** en zoru; erken kâr alma ana hareketi kaçırtır |
| BK-104 | T | Emsalleri düşerken direnen varlık er geç uyar (kitapta tek örnek; tersi de mümkün, ölçülmeli) |
| BK-105 | D | Büyük pozisyon, piyasa **hacimliyken** kapatılır (likidite varken çık) |
| BK-106 | D | Tüyo, umut ve belirli bir ihtiyaç için ("bu para şuna yetsin") işlem yok |
| BK-107 | D | Kârdakini satıp zarardakini tutmak klasik hata; zarardaki kapatılır |
| BK-190 | T | **Emir yoklaması:** küçük satış hemen emiliyorsa alıcı vardır, alıma dönülür. Büyük alış emri **kolay ve ucuza** doluyorsa ilgi yok; giderek pahalıya doluyorsa alım doğru (bizde emir defteri yok: ancak hacim/CVD ile yaklaşık) |
| BK-191 | T | Aralık örneği: 1,10–1,20 arası işlem yok; 1,20'nin **üstünde** al. 1,19 üstü kapanış hazırlık sayılır, girişi kırılım verir |
| BK-192 | D | Kırılım gelmeden kendi alımıyla fiyatı "itmek" işe yaramadı: beş deneme, beş zarar; sonra hareket kendiliğinden geldi |
| BK-193 | T | **Merdiven:** planlanan miktarın küçük bir bölümüyle başla; her +%1 (ya da sabit adım) kârda ekle; son alışın %1 altına stop (Pat Hearne; küçük adım günümüzde ölçülmeli) |
| BK-194 | T | **Yuvarlak sayı ivmesi:** 100 / 200 / 300 **ilk kez** aşılınca hareket hızlanır. Hemen devam etmez ve seviyenin altına dönmeye başlarsa derhal çık (Bethlehem 100: tuttu; Anaconda 300: tutmadı) |
| BK-195 | T | **Haber en az direnç yönünde çalışır:** boğada kötü haber birkaç gün gecikir ya da yok sayılır; ayıda aynı haber düşüşü hızlandırır |
| BK-196 | T | Yön doğru, zaman **erken** ise de iflas ettirir: fiyat dönüşü göstermeden büyük pozisyon yok; ilk deneme zarardaysa ekleme yok, beklenir |
| BK-197 | T | Boğa sonu: aylardır önderlik eden varlıklar ilk kez birkaç puan düşüp **geri çıkamaz**; piyasa henüz dönmemiş olabilir. Önce onlarda azalt/deneme short |
| BK-198 | T | Uzun düşüşten sonra küçük tepki dip değildir; birkaç gün en düşük düzeyde kalma gerekir |
| BK-199 | T | **Grup kuralı:** grubu yükselirken geride kalan varlık "yetişir" diye alınmaz; önce zayıflayan satılır (BK-104'ün tersi; ikisi birlikte ölçülmeli) |
| BK-200 | D | İki pozisyondan **beklenen hareketi yapana** eklenir, yapmayana eklenmez |
| BK-201 | T | Tek fikirde ısrarla zarar büyürken fiyat her düşüşten sonra hemen yeni yükseğe çıkıyordu; bu davranış **ilk kez bozulunca** yön değişti |
| BK-202 | T | Dağıtım tepede değil, tepeden sonraki **düşüş sırasında** yapılır: yüksek hacim + ilerlemeyen fiyat (BK-166 ile aynı fikir) |
| BK-203 | F | Panik ve olağanüstü haberde kazanan pozisyon **likidite varken** kapatılır; düşen fiyatı "açığa satanlar yaptı" diye açıklayan haber güvenilmez |
| BK-204 | T | Önceki başarılı yön, aynı fiyatta tekrar geçerli değildir: kötü piyasada yükselişini sürdüren varlıkta short kapatıldı, sonra alındı |
| BK-205 | D | Kısa vadeli 1–2 puanlık yöntem, emir gecikmesi ve **kayma** yüzünden gerçek borsada çalışmadı → backtest'te ücret **ve** kayma olmalı |

## 8. High Performance Trading (Steve Ward, 2009)
| No | Tür | Kural |
|---|---|---|
| BK-110 | D | **Ödeme oranı** = ort. kazanç / ort. kayıp; 1'in altı → başarı oranı yüksek olmak zorunda (RK-04 ile aynı hesap) |
| BK-111 | D | Rapor ölçüleri: işlem sayısı, kazanma %, ort. kazanç/kayıp, en büyük kazanç/kayıp, **en uzun kazanç ve kayıp serisi, en büyük düşüş**, long/short ayrımı, maliyet → backtest raporumuza eklenecekler |
| BK-112 | D | Hesaba göre fazla risk → kâr erken kapatılır, zarar taşınır |
| BK-113 | D | Hareket başarı değildir: kural dışı / sıkıntıdan işlem fazladan işlemdir |

## 9. Market Mind Games (Denise Shull, 2012)
Psikoloji; grafik kuralı yok.
| No | Tür | Kural |
|---|---|---|
| BK-115 | D | Geçmiş olasılıklar **gelecekte olabilecek her şeyi** içermez (backtest güven metnine yazılacak uyarı) |
| BK-116 | D | Yorgun / uykusuzken karar verilmez; zor gün sonrası ara |
| BK-117 | D | En yaygın bozukluk açgözlülük değil **kaçırma korkusu**: kötü nedenle stopu girişe çekip iyi işlemden atılmak → başa baş stop ancak **kuralla** taşınır (MB-12 ile birlikte ölçülecek) |

## 10. Piyasaları Okumak (Hakan Özerol)
| No | Tür | Kural |
|---|---|---|
| BK-120 | T | Dow: trend çizgisi ihlali **2–3 gün** sürerse kesin sayılır, daha azı yanlış sinyal olabilir |
| BK-121 | F | Hacim trendi teyit etmeli: trend yönünde artan hacim devam, azalan hacim sona yaklaşma |
| BK-122 | F | Birden çok endeks aynı dönüşü göstermeli (BK-52) |
| BK-123 | F | Makro: yalnız **beklentiden sapan** veri bilgidir (RK-41 ile aynı); faiz ile tahvil fiyatı ters yönlü |

## 11. Borsa Sihirbazları (Jack D. Schwager)
| No | Tür | Kural |
|---|---|---|
| BK-130 | T | **Kovner:** dar sıkışmadan, görünür nedeni **olmayan** kırılım en iyisi; haberi yazılmış / herkesin izlediği kırılım zayıf |
| BK-131 | T | **Kovner:** stop, sıkışma aralığının **ortasına değil dışına**; doğruysa fiyat oraya dönmemeli. Önce stop yeri, sonra miktar |
| BK-132 | T | **Marcus:** iyi habere uymayan ya da emsalleriyle birlikte yükselemeyen varlıktan çıkılır (BK-30, BK-83: üçüncü kaynak) |
| BK-133 | D | **Jones:** kötü giderken miktar küçülür, iyi giderken büyür; giriş fiyatına değil bugünkü beklentiye bakılır; ay içi kayıp sınırı |
| BK-134 | D | **Hite:** tek işlemde sermayenin en fazla **%1**'i; en kötü ihtimal önceden bilinir; sisteme müdahale edilmez |
| BK-135 | D | **Hite:** sistemi takvim yılıyla değil **her uzunluktaki tutma süresiyle** ölç (kayan pencerelerin kaçı kârlı) → raporumuza eklenecek |
| BK-136 | D | **Seykota:** sisteme "fazla yükseldi" diye müdahale, yılın en iyi işlemini kaçırdı |
| BK-137 | D | **Schwartz:** büyük kayıptan sonra normalin 1/5–1/10'u ile dönülür; en büyük kayıplar en büyük kazançlardan **sonra** gelir |
| BK-140 | T | **Marcus:** en iyi işlem üç şey aynı anda uyunca: temel + teknik + **piyasanın tavrı** (habere doğru yönde tepki). Yalnız bunlarda büyük pozisyon; öbürleri başa baş kalıyor |
| BK-141 | T | **Marcus:** aşırı tempoda (art arda dikey günler) çıkış: 3. gün dikkat, 4. gün çık |
| BK-142 | D | **Marcus:** tek **fikre** sermayenin %5'inden az; ilişkili iki pozisyon tek fikirdir. Aleyhte ve açıklanamayan hareket → önce çık, sebebi sonra ara |
| BK-143 | D | **Kovner:** işlem başına %1'den az; korelasyonlu 8 pozisyon 8 kat risktir. Yeni başlayan 3–5 kat fazla büyük oynar |
| BK-144 | T | **Kovner:** uzun süre ve çok kez test edilen aralığın kırılması en güveniliri (örnekte bir yıl, 20 test) |
| BK-145 | T | **Kovner:** stop, fiyatın **kolayca ulaşamayacağı** teknik engelin ötesinde; mesafe uzarsa miktar küçülür, dolar riski sabit kalır |
| BK-146 | F | **Kovner:** ayı piyasasında iniş hızlı, tepki sert; satış ani yükselişte yapılır, düşüşe geç katılınmaz |
| BK-147 | D | **Dennis:** kârın %95'i işlemlerin %5'inden; kurallar büyük trendi kaçırmamaya göre kurulur |
| BK-148 | T | **Dennis:** iyi kural **birbirinden farklı piyasalarda** aynı ayarla çalışır; yalnız birinde çalışan kurala güvenilmez → bizde BTC, altın, S&P birlikte ölçülür |
| BK-149 | T | **Dennis:** Cuma güçlü kapanan piyasada hafta sonu short, zayıf kapananda long taşınmaz (**Schwartz:** düşen Cuma'yı genelde düşen Pazartesi izler) |
| BK-150 | T | **Dennis / Jones: zaman stopu:** 1–2 hafta sonra zararda ya da beklenen hareket gelmiyorsa, stop vurulmasa da çık |
| BK-151 | F | **Dennis:** formasyon yön söyler; "bu fiyatı geçemez" diye tavan koymak için kullanılmaz |
| BK-152 | T | **Jones: oynaklık kırılımı:** dar aralık aniden genişlerse o yönde girilir |
| BK-153 | T | **Jones:** ölçülü hareket: aralık kırılınca hedef **aralık yüksekliği** kadar (PA-35, BK-42 ile aynı) |
| BK-154 | T | **Jones:** büyük pozisyon yeni tepe/dipte yarı yarıya kapatılır; stopların biriktiği yerde dönüş olabilir |
| BK-155 | D | **Jones:** günlük kayıp %1–2'de her şey kapatılır; giriş fiyatı önceki gün kapanışı sayılır |
| BK-156 | D | **Bielfeldt:** tek yönteme bağlanma: sistem sinyali ile kendi görüşü yarı yarıya; düşük olasılıklı el küçük kayıpla bırakılır |
| BK-157 | T | **Seykota:** önem sırası: uzun vadeli trend → mevcut formasyon → giriş noktası. Alış emri fiyatın **üstünde** (momentum yönünde), dip seçilmez |
| BK-158 | F | **Seykota:** karar günde bir kez, **kapanış** verisiyle; sürekli ekran fazla işlem yaptırır |
| BK-159 | T | **Hite: üç ışık:** oynaklık normal → bütün sinyaller; yüksek → yeni işlem yok; aşırı → açık işlemler de kapatılır (10–100 günlük pencereler) |
| BK-160 | T | **Hite:** stop sonrası fiyat **yeni tepe** yaparsa yeniden girilir. Tarihî yeni yüksek "bir şey değişti" demektir |
| BK-161 | F | **Hite:** aşırı alım/satım göstergelerinin işe yaradığı testle gösterilemedi; en iyi değil **sağlam** (ayara duyarsız) parametre seçilir |
| BK-162 | F | **Steinhardt (karşıt görüş):** grafik ve stop kullanmaz; yalnız piyasadan farklı bir görüşü varken pozisyonda kalır, beklenen haber gelince çıkar |
| BK-163 | T | **O'Neil:** geniş tabandan **yeni yükseğe** çıkışta alınır, dipten değil; tabandan %10'dan fazla uzaklaşmışsa alınmaz |
| BK-164 | T | **O'Neil / Ryan:** kırılım hacmi ortalamanın en az **%50** üstünde (Ryan: iki katı); tabanda hacim **azalmış** olmalı (BK-25 ile aynı) |
| BK-165 | D | **O'Neil / Ryan:** en fazla **%7** zarar; isabet %50–66 yeter. 5–6 ardışık kayıpta nakde dön |
| BK-166 | T | **O'Neil:** endeks tepesi: düşük hacimli yeni yüksek **ya da** birkaç gün hacim artarken fiyatın ilerlememesi; liderlerin önce kırılması |
| BK-167 | T | **O'Neil:** short "pahalı" diye açılmaz; 3./4. tabandan çıkış başarısız olup tabanın altına hacimle inince, tabana **ilk geri çekilişte** |
| BK-168 | T | **Ryan:** kırılan aralığın **içine geri dönen** fiyatta en az yarısı satılır; genelde aralığın dibine kadar gider |
| BK-169 | T | **Ryan:** göreli güç en az %80, tercihen %90+; **düşmeye başlarsa** vazgeçilir (Marcus karşıt: kendi işine yaramadığını söylüyor) |
| BK-170 | T | **Ryan:** hedef yok; fiyat yeni taban kurup **aşağı kırınca** çıkılır. Kazananlar 6–12 ay, kaybedenler iki haftadan az tutulur |
| BK-171 | T | **Schwartz:** işlemden önce fiyat hareketli ortalamanın hangi tarafında? Ters tarafa işlem yok |
| BK-172 | T | **Schwartz:** piyasa yeni dip yaparken kendi dibinin üstünde kalan varlık güçlüdür (göreli güç) |
| BK-173 | T | **Schwartz:** tepenin süresi fiyat tepesinden değil, ondan **önceki osilatör tepesinden** ölçülür; iniş ve çıkış süreleri benzer |
| BK-174 | F | **Schwartz:** birlikte gitmesi gereken iki araç ortalamalarına göre ayrışıyorsa işlem yok |
| BK-175 | F | **Schwartz:** korkulan haberden sonra açılış beklendiği kadar kötü değilse pozisyon korunur; yönü destekleyen güç vardır |
| BK-176 | T | **Rogers:** histeri (boşluklu, dikey hareket) aranır; katalizör yoksa ucuz varlık yıllarca ucuz kalır. **Uyarı:** tek başına "tepe satmak" kitapta da tehlikeli deniyor |
| BK-177 | T | **Weinstein:** temposunu kaybeden harekette ters yön; dip ve tepe değil, hareketin en hızlı **orta kısmı** alınır. (%99 isabet iddiası doğrulanamadı) |
| BK-178 | F | **Weinstein:** hiçbir yöntem her zaman çalışmaz; önce hangi rejimde olunduğuna bakılır |
| BK-179 | D | **Gelber:** tek kural: **kaybeden pozisyon büyütülmez**. Yıl başında küçük, kazandıkça büyük; kayıpta kalan pozisyonlar da kapatılır |
| BK-180 | T | **Baldwin:** bakılan seviyeler haftanın en yükseği/düşüğü, %50 düzeltme ve sıkışma alanı; haftalık ucun kırılıp **geri dönmesi** tuzaktır (SFP, MB-20) |
| BK-181 | F | **Baldwin (karşıt görüş):** zararda en kötü anda değil, gelen tepkide çıkılır. Yalnız disiplinli çok kısa vade için; bizde stop esas |
| BK-182 | D | **Saliba:** pozisyona girmeden en kötü kayıp bilinir; kötü pozisyon hemen kapatılır ya da nötrlenir, büyük emir **parça parça** verilir |
| BK-183 | T | **Saliba:** ani oynaklık + toparlanamayan gün + zayıf Cuma, Pazartesi açılışında da sürdü (Ekim 1987; tek olay). BK-149 ile birlikte ölçülür |
| BK-184 | D | **Tharp:** kaybı kısa kes, kârı bırak kuralının tersi doğal eğilimdir: kazançta kesin küçüğü alır, kayıpta riske gireriz. Gün sonunda ölçü kâr değil **kurala uyuldu mu** |
| BK-185 | F | **Tharp:** sinyal sistemi üç adımla uygulanır: gör, tanı, uygula. Araya "ters gidebilir" adımı girince sinyal alınmaz → onay-algoda karar koddadır, elle müdahale yok |
| BK-186 | T | **Schwager:** doğru tahminde baz pozisyon **tutulur**, düzeltmede büyütülür. Tamamı kapatılıp geri çekilme beklenirse hareket kaçar |
| BK-187 | D | **Schwager:** kaçan girişi en kötü anda kovalama; günlük inceleme yapılamıyorsa pozisyon taşınmaz |
| BK-188 | T | **Marcus:** uzun süre aşılamayan **resmî ya da alışılmış üst sınır** aşılır ve işlem orada sürerse yeni düzendir: alınır, kâr arttıkça azalan miktarla eklenir |
| BK-189 | T | **Sözlük:** dönüş günü: yeni yüksek yapıp önceki bir/birkaç günün **kapanışının altında** kapanmak (dipte tersi); hacim ve boşlukla güçlenir |

**Bölüm 3–5 ve 8–10'daki kitapların tamamı okunmadı** (aşağıdaki sayfalar); başarı öyküleri **hayatta kalma yanlılığı** taşır: aynı kuralı uygulayıp batanlar kitapta yok.

## 12. Okuma durumu
| Kitap | Sayfa | Durum |
|---|---|---|
| VWAP Stratejisi | 44 | ✅ tamamı |
| Altın Kurallar | 53 | ✅ tamamı |
| Akıllı Borsacı | 67 | ◐ 12–15, 18, 21–32, 37–39. sayfalar (teknik kısım); bilanço, tanıtım ve sözlük atlandı |
| Trading Psikolojisi | 129 | ◐ 4. bölüm (91–129); 1.–3. bölüm kişisel gelişim, atlandı |
| Karar Verme | 22 | ◐ 2–22. sayfalar, 1. sayfanın üst yarısı |
| Alpha Trader | 488 | ✅ tamamı (5–488; 1–4 kapak ve tanıtım) |
| Bir Borsa Spekülatörünün Anıları | 270 | ✅ tamamı (8–270; 1–7 kapak ve künye) |
| High Performance Trading | 312 | ◐ strateji 15, 26'dan sayfalar + içindekiler |
| Market Mind Games | 257 | ◐ 11. ve 13. bölümden sayfalar + içindekiler |
| Piyasaları Okumak | 270 | ◐ teknik analiz bölümü (184–205) ve makro varsayımlar; banka/faiz bölümleri atlandı |
| Borsa Sihirbazları | 524 | ✅ tamamı (9–524; 1–8 kapak ve içindekiler) |
| Temel analiz / portföy | | Akıllı Yatırımcı, Borsada Tek Başına, Duygusuz Yatırımcı, Değerleme, Finans Teorileri: 4.4 değil, 4.1–4.3 için |
| Alınmayacak | | Tarih, ekonomi-politik, kişisel gelişim (işlem kuralı yok) |
