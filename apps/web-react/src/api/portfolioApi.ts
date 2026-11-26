import { PORTFOLIO_SOURCE, type PortfolioSource } from "../config";
import { SAMPLE_PORTFOLIO_PROPOSAL } from "../mocks/portfolioProposal";
import type { ApiResult, PortfolioProposal } from "../types/api";
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
