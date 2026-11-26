import { PORTFOLIO_SOURCE, type PortfolioSource } from "../config";
import { SAMPLE_PORTFOLIO_PROPOSAL } from "../mocks/portfolioProposal";
import type { ApiResult, PortfolioProposal } from "../types/api";
import type { PortfolioOptions } from "../types/portfolioService";
import { authorizedRequest, currentUserId } from "./authorizedRequest";
import { errorFrom, type CallOptions } from "./http";

// The allocation is computed by the Portfolio Service (deterministic, CLAUDE.md 8.4); the frontend only shows it.
// VITE_PORTFOLIO_SOURCE=mock (default) returns the draft schema's example; =service calls the gateway.

export interface PortfolioProposalResult {
  proposal: PortfolioProposal;
  // "mock": the schema example of a demo user, not the signed-in user's own proposal
  source: PortfolioSource;
}

export function portfolioSource(): PortfolioSource {
  return PORTFOLIO_SOURCE;
}

// null when the user has no proposal yet (404 from the service)
export async function getPortfolioProposal(options: CallOptions = {}): Promise<PortfolioProposalResult | null> {
  if (PORTFOLIO_SOURCE === "mock") {
    return { proposal: structuredClone(SAMPLE_PORTFOLIO_PROPOSAL), source: "mock" };
  }

  const response = await authorizedRequest<ApiResult<PortfolioProposal> | PortfolioProposal>(
    `/api/portfolio/${encodeURIComponent(currentUserId())}/latest`,
    options
  );
  if (response.status === 404) return null;
  const body = response.body;
  // the Portfolio Service uses the same { data, success, message } envelope as the .NET services
  const proposal = body && "proposalId" in body ? body : (body as ApiResult<PortfolioProposal> | null)?.data;
  if (response.status !== 200 || !proposal) throw errorFrom(response, "Portföy önerisi yüklenemedi.");
  return { proposal, source: "service" };
}

// What the user may choose (risk ceiling, investable amounts and their basis, options, institution sources).
// null in mock mode: the page then falls back to the IQ segment as the ceiling.
export async function getPortfolioOptions(options: CallOptions = {}): Promise<PortfolioOptions | null> {
  if (PORTFOLIO_SOURCE === "mock") return null;
  const response = await authorizedRequest<ApiResult<PortfolioOptions>>(
    `/api/portfolio/${encodeURIComponent(currentUserId())}/options`,
    options
  );
  const data = response.body?.data;
  if (response.status !== 200 || !data) throw errorFrom(response, "Portföy seçenekleri yüklenemedi.");
  return data;
}

export interface PortfolioChoice {
  option: PortfolioProposal["preferences"]["option"];
  riskLevel: PortfolioProposal["preferences"]["riskLevel"];
  institutionStyle: PortfolioProposal["preferences"]["institutionStyle"] | null;
  focusAssets: string[];
  excludedAssets: string[];
}

// The service refuses fields that do not belong to the chosen option, so only the option's own fields are sent.
export function choiceBody(choice: PortfolioChoice): PortfolioProposal["preferences"] {
  const body: PortfolioProposal["preferences"] = { option: choice.option, riskLevel: choice.riskLevel };
  if (choice.option === "INSTITUTION" && choice.institutionStyle) body.institutionStyle = choice.institutionStyle;
  if (choice.option === "CUSTOM") body.focusAssets = choice.focusAssets;
  if (choice.option === "CUSTOM" || choice.option === "STANDARD") body.excludedAssets = choice.excludedAssets;
  return body;
}

// Stores the choice and lets the Portfolio Service compute a new proposal (PUT preferences, then POST proposal).
// The allocation is the service's; nothing is computed here.
export async function computePortfolioProposal(choice: PortfolioChoice, options: CallOptions = {}): Promise<PortfolioProposal> {
  const base = `/api/portfolio/${encodeURIComponent(currentUserId())}`;
  const saved = await authorizedRequest<ApiResult<unknown>>(`${base}/preferences`, { ...options, method: "PUT", body: choiceBody(choice) });
  if (saved.status !== 200) throw errorFrom(saved, "Seçimin kaydedilemedi.");
  const created = await authorizedRequest<ApiResult<PortfolioProposal>>(`${base}/proposal`, { ...options, method: "POST", body: {} });
  const proposal = created.body?.data;
  if (created.status !== 200 || !proposal) throw errorFrom(created, "Öneri hesaplanamadı.");
  return proposal;
}
