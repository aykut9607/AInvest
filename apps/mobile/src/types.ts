export type RiskLevel = "LOW" | "MEDIUM" | "HIGH";
export type Segment = "LOW" | "MEDIUM" | "HIGH";

export interface AuthSession {
  accessToken: string;
  refreshToken: string;
  // JWT "sub" claim from the Identity service, used as the userId in the other services
  userId: string;
  email: string;
}

// form values are kept as strings while typing, converted to numbers on submit
export interface ProfileForm {
  monthlyIncome: string;
  monthlyExpenses: string;
  monthlyDebtPayment: string;
  totalDebt: string;
  cashReserve: string;
  investmentAmount: string;
  riskPreference: RiskLevel;
  impatienceLevel: number;
}

export interface FinancialProfile {
  userId: string;
  monthlyIncome: number;
  monthlyExpenses: number;
  monthlyDebtPayment: number;
  totalDebt: number;
  cashReserve: number;
  investmentAmount: number;
  riskPreference: RiskLevel;
  impatienceLevel: number;
}

export interface RiskProfile {
  stated: RiskLevel;
  behavioral: RiskLevel;
  inconsistent: boolean;
  direction: "OVERSTATED" | "UNDERSTATED" | "ALIGNED";
}

// shape of the factorBreakdown JSON produced by the Financial IQ service
export interface FactorBreakdown {
  factors: Record<string, number>;
  warnings: string[];
  riskProfile?: RiskProfile;
}

export interface IqResult {
  score: number;
  segment: Segment;
  breakdown: FactorBreakdown | null;
}

export interface Explanation {
  explanation: string;
  disclaimer: string;
}

// standard envelope returned by the .NET services (Result pattern)
export interface ApiResult<T> {
  data: T | null;
  success: boolean;
  message: string;
}
