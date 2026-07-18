import axios from "axios";

const AI_BASE_URL = import.meta.env.VITE_AI_EXPLANATION_API_BASE_URL as string;

export interface ExplainResult {
  explanation: string;
  disclaimer: string;
}

export async function explainFinancialScore(
  score: number,
  segment: string
): Promise<ExplainResult> {
  const response = await axios.post<ExplainResult>(
    `${AI_BASE_URL}/ai/explain-financial-iq`,
    { score, segment }
  );
  return response.data;
}