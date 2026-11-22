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
  impatienceLevel: number;
}

export type AppliedRule = "VERY_HIGH_INCOME" | "VERY_HIGH_WEALTH" | "EXTREME_DEBT";

// shape of the factorBreakdown object produced by the Financial IQ service (contract v2: 5 factors,
// no self-reported risk any more)
export interface FactorBreakdown {
  version?: string;
  factors: Record<string, number>;
  warnings: string[];
  // set when an extreme amount decided the score instead of the 5 factors; null/absent otherwise
  appliedRule?: AppliedRule | null;
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
