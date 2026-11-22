export interface FinancialProfileFormData {
  userId: string;
  monthlyIncome: string;
  monthlyExpenses: string;
  monthlyDebtPayment: string;
  totalDebt: string;
  cashReserve: string;
  investmentAmount: string;
  // "1" = can wait years for a return, "5" = wants results right away
  impatienceLevel: "1" | "2" | "3" | "4" | "5";
}

// factorBreakdown object of the Financial IQ service (contract v2: 5 factors, no self-reported risk)
export interface FactorBreakdown {
  version?: string;
  factors: Record<string, number>;
  warnings: string[];
  appliedRule?: "VERY_HIGH_INCOME" | "VERY_HIGH_WEALTH" | "EXTREME_DEBT" | null;
}

export interface FinancialScoreResult {
  score: number;
  segment: "LOW" | "MEDIUM" | "HIGH";
  factorBreakdown: FactorBreakdown | null;
}

/*0-40   -> LOW
41-70  -> MEDIUM
71-100 -> HIGH */