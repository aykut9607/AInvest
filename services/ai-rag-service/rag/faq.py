"""Frequently asked questions: the knowledge the assistant may quote about the platform itself.

Written from the scoring rules (FinancialIqCommandManager.cs, ScoringRules.cs, CLAUDE.md 5.4 and 8.4), so the answers
describe what the code really does. This is the document set the RAG step (pgvector + HNSW, Faz 3) will index; until
then rag/retriever.py finds entries by keyword overlap.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class FaqEntry:
    id: str
    question: str
    answer: str
    # extra words people use for this topic (matched by stem, see rag/retriever.py)
    keywords: tuple[str, ...] = ()


FAQ: tuple[FaqEntry, ...] = (
    FaqEntry(
        "what-is-iq", "Finansal IQ nedir?",
        "Finansal IQ, finansal durumunu ve davranışını 0 ile 100 arasında özetleyen bir skordur. Bilgi ya da zekâ "
        "düzeyini ölçmez. Gelir, gider, taksit, toplam borç, nakit, yatırım ve sabırsızlık bilgilerinden sabit "
        "kurallarla hesaplanır; yapay zekâ skoru hesaplamaz, yalnızca açıklar.",
        ("iq", "skor", "puan", "ne", "anlam", "ölç"),
    ),
    FaqEntry(
        "how-calculated", "Finansal IQ nasıl hesaplanıyor?",
        "Skor beş faktörün toplamıdır: nakit rezervi en fazla 25 puan, borç/gelir oranı en fazla 25 puan, tasarruf "
        "oranı en fazla 25 puan, gider/gelir oranı en fazla 15 puan ve sabır en fazla 10 puan. Nakit rezervi 6 aylık "
        "gideri karşılıyorsa tam puan alır; nakit rezervine yatırımlarının yarısı da sayılır. Borç faktörü hem "
        "taksitin gelire oranına hem de net borcun yıllık gelire oranına bakar ve kötü olanı alır.",
        ("hesap", "faktör", "formül", "ağırlık", "nasıl", "puan"),
    ),
    FaqEntry(
        "segments", "Segmentler ne anlama geliyor?",
        "Skor 0 ile 40 arasındaysa DÜŞÜK, 41 ile 70 arasındaysa ORTA, 71 ile 100 arasındaysa YÜKSEK segmenttesin. "
        "DÜŞÜK öncelikli iyileştirme gerektiğini, ORTA dengeli ama güçlendirilecek alanlar olduğunu, YÜKSEK ise "
        "finansal durumunun güçlü olduğunu gösterir.",
        ("segment", "düşük", "orta", "yüksek", "seviye", "grup"),
    ),
    FaqEntry(
        "special-rules", "Skorum neden doğrudan 100 ya da 0 oldu?",
        "Üç özel kural vardır. Aylık gelir 1.000.000 TL veya üstündeyse ve net borç bir yıllık geliri aşmıyorsa skor "
        "100 olur. Net servet (nakit ve yatırımlardan borç çıkınca kalan) 10.000.000 TL veya üstündeyse skor 100 olur. "
        "Gelir 1.000.000 TL'nin altındayken net borç 100.000.000 TL veya üstündeyse skor 0 olur.",
        ("kural", "100", "sıfır", "doğrudan", "servet", "aşırı", "neden"),
    ),
    FaqEntry(
        "improve", "Skorumu nasıl yükseltebilirim?",
        "En hızlı etki genellikle zayıf faktörden gelir. Acil durum fonunu en az 3, ideal olarak 6 aylık gidere "
        "çıkarmak, taksitlerin gelirin %36'sının altında kalmasını sağlamak, gelirinin en az %20'sini "
        "biriktirmek ve giderleri gelirin %80'inin altında tutmak skoru yükseltir. Acele etmeden "
        "bekleyebilmek de sabır faktörünü artırır.",
        ("yüksel", "artır", "iyileş", "geliştir", "nasıl", "öneri", "tavsiye"),
    ),
    FaqEntry(
        "privacy", "Verilerim nereye gidiyor?",
        "Finansal verilerin AInvest'in kendi sunucularında kalır. Açıklamaları yazan dil modeli de bizim sunucumuzda "
        "çalışır; verilerin başka bir yapay zekâ şirketine gönderilmez. Asistan yalnızca senin oturumunla, yalnızca "
        "senin verilerini okuyabilir.",
        ("veri", "gizli", "güven", "nereye", "paylaş", "sunucu", "kişisel"),
    ),
    FaqEntry(
        "no-risk-question", "Neden risk tercihimi sormuyorsunuz?",
        "Risk tercihi artık skoru etkilemiyor. Önce Finansal IQ hesaplanır; portföy oluştururken risk seviyeni sen "
        "seçersin ama en fazla skorunun izin verdiği seviyeye kadar: DÜŞÜK segment en fazla düşük, ORTA segment en "
        "fazla orta, YÜKSEK segment yüksek risk seçebilir.",
        ("risk", "tercih", "sorm", "seviye", "agresif"),
    ),
    FaqEntry(
        "investable-share", "Ne kadar yatırım yapabilirim?",
        "Yatırılabilir pay Finansal IQ'ndan hesaplanır: skorundan 30 çıkarılır ve sonuç %0 ile %70 arasında tutulur; "
        "bu oran aylık artan paraya ve 3 aylık acil durum fonunun üstündeki nakde uygulanır. Acil durum fonun 3 "
        "ayın altındaysa önce fonu tamamlaman gerekir.",
        ("yatırım", "ne kadar", "pay", "tutar", "yatır", "portföy"),
    ),
    FaqEntry(
        "not-advice", "Bu uygulama yatırım tavsiyesi veriyor mu?",
        "Hayır. AInvest'in açıklamaları ve önerileri eğitim amaçlıdır, yatırım tavsiyesi değildir. Belirli bir hisse, "
        "kripto para ya da al-sat önerisi verilmez.",
        ("tavsiye", "hisse", "kripto", "al", "sat", "öneri", "yasal"),
    ),
    FaqEntry(
        "emergency-fund", "Acil durum fonu nedir?",
        "Acil durum fonu, gelirin kesilse bile giderlerini karşılayacak birikimdir. AInvest nakit paranı ve "
        "yatırımlarının yarısını bu fona sayar. En az 3 aylık gider önerilir, 6 aylık gider tam puan alır.",
        ("acil", "fon", "rezerv", "birikim", "nakit"),
    ),
    FaqEntry(
        "impatience", "Sabırsızlık skoru neden etkiliyor?",
        "Bugün küçük bir kazancı yarın daha büyük bir kazanca tercih etme eğilimi uzun vadeli birikimi zorlaştırır. "
        "Bu yüzden sabırsızlık 1 ile 5 arasında seçilir: 1 en sabırlı (10 puan), 5 en sabırsız (0 puan) demektir.",
        ("sabır", "sabırsız", "acele", "bekle"),
    ),
)
