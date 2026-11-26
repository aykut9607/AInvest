import type {
  AskResponse,
  AssistantMode,
  ExplainRequest,
  ExplainResponse,
  PortfolioExplanationResponse,
  TrendResponse,
  WarningsResponse,
} from "../types/api";
import { authorizedRequest } from "./authorizedRequest";
import { errorFrom, type ApiResponse, type CallOptions } from "./http";

// AI / RAG through the gateway (/ai/**, any valid token). 10 requests a minute per user -> RateLimitError.
// Timeout 70 s (the local model may take up to 60 s). The AI service reads the user's data from the gateway itself,
// with the same token; the web app never sends amounts it was not asked for.

function expectOk<T>(response: ApiResponse<T>, fallback: string): T {
  if (response.status !== 200 || !response.body) throw errorFrom(response, fallback);
  return response.body;
}

// Coach: explains score + factor breakdown. Send the breakdown exactly as the IQ service returned it: the AI service
// checks that the factor points add up to the score (422 otherwise). Without a breakdown the template is used.
export async function explainScore(input: ExplainRequest, options: CallOptions = {}): Promise<ExplainResponse> {
  const body: ExplainRequest = input.factorBreakdown
    ? { score: input.score, segment: input.segment, factorBreakdown: input.factorBreakdown }
    : { score: input.score, segment: input.segment };
  const response = await authorizedRequest<ExplainResponse>("/ai/explain-financial-iq", { ...options, method: "POST", body });
  return expectOk(response, "Skor açıklaması alınamadı.");
}

export const ASSISTANT_QUESTION_MAX_LENGTH = 500;

// Assistant: answers from the user's live data. mode overrides the server default (router | tools)
export async function askAssistant(question: string, mode?: AssistantMode, options: CallOptions = {}): Promise<AskResponse> {
  const body = mode ? { question, mode } : { question };
  const response = await authorizedRequest<AskResponse>("/ai/assistant/ask", { ...options, method: "POST", body });
  return expectOk(response, "Asistan cevap veremedi.");
}

// rule-based alerts (no model): monthly deficit, emergency fund, installments, total debt, impatience, score drop
export async function getWarnings(options: CallOptions = {}): Promise<WarningsResponse> {
  const response = await authorizedRequest<WarningsResponse>("/ai/insights/warnings", options);
  return expectOk(response, "Uyarılar yüklenemedi.");
}

// explanation of the score history (/history + latest result)
export async function explainTrend(options: CallOptions = {}): Promise<TrendResponse> {
  const response = await authorizedRequest<TrendResponse>("/ai/explain-iq-trend", options);
  return expectOk(response, "Skor geçmişi açıklaması alınamadı.");
}

// explanation of the portfolio proposal; source "sample" while the Portfolio Service does not exist,
// stale = the proposal is based on an older IQ than the latest one
export async function explainPortfolio(options: CallOptions = {}): Promise<PortfolioExplanationResponse> {
  const response = await authorizedRequest<PortfolioExplanationResponse>("/ai/explain-portfolio", options);
  return expectOk(response, "Portföy açıklaması alınamadı.");
}
