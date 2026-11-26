// Turkish wording for every code the services send. Sources (keep in sync):
// factors, warnings, segments, rules: services/ai-rag-service/core/domain.py; fallback reasons: evaluation/playground.html
// (REASONS); portfolio assets, options, reasons: services/ai-rag-service/services/portfolio.py.
import type {
  AppliedRule,
  FactorBreakdown,
  FallbackReason,
  InstitutionStyle,
  PortfolioOption,
  RiskLevel,
  Segment,
  Severity,
} from "../types/api";

// ---- Financial IQ factors ----------------------------------------------------------------------------------------

export const FACTOR_LABELS: Record<string, string> = {
  CashReserveMonths: "Nakit rezervi",
  DebtToIncomeRatio: "Borç/gelir oranı",
  // scoring v3 splits the debt factor in two and drops the expense ratio
  InstallmentToIncome: "Taksit/gelir oranı",
  NetDebtToIncome: "Net borç/gelir oranı",
  SavingsRate: "Tasarruf oranı",
  ExpenseRatio: "Gider/gelir oranı",
  Impatience: "Sabır",
};

// scoring v2 maximums (25/25/25/15/10 = 100); used when the breakdown carries no factorMaximums
export const V2_FACTOR_MAXIMUMS: Record<string, number> = {
  CashReserveMonths: 25,
  DebtToIncomeRatio: 25,
  SavingsRate: 25,
  ExpenseRatio: 15,
  Impatience: 10,
};

// display order for known keys (v2 and v3); unknown keys follow in the order the service sent them
const FACTOR_ORDER = Object.keys(FACTOR_LABELS);

export interface FactorRow {
  key: string;
  // Turkish label, or the raw key for a factor this app does not know yet
  label: string;
  points: number;
  // null when neither the breakdown nor the v2 table knows the maximum
  max: number | null;
}

// Data-driven factor list: maximums from breakdown.factorMaximums when present (a later scoring version), else the
// v2 table for a v2 breakdown; labels from FACTOR_LABELS, else the raw key. Works for any factor keys the IQ service sends.
export function factorRows(breakdown: FactorBreakdown | null | undefined): FactorRow[] {
  if (!breakdown?.factors) return [];
  // the v2 table only applies to v2 (or an unversioned breakdown); another version must bring factorMaximums
  const fallback: Record<string, number> = !breakdown.version || breakdown.version === "v2" ? V2_FACTOR_MAXIMUMS : {};
  const keys = Object.keys(breakdown.factors).sort((a, b) => {
    const ia = FACTOR_ORDER.indexOf(a);
    const ib = FACTOR_ORDER.indexOf(b);
    return (ia === -1 ? Number.MAX_SAFE_INTEGER : ia) - (ib === -1 ? Number.MAX_SAFE_INTEGER : ib);
  });
  return keys.map((key) => {
    const max = breakdown.factorMaximums?.[key] ?? fallback[key];
    return {
      key,
      label: FACTOR_LABELS[key] ?? key,
      points: Number(breakdown.factors[key]) || 0,
      max: typeof max === "number" && max > 0 ? max : null,
    };
  });
}

// ---- IQ warnings and rules -----------------------------------------------------------------------------------------

export const WARNING_LABELS: Record<string, string> = {
  "Low cash reserve": "Nakit rezervi düşük",
  "High debt burden": "Taksit yükü yüksek",
  "High total debt": "Toplam borç yüksek",
  "Negative savings rate": "Tasarruf oranı negatif",
  "Overspending relative to income": "Giderler gelire göre çok yüksek",
  "High impatience": "Sabırsızlık yüksek",
  "Extreme total debt": "Toplam borç aşırı yüksek",
  // scoring v3
  "Elevated debt burden": "Taksit yükü dikkat gerektiren düzeyde",
  "Elevated total debt": "Toplam borç dikkat gerektiren düzeyde",
  "Low savings rate": "Tasarruf oranı düşük",
  "High expense ratio": "Gider oranı yüksek",
  "Installment below interest": "Taksit, borcun tahmini faizini karşılamıyor",
  "Expenses look too low": "Bildirilen gider gerçekçi olamayacak kadar düşük",
  "Installment without debt": "Borç yokken taksit bildirilmiş",
  "Installment exceeds total debt": "Taksit toplam borçtan büyük",
};

export function warningLabel(warning: string): string {
  return WARNING_LABELS[warning] ?? warning;
}

export interface AppliedRuleLabel {
  title: string;
  // what the rule means (domain.py RULES)
  description: string;
  // the score a v2 rule sets; null for a v3 label, where the score is still the sum of the factors
  score: number | null;
}

