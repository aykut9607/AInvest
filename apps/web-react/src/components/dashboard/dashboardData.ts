// Pure data helpers of the dashboard (/panel): which result to show, alert order, factor tones, trend and debt rows,
// the interest input. No React, no fetch; unit tested in dashboardData.test.ts.
import { formatDateTime, formatNumber, formatShortDate, formatSigned } from "../../lib/format";
import type { Alert, DebtPayoff, FactorBreakdown, IqCalculation, IqResult, IqTrendPoint, Segment, Severity } from "../../types/api";

// ---- the result on screen ------------------------------------------------------------------------------------------

export interface DashboardResult {
  score: number;
  segment: Segment;
  // exactly as the service sent it: goes to /ai/explain-financial-iq unchanged
  factorBreakdown: FactorBreakdown | null;
  // ISO time of the calculation; null for a result that only came with the navigation (not loaded from /latest yet)
  calculatedAt: string | null;
  // changes whenever the content changes: resets the Coach answer for a new result
  key: string;
}

const SEGMENTS: Segment[] = ["LOW", "MEDIUM", "HIGH"];

// location.state is whatever the previous page pushed (or a stale history entry): accept only a real calculation
export function freshCalculation(state: unknown): IqCalculation | undefined {
  if (!state || typeof state !== "object") return undefined;
  const calculation = (state as { calculation?: unknown }).calculation;
  if (!calculation || typeof calculation !== "object") return undefined;
  const candidate = calculation as Partial<IqCalculation>;
  if (typeof candidate.score !== "number" || !SEGMENTS.includes(candidate.segment as Segment)) return undefined;
  return { score: candidate.score, segment: candidate.segment as Segment, factorBreakdown: candidate.factorBreakdown ?? null };
}

function resultKey(score: number, segment: Segment, breakdown: FactorBreakdown | null): string {
  return `${score}|${segment}|${JSON.stringify(breakdown)}`;
}

// /latest wins once it is loaded (the service's own record, with its time); until then (or if it fails) the
// calculation the profile page just made is shown; null = nothing to show (no score yet, or still loading)
export function currentResult(fresh: IqCalculation | undefined, latest: IqResult | null | undefined): DashboardResult | null {
  if (latest) {
    return {
      score: latest.score,
      segment: latest.segment,
      factorBreakdown: latest.factorBreakdown,
      calculatedAt: latest.updatedAt || latest.createdAt || null,
      key: resultKey(latest.score, latest.segment, latest.factorBreakdown),
    };
  }
  if (fresh) {
    return {
      score: fresh.score,
      segment: fresh.segment,
      factorBreakdown: fresh.factorBreakdown,
      calculatedAt: null,
      key: resultKey(fresh.score, fresh.segment, fresh.factorBreakdown),
    };
  }
  return null;
}

// ---- factor bars ---------------------------------------------------------------------------------------------------

export type FactorTone = "good" | "warning" | "critical";

export const FACTOR_TONE_LABELS: Record<FactorTone, string> = { good: "güçlü", warning: "orta", critical: "zayıf" };

// share of the maximum, clamped to 0..1
export function factorRatio(points: number, max: number): number {
  if (!(max > 0) || !Number.isFinite(points)) return 0;
  return Math.min(1, Math.max(0, points / max));
}

// same thresholds as the mobile FactorBar: >= 70 % strong, >= 40 % partial, below that weak
export function factorTone(points: number, max: number): FactorTone {
  const ratio = factorRatio(points, max);
  if (ratio >= 0.7) return "good";
  if (ratio >= 0.4) return "warning";
  return "critical";
}

// ---- alerts --------------------------------------------------------------------------------------------------------

const SEVERITY_ORDER: Record<Severity, number> = { CRITICAL: 0, WARNING: 1, INFO: 2 };

// CRITICAL -> WARNING -> INFO, keeping the service's order within a level; an unknown severity goes last
export function sortAlerts(alerts: readonly Alert[]): Alert[] {
  const rank = (alert: Alert) => SEVERITY_ORDER[alert.severity] ?? 3;
  return alerts
    .map((alert, index) => ({ alert, index }))
    .sort((a, b) => rank(a.alert) - rank(b.alert) || a.index - b.index)
    .map(({ alert }) => alert);
}

// shown while the local model writes an explanation (it may take up to a minute)
export const MODEL_WAIT_LABEL = "Model düşünüyor, bu 30–60 saniye sürebilir";

// the countdown text for a 429 on /ai/* (10 requests a minute per user)
export function aiRateLimitMessage(seconds: number): string {
  return `Yapay zekâ için dakikalık istek sınırına ulaşıldı. ${seconds} saniye sonra tekrar deneyebilirsin.`;
}

// ---- trend ---------------------------------------------------------------------------------------------------------

const TIME = new Intl.DateTimeFormat("tr-TR", { hour: "2-digit", minute: "2-digit", timeZone: "Europe/Istanbul" });

