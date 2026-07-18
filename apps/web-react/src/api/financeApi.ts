import axios from "axios";
import type { FinancialProfileFormData } from "../types/finance";

const BASE_URL = import.meta.env.VITE_FINANCE_API_BASE_URL as string;

interface ApiResult<T> {
  data: T | null;
  success: boolean;
  message: string;
}

interface FinancialIqCalculateResponse {
  score: number;
  segment: "STRONG" | "BALANCED" | "NEEDS_IMPROVEMENT" | "HIGH_RISK";
}

export async function saveAndCalculateFinancialScore(
  userId: string,
  form: FinancialProfileFormData
): Promise<FinancialIqCalculateResponse> {
  const upsertBody = {
    monthlyIncome: Number(form.monthlyIncome),
    monthlyExpenses: Number(form.monthlyExpenses),
    monthlyDebtPayment: Number(form.monthlyDebtPayment),
    totalDebt: Number(form.totalDebt),
    cashReserve: Number(form.cashReserve),
    investmentAmount: Number(form.investmentAmount),
    riskPreference: form.riskPreference,
  };

  try {
    await axios.put(`${BASE_URL}/api/Profiles/${userId}`, upsertBody);
  } catch (err) {
    throw new Error(extractErrorMessage(err, "Failed to save financial profile."), { cause: err });
  }

  try {
    const response = await axios.post<ApiResult<FinancialIqCalculateResponse>>(
      `${BASE_URL}/api/Profiles/${userId}/calculate-iq`
    );

    if (!response.data.success || !response.data.data) {
      throw new Error(response.data.message || "Failed to calculate financial IQ.");
    }

    return response.data.data;
  } catch (err) {
    throw new Error(extractErrorMessage(err, "Failed to calculate financial IQ."), { cause: err });
  }
}

function extractErrorMessage(err: unknown, fallback: string): string {
  if (axios.isAxiosError(err)) {
    const data = err.response?.data as ApiResult<unknown> | undefined;
    if (data?.message) return data.message;
  }
  return fallback;
}