export const APPLIED_RULE_LABELS: Record<AppliedRule, AppliedRuleLabel> = {
  VERY_HIGH_INCOME: {
    title: "Çok yüksek gelir kuralı",
    description:
      "Aylık gelir çok yüksek ve net borç bir yıllık geliri aşmıyor; bu gelirle diğer eksikler kısa sürede kapanır.",
    score: 100,
  },
  VERY_HIGH_WEALTH: {
    title: "Çok yüksek servet kuralı",
    description:
      "Net servet (nakit ve yatırımlardan borç çıkınca kalan) çok yüksek; bu servet giderleri uzun yıllar karşılar.",
    score: 100,
  },
  EXTREME_DEBT: {
    title: "Aşırı borç kuralı",
    description: "Net borç aşırı yüksek; bu borç düzeyinde diğer göstergeler skoru kurtaramaz.",
    score: 0,
  },
  SOLVENCY_CAP: {
    title: "Ödeme gücü tavanı",
    description:
      "Net borç yıllık gelire göre çok yüksek; bu borç düzeyinde bütün faktörlerin puanı ödeme gücü tavanıyla aşağı çekildi.",
    score: null,
  },
  WEALTH_RUNWAY: {
    title: "Servet pisti",
    description:
      "Likit servet (nakit ve yatırımların yarısından borç çıkınca kalan) giderleri en az beş yıl karşılıyor; bu yüzden tasarruf ve taksit puanları servete göre yukarı çekildi.",
    score: null,
  },
};

// v3 labels describe how the factor points were shaped; only the v2 rules replace the factors
export function ruleSetsScore(rule: AppliedRule): boolean {
  return APPLIED_RULE_LABELS[rule].score !== null;
}

// thresholds of the three rules (ScoringRules.cs), for an "how was this score set" note
export const APPLIED_RULE_THRESHOLDS: Record<AppliedRule, string> = {
  VERY_HIGH_INCOME: "Aylık gelir en az 1.000.000 ve net borç en fazla 1 yıllık gelir olduğunda skor 100 olur.",
  VERY_HIGH_WEALTH: "Net servet (nakit + yatırım − borç) en az 10.000.000 olduğunda skor 100 olur.",
  EXTREME_DEBT: "Net borç (borç − nakit − yatırım) en az 100.000.000 olduğunda skor 0 olur.",
  SOLVENCY_CAP:
    "Net borç 5 yıllık gelirin üstüne çıkınca her faktörün puanı kademeli olarak azalır; 15 yıllık gelirde sıfıra iner.",
  WEALTH_RUNWAY:
    "Likit servet giderlerin kaç yılını karşılıyorsa puanlar o kadar yukarı çekilir; 25 yıl (yüzde 4 kuralı) ve üstü tam etki verir. Etiket beş yıldan itibaren gösterilir.",
};

// ---- Segments ------------------------------------------------------------------------------------------------------

export const SEGMENT_LABELS: Record<Segment, string> = { LOW: "DÜŞÜK", MEDIUM: "ORTA", HIGH: "YÜKSEK" };

export const SEGMENT_MEANINGS: Record<Segment, string> = {
  LOW: "Finansal durum zayıf, öncelikli iyileştirme gerekiyor.",
  MEDIUM: "Finansal durum dengeli, bazı alanlar güçlendirilmeli.",
  HIGH: "Finansal durum güçlü.",
};

export const SEGMENT_RANGES: Record<Segment, string> = { LOW: "0–40", MEDIUM: "41–70", HIGH: "71–100" };

// lower-case level words (risk level, "düşük segment"), domain.py LEVEL_TR
export const LEVEL_LABELS: Record<RiskLevel, string> = { LOW: "düşük", MEDIUM: "orta", HIGH: "yüksek" };

export function capitalizeTr(text: string): string {
  return text.charAt(0).toLocaleUpperCase("tr-TR") + text.slice(1);
}

// ---- AI responses --------------------------------------------------------------------------------------------------

export const FALLBACK_REASON_LABELS: Record<FallbackReason, string> = {
  NO_BREAKDOWN: "Skor dökümü yok",
  NO_DATA: "Veri yok",
  DATA_UNAVAILABLE: "Veriye ulaşılamadı",
  LLM_UNAVAILABLE: "Model çalışmadı",
  EMPTY_OUTPUT: "Model boş cevap verdi",
  WRONG_LANGUAGE: "Model başka alfabe kullandı",
  UNVERIFIED_NUMBERS: "Model veride olmayan sayı yazdı",
  BLOCKED_INPUT: "Enjeksiyon filtresi soruyu engelledi",
  UNSUPPORTED: "Desteklenmeyen konu: sabit cevap",
};

export function fallbackReasonLabel(reason: string | null | undefined): string {
  if (!reason) return "";
  return FALLBACK_REASON_LABELS[reason as FallbackReason] ?? reason;
}

export const SEVERITY_LABELS: Record<Severity, string> = { CRITICAL: "KRİTİK", WARNING: "UYARI", INFO: "BİLGİ" };

// ---- Impatience (profile form) -----------------------------------------------------------------------------------

export const IMPATIENCE_LEVELS = [1, 2, 3, 4, 5] as const;