// "01.11.2026 12:00" (table rows: short enough for a phone)
export function formatShortDateTime(value: string): string {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "" : `${formatShortDate(date)} ${TIME.format(date)}`;
}

export interface TrendRow {
  key: string;
  date: string;
  score: number;
  segment: Segment;
  // signed ("+29", "−3") or "–" for the first calculation
  change: string;
  // 3-point moving average with one decimal ("35,7")
  average: string;
}

export function formatChange(change: number | null): string {
  return change === null || change === undefined ? "–" : formatSigned(change);
}

export function formatAverage(value: number): string {
  return Number.isFinite(value) ? formatNumber(value, 1) : "–";
}

export function trendRows(points: readonly IqTrendPoint[]): TrendRow[] {
  return points.map((point, index) => ({
    key: `${point.calculatedAt}-${index}`,
    date: formatShortDateTime(point.calculatedAt),
    score: point.score,
    segment: point.segment,
    change: formatChange(point.scoreChange),
    average: formatAverage(point.movingAverage3),
  }));
}

// read by screen readers for the point the keyboard / pointer is on
export function describeTrendPoint(point: IqTrendPoint): string {
  return `${formatDateTime(point.calculatedAt)}: skor ${point.score}, değişim ${formatChange(point.scoreChange)}, 3'lü ortalama ${formatAverage(point.movingAverage3)}.`;
}

// accessible name of the trend chart (the table view carries every value)
export function trendSummary(points: readonly IqTrendPoint[]): string {
  if (points.length === 0) return "Skor geçmişi yok.";
  const scores = points.map((p) => p.score);
  const first = points[0].score;
  const last = points[points.length - 1].score;
  return `Skor geçmişi grafiği, ${points.length} hesaplama: ilk skor ${first}, son skor ${last}, en düşük ${Math.min(...scores)}, en yüksek ${Math.max(...scores)}.`;
}


// x axis labels of the trend: the date, or the time of day when every calculation happened on the same day
export function trendAxisLabels(points: readonly IqTrendPoint[]): string[] {
  const dates = points.map((p) => formatShortDate(p.calculatedAt));
  const sameDay = dates.length > 1 && dates.every((d) => d === dates[0]);
  if (!sameDay) return dates;
  return points.map((p) => {
    const date = new Date(p.calculatedAt);
    return Number.isNaN(date.getTime()) ? "" : TIME.format(date);
  });
}

// ---- debt payoff ---------------------------------------------------------------------------------------------------

export const DEFAULT_INTEREST_PERCENT = 3.5;

export type PercentParse = { ok: true; value: number } | { ok: false; error: string };

// the monthly interest field: "3,5", "3.5", "0" ... in percent, 0-100, at most 4 decimals
export function parsePercentInput(text: string): PercentParse {
  const trimmed = text.trim().replace(/^%/, "").trim();
  if (!/^\d{1,3}([.,]\d{1,4})?$/.test(trimmed)) {
    return { ok: false, error: "Aylık faiz oranını 0 ile 100 arasında bir sayı olarak yaz (ör. 3,5)." };
  }
  const value = Number(trimmed.replace(",", "."));
  if (!(value >= 0 && value <= 100)) {
    return { ok: false, error: "Aylık faiz oranı 0 ile 100 arasında olmalı." };
  }
  return { ok: true, value };
}

// 3.5 (%) -> 0.035 without floating noise in the query string
export function percentToRate(percent: number): number {
  return Number((percent / 100).toFixed(6));
}

// 3.5 -> "3,5" for the input
export function percentToText(percent: number): string {
  return formatNumber(percent, 4);
}

// 13 -> "13 ay (1 yıl 1 ay)", 24 -> "24 ay (2 yıl)", 7 -> "7 ay"
export function formatMonths(months: number): string {
  if (months < 12) return `${months} ay`;
  const years = Math.floor(months / 12);
  const rest = months % 12;
  return `${months} ay (${years} yıl${rest > 0 ? ` ${rest} ay` : ""})`;
}

export interface BalancePoint {
  month: number;
  balance: number;
  interest: number | null;
  principal: number | null;
}

// month 0 = today's debt, then the closing balance of every month
export function balanceSeries(payoff: DebtPayoff): BalancePoint[] {
  if (payoff.schedule.length === 0) return [];
  return [
    { month: 0, balance: payoff.totalDebt, interest: null, principal: null },
    ...payoff.schedule.map((m) => ({ month: m.month, balance: m.closingBalance, interest: m.interest, principal: m.principal })),
  ];
}

export type DebtState = "no-debt" | "paid-off" | "not-paid-off";

export function debtState(payoff: DebtPayoff): DebtState {
  if (payoff.totalDebt <= 0) return "no-debt";
  return payoff.paidOff ? "paid-off" : "not-paid-off";
}
