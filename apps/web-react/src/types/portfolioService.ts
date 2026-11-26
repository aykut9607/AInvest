// GET /api/portfolio/{userId}/options (services/portfolio-service/schemas/portfolio.py Options). Everything here is
// computed by the Portfolio Service; the web app only shows it.
import type { InstitutionStyle, PortfolioOption, RiskLevel, Segment } from "./api";

// where the investable amounts come from: surplus = income - expenses - installment; emergency fund = reserveMonths x
// expenses; freeCash = cash above the emergency fund; reserve = cash + half of the investments (the reserve check)
export interface InvestableBasis {
  monthlyIncome: number;
  monthlyExpenses: number;
  monthlyDebtPayment: number;
  monthlySurplus: number;
  cashReserve: number;
  investmentAmount: number;
  reserve: number;
  emergencyFund: number;
  freeCash: number;
  reserveMonths: number;
}

export interface ServiceInvestable {
  sharePercent: number;
  monthlyAmount: number;
  oneTimeAmount: number;
  basis?: InvestableBasis | null;
  // RESERVE_FIRST, NO_MONTHLY_SURPLUS, DEBT_FIRST
  reasons?: string[];
}

export interface PublishedSource {
  name: string;
  // the month the numbers were published for, "YYYY-MM"
  period: string;
  url: string;
}

export interface InstitutionStyleInfo {
  code: InstitutionStyle;
  label: string;
  description: string;
  source: PublishedSource;
}

export interface PortfolioOptions {
  iqScore: number;
  segment: Segment;
  // the service's risk ceiling; can be lower than the segment (CEILING_RESERVE, CEILING_NO_SURPLUS, CEILING_DEBT,
  // CEILING_IMPATIENCE) and PUT /preferences rejects a level above it
  maxRisk: RiskLevel;
  investable: ServiceInvestable;
  options: PortfolioOption[];
  // shown but not selectable yet
  unavailableOptions: PortfolioOption[];
  institutionStyles: InstitutionStyle[];
  institutionStyleInfo: InstitutionStyleInfo[];
  assets: string[];
  assetInfo: { code: string; label: string }[];
  reasons: string[];
}
