// Display helpers for a portfolio proposal. Nothing here computes an allocation or an investable amount: those come
// from the Portfolio Service (or the draft schema's sample) and are only shown (CLAUDE.md 8.4).
import { assetLabel, portfolioReasonLabel } from "../../lib/labels";
import type { IqResult, PortfolioProposal } from "../../types/api";
import type { PortfolioSource } from "../../config";

function time(value: string | undefined | null): number | null {
  if (!value) return null;
  const ms = new Date(value).getTime();
  return Number.isNaN(ms) ? null : ms;
}

// Same rule as the AI service (services/portfolio.py _stale_since): the proposal is stale when the latest IQ was
// calculated after the one the proposal is based on, or has a different score. Only meaningful for the service's own
// proposal: the sample belongs to a demo user, comparing it with the signed-in user's IQ says nothing.
// (Later: compare IQ's resultVersion instead of dates, CLAUDE.md 5.4.)
export function isProposalStale(
  proposal: Pick<PortfolioProposal, "basedOn">,
  latest: Pick<IqResult, "score" | "updatedAt" | "createdAt"> | null,
  source: PortfolioSource
): boolean {
  if (source !== "service" || !latest) return false;
  const based = time(proposal.basedOn.iqCalculatedAt);
  const latestAt = time(latest.updatedAt) ?? time(latest.createdAt);
  if (based !== null && latestAt !== null && latestAt > based) return true;
  return latest.score !== proposal.basedOn.iqScore;
}

export interface ReasonText {
  text: string;
  // true when the code is not known yet and is shown as it came
  raw: boolean;
}

// a known reason code -> Turkish sentence; an unknown one is shown as the raw code (React escapes it)
export function reasonText(code: string): ReasonText {
  const label = portfolioReasonLabel(code);
  return label ? { text: label, raw: false } : { text: code, raw: true };
}

const DISCLAIMERS: Record<string, string> = {
  "This is not investment advice.": "Bu bir yatırım tavsiyesi değildir.",
  "This is not investment advice": "Bu bir yatırım tavsiyesi değildir.",
};

export function disclaimerText(disclaimer: string | null | undefined): string {
  const text = (disclaimer ?? "").trim();
  if (!text) return "Bu bir yatırım tavsiyesi değildir.";
  return DISCLAIMERS[text] ?? text;
}

// ---- allocation bar --------------------------------------------------------------------------------------------

// categorical slots 1..8 in fixed order (tokens.css); past 8 parts the tail folds into "Diğer"
export const MAX_SLOTS = 8;

export interface AllocationPart {
  key: string;
  label: string;
  percent: number;
  amount: number;
  // CSS colour of the mark
  color: string;
  // colour of a label printed inside the mark
  ink: string;
}

const slotColor = (slot: number) => `var(--chart-${slot})`;
// per-slot ink with the higher contrast on that fill, light and dark (tokens.css --chart-ink-N)
const slotInk = (slot: number) => `var(--chart-ink-${slot})`;

// Parts for the segmented bar, in the service's order (colour follows the order the service sent, slot by slot).
// Parts at 0 % draw nothing. With more than 8 parts the rest is shown as one grey "Diğer" block; the table keeps them all.
export function allocationParts(allocations: PortfolioProposal["allocations"]): AllocationPart[] {
  const visible = allocations.filter((a) => Number.isFinite(a.percent) && a.percent > 0);
  const head = visible.length > MAX_SLOTS ? visible.slice(0, MAX_SLOTS - 1) : visible;
  const tail = visible.length > MAX_SLOTS ? visible.slice(MAX_SLOTS - 1) : [];
  const parts = head.map((a, index) => ({
    key: a.asset,
    label: assetLabel(a.asset),
    percent: a.percent,
    amount: a.amount,
    color: slotColor(index + 1),
    ink: slotInk(index + 1),
  }));
  if (tail.length > 0) {
    parts.push({
      key: "__other",
      label: "Diğer",
      percent: tail.reduce((sum, a) => sum + a.percent, 0),
      amount: tail.reduce((sum, a) => sum + a.amount, 0),
      color: "var(--color-border-strong)",
      ink: "var(--color-text)",
    });
  }
  return parts;
}

// colour of each table row's swatch: the part's colour, grey for the folded tail
export function swatchFor(parts: AllocationPart[], asset: string): string {
  return parts.find((p) => p.key === asset)?.color ?? "var(--color-border-strong)";
}

// a label fits inside a block when the block is wider than the text plus padding (approx. 7.5 px per character at
// 12 px semibold); before the bar is measured, only blocks of at least 12 % get one
export function labelFits(percent: number, barWidth: number | null, label: string): boolean {
  if (barWidth === null) return percent >= 12;
  const blockWidth = (percent / 100) * barWidth - 2;
  return blockWidth >= label.length * 7.5 + 16;
}
