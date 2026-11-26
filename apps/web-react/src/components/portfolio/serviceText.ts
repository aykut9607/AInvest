// Turkish texts for what the Portfolio Service's /options adds to the page (risk ceiling, investable steps, sources).
// Reason sentences themselves live in lib/labels.ts (portfolioReasonLabel); these are only the glue around them.
import { LEVEL_LABELS } from "../../lib/labels";
import type { RiskLevel, Segment } from "../../types/api";
import type { PortfolioOptions } from "../../types/portfolioService";
import { reasonText } from "./proposal";
import { maxRiskForSegment } from "./risk";

const MONTHS = ["Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran", "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"];

// "2026-10" -> "Ekim 2026"; anything else is shown as it came
export function formatPeriod(period: string | null | undefined): string {
  const match = /^(\d{4})-(\d{2})$/.exec(period ?? "");
  if (!match) return period ?? "";
  const month = MONTHS[Number(match[2]) - 1];
  return month ? `${month} ${match[1]}` : (period ?? "");
}

// only http(s) links from the service are rendered as links
export function safeUrl(url: string | null | undefined): string | null {
  return url && /^https?:\/\//i.test(url) ? url : null;
}

// the note under the risk levels when the service's ceiling is below the IQ segment
export function serviceCeilingNote(segment: Segment, maxRisk: RiskLevel): string {
  return `IQ segmentin ${LEVEL_LABELS[segment] ?? segment}, ama risk tavanın şu an ${LEVEL_LABELS[maxRisk] ?? maxRisk}: aşağıdaki nedenler tavanı düşürüyor.`;
}

export const UNAVAILABLE_OPTION_NOTE = "Henüz seçilemiyor.";
export const AINVEST_UNAVAILABLE_NOTE = "AInvest önerisi henüz bir portföy türü olarak seçilemiyor; koşullu piyasa planları";

// The risk ceiling: the Portfolio Service's own (it can be below the IQ segment and PUT /preferences refuses a level
// above it); the segment only when the service's options are not there (mock mode, or the call failed).
export function riskCeiling(segment: Segment | null | undefined, options: PortfolioOptions | null | undefined): RiskLevel {
  return options?.maxRisk ?? maxRiskForSegment(segment);
}

// sentences for the reasons behind the ceiling; the investable reasons are shown with the investable steps instead
export function ceilingReasons(options: PortfolioOptions | null | undefined): string[] {
  if (!options) return [];
  const investable = options.investable.reasons ?? [];
  return [...new Set(options.reasons)].filter((code) => !investable.includes(code)).map((code) => reasonText(code).text);
}
