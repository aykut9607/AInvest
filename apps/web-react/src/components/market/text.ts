// Turkish labels and number formats of the 4.4 (market) screens. Ported from Aykut's src/portfolio/text.ts.
import type { MarketKind } from "../../types/market";

const number = (digits: number) => new Intl.NumberFormat("tr-TR", { minimumFractionDigits: digits, maximumFractionDigits: digits });
const two = number(2);

export const usd = (v: number, digits = 2) => `${number(digits).format(v)} $`;
export const signedUsd = (v: number) => `${v < 0 ? "−" : "+"}${two.format(Math.abs(v))} $`;
export const percent = (v: number, digits = 0) => `%${number(digits).format(v)}`;
export const signed = (v: number, digits = 2) => `${v < 0 ? "−" : "+"}${number(digits).format(Math.abs(v))}`;
export const price = (v: number) => two.format(v);
export const plain = (v: number, digits = 1) => number(digits).format(v);

// a time without a zone is UTC
export const date = (iso: string) =>
  new Date(/[zZ]|[+-]\d\d:?\d\d$/.test(iso) ? iso : `${iso}Z`).toLocaleString("tr-TR", {
    day: "numeric",
    month: "long",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
export const day = (seconds: number) =>
  new Date(seconds * 1000).toLocaleDateString("tr-TR", { day: "2-digit", month: "2-digit", year: "numeric" });

export const KINDS: MarketKind[] = ["SCALP", "SCALP_SWING", "SWING"];
export const KIND: Record<MarketKind, string> = { SCALP: "Scalp", SCALP_SWING: "Scalp · swing ihtimalli", SWING: "Swing" };
export const ASSET: Record<string, string> = { BTC: "Bitcoin", GOLD: "Altın", SPX: "S&P 500", ALL: "Üçü tek kasada" };
export const DIRECTION: Record<string, string> = { LONG: "Uzun (long)", SHORT: "Kısa (short)" };

export const assetName = (code: string) => ASSET[code] ?? code;
export const kindName = (code: string) => KIND[code as MarketKind] ?? code;

// a profit zone or exit reason code as text ("HALF_AT_SCALP_TP", "TREND_5.618", "STOP", ...)
export function zone(kind: string): string {
  if (kind.startsWith("HALF_AT_")) return `Yarı kâr (${zone(kind.slice(8))})`;
  const known: Record<string, string> = {
    HALF: "Yarı kâr (+%50)",
    SCALP_TP: "Scalp TP",
    MARKET_SELL: "Market sell",
    STOP: "Stop",
    ENTRY_STOP: "Girişteki stop",
    ENTRY: "Giriş",
  };
  return known[kind] ?? kind.replace("TREND_", "Trend ").replace(".", ",");
}

// "Category|rule|variant" -> "rule (variant)"
export function rule(tag: string): string {
  const [, name = "", variant = ""] = tag.split("|");
  return variant ? `${name} (${variant})` : name || tag;
}

export const FRAMES = ["15m", "30m", "45m", "1h", "2h", "4h", "6h", "12h", "1d", "3d", "1w", "1M"];

export const TEXT = {
  description: "Kural tabanlı onay motorunun sanal işlemleri: hangi onaylarla açıldı, nerede kâr aldı, kasa ne oldu.",
  loading: "Piyasa verisi yükleniyor…",
  loadError: "Piyasa verisi yüklenemedi",
  refresh: "Yenile",
  noPlanTitle: "Henüz plan yok",
  noPlanText: "Motor bir uyumsuzlukta yeterli puanı bulunca açtığı ilk sanal işlem burada görünecek.",
  noOpenText: "Şu an açık sanal işlem yok. Motor her 15 dakikada bir bakıyor.",
  noMissedTitle: "Kaçırılan işlem yok",
  noMissedText: "Motor kapalıyken uygun bir durum oluşursa açıldığında buraya yazılır.",
  noStatsTitle: "Henüz kapanan işlem yok",
  noStatsText: "İlk işlem kapanınca başarı oranı, çıkış türleri ve hangi onayın nasıl gittiği burada görünür.",
  noBacktestTitle: "Geçmiş test yok",
  noBacktestText: "Portfolio Service'te kayıtlı bir geçmiş yıl testi bulunamadı.",
};
