// Every Turkish text and number format of the portfolio pages in one place.
import { ApiError } from "./api";
import type { Kind, Level, Option } from "./types";

const number = (digits: number) => new Intl.NumberFormat("tr-TR", { minimumFractionDigits: digits, maximumFractionDigits: digits });
const whole = number(0);
const two = number(2);

export const tl = (v: number) => `${(Number.isInteger(v) ? whole : two).format(v)} TL`;
export const usd = (v: number, digits = 2) => `${number(digits).format(v)} $`;
export const signedUsd = (v: number) => `${v < 0 ? "−" : "+"}${two.format(Math.abs(v))} $`;
export const percent = (v: number, digits = 0) => `%${number(digits).format(v)}`;
export const signed = (v: number, digits = 2) => `${v < 0 ? "−" : "+"}${number(digits).format(Math.abs(v))}`;
export const price = (v: number) => two.format(v);
export const plain = (v: number, digits = 1) => number(digits).format(v);

// a time without a zone is UTC (the .NET services send it so)
export const date = (iso: string) => new Date(/[zZ]|[+-]\d\d:?\d\d$/.test(iso) ? iso : `${iso}Z`).toLocaleString("tr-TR", { day: "numeric", month: "long", year: "numeric", hour: "2-digit", minute: "2-digit" });
export const month = (period: string) => new Date(`${period}-01T12:00:00`).toLocaleDateString("tr-TR", { month: "long", year: "numeric" });
export const day = (seconds: number) => new Date(seconds * 1000).toLocaleDateString("tr-TR", { day: "2-digit", month: "2-digit", year: "numeric" });

export const LEVEL: Record<Level, string> = { LOW: "Düşük", MEDIUM: "Orta", HIGH: "Yüksek" };
export const SEGMENT: Record<Level, string> = { LOW: "DÜŞÜK · 0–40", MEDIUM: "ORTA · 41–70", HIGH: "YÜKSEK · 71–100" };
export const RISK_TEXT: Record<Level, string> = {
  LOW: "Riskli varlıklar (Bitcoin, Nvidia, S&P 500, BIST 100) en çok %20. Daha az dalgalanma.",
  MEDIUM: "Riskli varlıklar (Bitcoin, Nvidia, S&P 500, BIST 100) en çok %50. Dengeli.",
  HIGH: "Riskli varlıklar (Bitcoin, Nvidia, S&P 500, BIST 100) en çok %80. Dalgalanma yüksek.",
};

export const OPTION: Record<Option, { number: string; title: string; text: string }> = {
  INSTITUTION: { number: "4.1", title: "Yayımlanmış kurum dağılımı", text: "Üç kurumun kendi yayımladığı dağılımlardan biri; kaynağı ve ayıyla." },
  CUSTOM: { number: "4.2", title: "Kendi seçtiğin alana odaklı portföy", text: "Seçtiğin varlıklar en büyük payı alır, kalanı standart sepetten gelir." },
  STANDARD: { number: "4.3", title: "Standart dengeli sepet", text: "Güvenli kısım eşit, riskli kısım oynaklığa göre; istemediğini çıkar." },
  AINVEST: { number: "4.4", title: "AInvest önerisi", text: "Kural tabanlı onay motoru. Kazandırdığına dair kanıt yok; şimdilik yalnız sanal işlemler." },
};

// codes the service may send later and this screen does not know are not shown
export function reason(code: string, label: (asset: string) => string): string | null {
  const [name, a = "", b = ""] = code.split(":");
  switch (name) {
    case "RESERVE_FIRST":
      return "Önce 3 aylık acil durum fonunu tamamla; şimdilik yatırılabilir payın 0.";
    case "NO_MONTHLY_SURPLUS":
      return "Aylık artan paran yok.";
    case "DEBT_FIRST":
      return "Borcun nakit ve yatırımından fazla; önce borcu düşünmek daha mantıklı olabilir.";
    case "CEILING_RESERVE":
      return "Risk tavanın düşük: acil durum fonun 3 aylık giderini karşılamıyor.";
    case "CEILING_NO_SURPLUS":
      return "Risk tavanın düşük: aylık artan paran yok.";
    case "CEILING_DEBT":
      return "Risk tavanın en çok orta: taksitlerin gelirinin %36'sını ya da net borcun 3 yıllık gelirini aşıyor.";
    case "CEILING_IMPATIENCE":
      return "Risk tavanın bir kademe düşürüldü: yatırım sabrın düşük (4–5).";
    case "RISK_CEILING_REACHED":
      return "Riskli varlıkların toplamı, seçtiğin risk seviyesinin sınırında.";
    case "FOCUS":
      return `${label(a)}: seçtiğin varlık.`;
    case "EXCLUDED_ASSET_REPLACED": {
      const [from = "", to = ""] = a.split("->");
      return `${label(from)} istemediğin için payı ${label(to)} varlığına geçti.`;
    }
    case "PUBLISHED_ALLOCATION":
      return `Kurumun ${month(b)} döneminde yayımladığı dağılım.`;
    default:
      return null;
  }
}

export function problem(error: unknown): string {
  if (!(error instanceof ApiError)) return "Beklenmeyen bir hata oldu. Yeniden dene.";
  switch (error.status) {
    case 0:
    case 401:
    case 429:
      return error.message;
    case 400:
      return `Bu seçim yapılamıyor.${error.message ? ` (${error.message})` : ""}`;
    case 403:
      return "Bu veriye erişimin yok.";
    case 404:
      return "Kayıt bulunamadı.";
    case 409:
      return "Bu seçenek hazırlanıyor.";
    case 502:
    case 503:
    case 504:
      return "Servise ulaşılamıyor. Birazdan yeniden dene.";
    default:
      return error.message || `Beklenmeyen cevap (${error.status}).`;
  }
}

// ---------- 4.4

export const KIND: Record<Kind, string> = { SCALP: "Scalp", SCALP_SWING: "Scalp · swing ihtimalli", SWING: "Swing" };
export const ASSET: Record<string, string> = { BTC: "Bitcoin", GOLD: "Altın", SPX: "S&P 500", ALL: "Üçü tek kasada" };

export function zone(kind: string): string {
  if (kind.startsWith("HALF_AT_")) return `Yarı kâr (${zone(kind.slice(8))})`;
  const known: Record<string, string> = { HALF: "Yarı kâr (+%50)", SCALP_TP: "Scalp TP", MARKET_SELL: "Market sell", STOP: "Stop", ENTRY_STOP: "Girişteki stop" };
  return known[kind] ?? kind.replace("TREND_", "Trend ").replace(".", ",");
}

export function rule(tag: string): string {
  const [, name = "", variant = ""] = tag.split("|");
  return variant ? `${name} (${variant})` : name;
}

export const FRAMES = ["15m", "30m", "45m", "1h", "2h", "4h", "6h", "12h", "1d", "3d", "1w", "1M"];