export const IMPATIENCE_HINTS: Record<number, string> = {
  1: "Yıllarca bekleyebilirim, acelem yok",
  2: "Bir-iki yıl",
  3: "Birkaç ay",
  4: "Birkaç hafta",
  5: "Sonucu hemen görmek isterim",
};

// ---- Portfolio -----------------------------------------------------------------------------------------------------

export const ASSET_LABELS: Record<string, string> = {
  GOLD: "Altın",
  SILVER: "Gümüş",
  TRY_DEPOSIT: "TL mevduat",
  TRY_BOND: "TL tahvil",
  BOND: "Tahvil",
  SPX: "S&P 500 endeksi",
  NDQ: "Nasdaq endeksi",
  BIST: "BIST 100 endeksi",
  BIST100: "BIST 100 endeksi",
  EUR: "Euro",
  USD: "Dolar",
  NVDA: "Nvidia hissesi",
  BTC: "Bitcoin",
  ETH: "Ethereum",
  OIL: "Petrol",
  AI_STOCKS: "Yapay zekâ şirketleri hisseleri",
  // fund categories of the institutions' published allocations (4.1); the service also sends its own label
  TRY_EQUITY: "TL hisse",
  FOREIGN_EQUITY: "Yabancı hisse",
  CONSERVATIVE_FUND: "Temkinli değişken fon",
  EUROBOND: "Eurobond",
  EQUITY: "Hisse",
  CASH_REPO: "Nakit ve ters repo",
  OTHER_FUNDS: "Diğer fon payları",
};

export function assetLabel(code: string): string {
  return ASSET_LABELS[code] ?? code;
}

export const PORTFOLIO_OPTION_LABELS: Record<PortfolioOption, string> = {
  INSTITUTION: "Kurum tarzı portföy",
  CUSTOM: "Kendi seçtiğin alana odaklı portföy",
  STANDARD: "Standart dengeli sepet",
  AINVEST: "AInvest önerisi (geçmiş verilerle test edilmiş kural tabanlı öneri)",
};

export const INSTITUTION_STYLE_LABELS: Record<InstitutionStyle, string> = {
  // the code names whose PUBLISHED allocation is used, not a risk style: each institution publishes all three levels
  ZIRAAT: "Aktif yönetilen değişken fon (Ziraat)",
  ISBANK: "Çok varlıklı fon sepeti (İş Bankası)",
  YAPIKREDI: "Mevduat temelli paket (Yapı Kredi)",
};

// sentences for the Portfolio Service's reason codes (same texts as the service's own portfolio pages)
const PORTFOLIO_REASON_LABELS: Record<string, string> = {
  IQ_TILT_TO_SAFE_ASSETS: "Finansal IQ'na göre dağılım daha güvenli varlıklara kaydırıldı.",
  RESERVE_FIRST: "Önce 3 aylık acil durum fonunu tamamla; şimdilik yatırılabilir payın 0.",
  RISK_CAPPED_BY_IQ: "Seçebileceğin risk seviyesi Finansal IQ'nla sınırlandı.",
  NO_MONTHLY_SURPLUS: "Aylık artan paran yok.",
  DEBT_FIRST: "Borcun nakit ve yatırımından fazla; önce borcu düşünmek daha mantıklı olabilir.",
  CEILING_RESERVE: "Risk tavanın düşük: acil durum fonun 3 aylık giderini karşılamıyor.",
  CEILING_NO_SURPLUS: "Risk tavanın düşük: aylık artan paran yok.",
  CEILING_DEBT: "Risk tavanın en çok orta: taksitlerin gelirinin %36'sını ya da net borcun 3 yıllık gelirini aşıyor.",
  CEILING_IMPATIENCE: "Risk tavanın bir kademe düşürüldü: yatırım sabrın düşük (4–5).",
  RISK_CEILING_REACHED: "Riskli varlıkların toplamı, seçtiğin risk seviyesinin sınırında.",
};

const REPLACED = /^EXCLUDED_ASSET_REPLACED:([A-Z0-9_]{1,24})->([A-Z0-9_]{1,24})$/;
const FOCUS = /^FOCUS:([A-Z0-9_]{1,24})$/;
const PUBLISHED = /^PUBLISHED_ALLOCATION:[A-Z0-9_]{1,24}:(\d{4})-(\d{2})$/;

// null for an unknown code. The AI service drops unknown codes from its explanation; the portfolio page lists them
// as the raw code (escaped by React), so a new service code is visible until it gets a Turkish sentence here.
export function portfolioReasonLabel(code: string): string | null {
  const replaced = REPLACED.exec(code);
  if (replaced) return `İstemediğin ${assetLabel(replaced[1])} yerine ${assetLabel(replaced[2])} kondu.`;
  const focus = FOCUS.exec(code);
  if (focus) return `${assetLabel(focus[1])}: seçtiğin varlık.`;
  const published = PUBLISHED.exec(code);
  if (published) return `Kurumun ${published[2]}.${published[1]} döneminde yayımladığı dağılım.`;
  return PORTFOLIO_REASON_LABELS[code] ?? null;
}
