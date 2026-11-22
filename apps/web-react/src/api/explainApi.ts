import axios from "axios";
import type { FactorBreakdown } from "../types/finance";

const AI_BASE_URL = import.meta.env.VITE_AI_EXPLANATION_API_BASE_URL as string;

export interface ExplainResult {
  explanation: string;
  disclaimer: string;
}

// factorBreakdown is optional: the AI service uses it to explain the factors, warnings and applied rule;
// a service that doesn't know the field ignores it
export async function explainFinancialScore(
  score: number,
  segment: string,
  factorBreakdown: FactorBreakdown | null
): Promise<ExplainResult> {
  const response = await axios.post<ExplainResult>(
    `${AI_BASE_URL}/ai/explain-financial-iq`,
    factorBreakdown ? { score, segment, factorBreakdown } : { score, segment }
  );
  return response.data;
}