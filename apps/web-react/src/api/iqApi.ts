import type { ApiResult, IqResult, IqTrendPoint, ScoringRules } from "../types/api";
import { authorizedRequest, currentUserId } from "./authorizedRequest";
import { parseFactorBreakdown } from "./financeApi";
import { errorFrom, type CallOptions } from "./http";

// Financial IQ through the gateway: only GET {userId}/latest, {userId}/history (own user only) and scoring-rules.
// Calculating goes through Finance Profile (financeApi.calculateIq).

const iqPath = () => `/api/financial-iq/${encodeURIComponent(currentUserId())}`;

// null when nothing has been calculated yet (404)
export async function getLatestIq(options: CallOptions = {}): Promise<IqResult | null> {
  const response = await authorizedRequest<ApiResult<IqResult>>(`${iqPath()}/latest`, options);
  if (response.status === 404) return null;
  const data = response.body?.data;
  if (response.status !== 200 || !data) throw errorFrom(response, "Son Finansal IQ sonucu yüklenemedi.");
  return { ...data, factorBreakdown: parseFactorBreakdown(data.factorBreakdown) };
}

// oldest first; [] when there is no history yet (404). take: 1-100
export async function getIqHistory(take = 12, options: CallOptions = {}): Promise<IqTrendPoint[]> {
  const count = Math.min(100, Math.max(1, Math.round(take)));
  const response = await authorizedRequest<ApiResult<IqTrendPoint[]>>(`${iqPath()}/history?take=${count}`, options);
  if (response.status === 404) return [];
  if (response.status !== 200 || !Array.isArray(response.body?.data)) {
    throw errorFrom(response, "Skor geçmişi yüklenemedi.");
  }
  return response.body.data;
}

// the active scoring version with its full rule set (segments, factor tiers, special rules)
export async function getScoringRules(options: CallOptions = {}): Promise<ScoringRules> {
  const response = await authorizedRequest<ApiResult<ScoringRules>>("/api/financial-iq/scoring-rules/current", options);
  if (response.status !== 200 || !response.body?.data) throw errorFrom(response, "Skor kuralları yüklenemedi.");
  return response.body.data;
}
