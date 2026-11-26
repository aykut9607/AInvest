// Turkish wording for the 4.4 codes (types/signals.ts, a draft). Kept here until the 4.4 module publishes its schema.
import { formatNumber } from "../../lib/format";
import type { Direction, LtfSignal, MarketBias, ModelKind, PriceZone, SignalAsset, SignalPlan, Timeframe } from "../../types/signals";

// display order of the cards: BTC, gold, S&P 500
export const SIGNAL_ASSET_ORDER: SignalAsset[] = ["BTC", "GOLD", "SPX"];

export const SIGNAL_ASSET_SHORT: Record<SignalAsset, string> = { BTC: "Bitcoin", GOLD: "Altın", SPX: "S&P 500" };

export const BIAS_LABELS: Record<MarketBias, string> = {
  BULLISH: "Yükseliş beklentisi",
  BEARISH: "Düşüş beklentisi",
  NEUTRAL: "Yön belirsiz",
};

export const DIRECTION_LABELS: Record<Direction, string> = { LONG: "Uzun (long)", SHORT: "Kısa (short)" };

export const TIMEFRAME_LABELS: Record<Timeframe, string> = {
  "1W": "Haftalık",
  "1D": "Günlük",
  "4h": "4 saatlik",
  "1h": "1 saatlik",
  "45m": "45 dakikalık",
  "30m": "30 dakikalık",
  "15m": "15 dakikalık",
};

export const LTF_SIGNAL_LABELS: Record<LtfSignal, string> = {
  SFP: "SFP (likidite avı)",
  RSI_DIVERGENCE: "RSI uyumsuzluğu",
  CVD_DIVERGENCE: "CVD uyumsuzluğu",
  CLOSE_CONFIRMATION: "Kapanış onayı",
};

export const MODEL_KIND_LABELS: Record<ModelKind, string> = {
  ELLIOTT_IMPULSE: "Elliott itki",
  ELLIOTT_CORRECTION: "Elliott düzeltme",
  HARMONIC: "Harmonik formasyon",
  FIBONACCI: "Fibonacci",
  RANGE: "Fiyat aralığı",
};

// a code this app does not know yet is shown as it came
export function labelOf<K extends string>(table: Record<K, string>, code: string): string {
  return (table as Record<string, string>)[code] ?? code;
}

export function timeframesText(timeframes: Timeframe[]): string {
  return timeframes.map((t) => labelOf(TIMEFRAME_LABELS, t)).join(", ");
}

// >= threshold: the rule-based confirmation is strong enough for a conditional plan
export function isPlanActive(plan: Pick<SignalPlan, "confirmation">): boolean {
  const { total, threshold } = plan.confirmation;
  return Number.isFinite(total) && Number.isFinite(threshold) && total >= threshold;
}

export function sortPlans(plans: SignalPlan[]): SignalPlan[] {
  const rank = (asset: string) => {
    const index = SIGNAL_ASSET_ORDER.indexOf(asset as SignalAsset);
    return index === -1 ? SIGNAL_ASSET_ORDER.length : index;
  };
  return [...plans].sort((a, b) => rank(a.asset) - rank(b.asset));
}

// "4.280–4.320 USD"
export function zoneText(zone: PriceZone, currency: string): string {
  return `${formatNumber(zone.low, 2)}–${formatNumber(zone.high, 2)} ${currency}`;
}
