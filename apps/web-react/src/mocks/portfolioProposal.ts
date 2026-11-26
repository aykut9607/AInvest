import type { PortfolioProposal } from "../types/api";

// The example of contracts/schemas/portfolio-proposal.draft.schema.json (also services/ai-rag-service/adapters/
// portfolio_sample.py), used while the Portfolio Service does not exist (VITE_PORTFOLIO_SOURCE=mock).
// It belongs to a demo user with IQ 88 (income 20,000, expenses 8,000, installment 2,000, cash 30,000), not to the
// signed-in user: show it as sample data. The numbers were computed by the planned service's rules, never by the
// frontend.
export const SAMPLE_PORTFOLIO_PROPOSAL: PortfolioProposal = {
  proposalId: "7d1f3c2a-1111-4b6e-9a3e-0c8e2f5d9a01",
  userId: "demo.high",
  createdAt: "2026-11-26T10:00:00Z",
  basedOn: { iqScore: 88, segment: "HIGH", appliedRule: null, iqCalculatedAt: "2026-11-26T09:58:00Z", scoringVersion: "v2" },
  preferences: { option: "STANDARD", riskLevel: "MEDIUM", focusAssets: [], excludedAssets: ["BTC"] },
  risk: { chosen: "MEDIUM", maxAllowed: "HIGH" },
  investable: { sharePercent: 58, monthlyAmount: 5800, oneTimeAmount: 3480 },
  allocations: [
    { asset: "GOLD", percent: 30, amount: 1740 },
    { asset: "TRY_DEPOSIT", percent: 25, amount: 1450 },
    { asset: "SPX", percent: 25, amount: 1450 },
    { asset: "EUR", percent: 10, amount: 580 },
    { asset: "NVDA", percent: 10, amount: 580 },
  ],
  reasons: ["EXCLUDED_ASSET_REPLACED:BTC->GOLD"],
  disclaimer: "This is not investment advice.",
};
