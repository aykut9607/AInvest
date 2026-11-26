import type { ApiResult, DebtPayoff, FactorBreakdown, FinancialProfile, IqCalculation, ProfileInput, Segment } from "../types/api";
import { authorizedRequest, currentUserId } from "./authorizedRequest";
import { translateServerMessage } from "../lib/messages";
import { errorFrom, type CallOptions } from "./http";

// Finance Profile through the gateway: /api/Profiles/{userId}/** is only reachable for the token's own user (403).

const profilePath = () => `/api/Profiles/${encodeURIComponent(currentUserId())}`;

// null when the user has no profile yet (404), so the form simply starts empty
export async function getProfile(options: CallOptions = {}): Promise<FinancialProfile | null> {
  const response = await authorizedRequest<ApiResult<FinancialProfile>>(profilePath(), options);
  if (response.status === 404) return null;
  if (response.status !== 200 || !response.body?.data) throw errorFrom(response, "Profil yüklenemedi.");
  const data = response.body.data;
  // a server without the payment habit fields leaves them out: unanswered
  return {
    ...data,
    billsOnTime: data.billsOnTime ?? null,
    minimumPaymentMonths: data.minimumPaymentMonths ?? null,
    latePayments: data.latePayments ?? null,
  };
}

// upsert; riskPreference is deliberately not sent (scoring v2 does not use it, the Portfolio Service will ask)
export async function saveProfile(input: ProfileInput, options: CallOptions = {}): Promise<void> {
  const response = await authorizedRequest<ApiResult<null>>(profilePath(), {
    ...options,
    method: "PUT",
    body: {
      monthlyIncome: input.monthlyIncome,
      monthlyExpenses: input.monthlyExpenses,
      monthlyDebtPayment: input.monthlyDebtPayment,
      totalDebt: input.totalDebt,
      cashReserve: input.cashReserve,
      investmentAmount: input.investmentAmount,
      impatienceLevel: input.impatienceLevel,
      // optional payment habits: only answered ones are sent (not part of the IQ score yet)
      ...(input.billsOnTime ? { billsOnTime: input.billsOnTime } : {}),
      ...(input.minimumPaymentMonths ? { minimumPaymentMonths: input.minimumPaymentMonths } : {}),
      ...(input.latePayments ? { latePayments: input.latePayments } : {}),
    },
  });
  if (response.status !== 200 || !response.body?.success) throw errorFrom(response, "Profil kaydedilemedi.");
}

interface CalculateIqBody {
  score: number;
  segment: Segment;
  // contract v2 sends an object; a v1 server sent the same JSON as a string
  factorBreakdown: FactorBreakdown | string | null;
}

// Finance Profile sends the saved profile to Financial IQ and returns its result (404 no profile, 502 IQ down)
export async function calculateIq(options: CallOptions = {}): Promise<IqCalculation> {
  const response = await authorizedRequest<ApiResult<CalculateIqBody>>(`${profilePath()}/calculate-iq`, {
    ...options,
    method: "POST",
  });
  const data = response.body?.data;
  if (response.status !== 200 || !data) throw errorFrom(response, "Finansal IQ hesaplanamadı.");
  return { score: data.score, segment: data.segment, factorBreakdown: parseFactorBreakdown(data.factorBreakdown) };
}

export interface DebtPayoffResult {
  payoff: DebtPayoff;
  // the service's explanation, translated; says why when paidOff is false
  message: string;
}

export const DEFAULT_MONTHLY_INTEREST_RATE = 0.035;

// amortisation of the saved totalDebt with the saved monthlyDebtPayment; null when there is no profile (404)
export async function getDebtPayoff(
  monthlyInterestRate: number = DEFAULT_MONTHLY_INTEREST_RATE,
  options: CallOptions = {}
): Promise<DebtPayoffResult | null> {
  const query = `?monthlyInterestRate=${encodeURIComponent(String(monthlyInterestRate))}`;
  const response = await authorizedRequest<ApiResult<DebtPayoff>>(`${profilePath()}/debt-payoff${query}`, options);
  if (response.status === 404) return null;
  if (response.status !== 200 || !response.body?.data) throw errorFrom(response, "Borç ödeme planı hesaplanamadı.");
  return { payoff: response.body.data, message: translateServerMessage(response.body.message ?? "") };
}

// v2: already an object; a string (v1 server) is still parsed. {} or anything without factors = no breakdown.
// The object itself is kept as received so it can go to /ai/explain-financial-iq unchanged.
export function parseFactorBreakdown(raw: unknown): FactorBreakdown | null {
  let value: unknown = raw;
  if (typeof raw === "string") {
    try {
      value = JSON.parse(raw);
    } catch {
      return null;
    }
  }
  if (!value || typeof value !== "object") return null;
  const candidate = value as Partial<FactorBreakdown>;
  if (!candidate.factors || typeof candidate.factors !== "object") return null;
  // the AI service treats a missing warnings list as empty, so the copy means the same thing
  return Array.isArray(candidate.warnings) ? (candidate as FactorBreakdown) : ({ ...candidate, warnings: [] } as FactorBreakdown);
}
