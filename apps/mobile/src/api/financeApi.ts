import { API } from "../config";
import type { ApiResult, FactorBreakdown, FinancialProfile, IqResult, ProfileForm, Segment } from "../types";
import { ApiError, messageFrom, request } from "./http";

interface CalculateIqResponse {
  score: number;
  segment: Segment;
  factorBreakdown: string;
}

// returns null when the user has no profile yet (404), so the form simply starts empty
export async function getProfile(userId: string): Promise<FinancialProfile | null> {
  const { status, body } = await request<ApiResult<FinancialProfile>>(
    `${API.finance}/api/Profiles/${encodeURIComponent(userId)}`
  );

  if (status === 404) return null;
  if (status !== 200 || !body?.data) {
    throw new ApiError(messageFrom(body, "Could not load the profile."), status);
  }
  return body.data;
}

export async function saveProfile(userId: string, form: ProfileForm): Promise<void> {
  const { status, body } = await request<ApiResult<null>>(
    `${API.finance}/api/Profiles/${encodeURIComponent(userId)}`,
    {
      method: "PUT",
      body: {
        monthlyIncome: toNumber(form.monthlyIncome),
        monthlyExpenses: toNumber(form.monthlyExpenses),
        monthlyDebtPayment: toNumber(form.monthlyDebtPayment),
        totalDebt: toNumber(form.totalDebt),
        cashReserve: toNumber(form.cashReserve),
        investmentAmount: toNumber(form.investmentAmount),
        riskPreference: form.riskPreference,
        impatienceLevel: form.impatienceLevel,
      },
    }
  );

  if (status !== 200 || !body?.success) {
    throw new ApiError(messageFrom(body, "Could not save the profile."), status);
  }
}

// Finance Profile forwards the profile to the Financial IQ service and returns its result
export async function calculateIq(userId: string): Promise<IqResult> {
  const { status, body } = await request<ApiResult<CalculateIqResponse>>(
    `${API.finance}/api/Profiles/${encodeURIComponent(userId)}/calculate-iq`,
    { method: "POST" }
  );

  if (status !== 200 || !body?.data) {
    throw new ApiError(messageFrom(body, "Could not calculate the Financial IQ."), status);
  }

  return {
    score: body.data.score,
    segment: body.data.segment,
    breakdown: parseBreakdown(body.data.factorBreakdown),
  };
}

// factorBreakdown arrives as a JSON string inside the JSON response
function parseBreakdown(raw: string | undefined): FactorBreakdown | null {
  if (!raw) return null;
  try {
    return JSON.parse(raw) as FactorBreakdown;
  } catch {
    return null;
  }
}

// the form keeps digits only (see ProfileScreen), so grouping like "30.000" can't shrink to 30; empty fields count as 0
function toNumber(value: string): number {
  const parsed = Number(value.replace(/\D/g, ""));
  return Number.isFinite(parsed) ? parsed : 0;
}
