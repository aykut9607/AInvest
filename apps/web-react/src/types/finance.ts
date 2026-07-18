export interface FinancialProfileFormData {
  userId: string;
  monthlyIncome: string;
  monthlyExpenses: string;
  monthlyDebtPayment: string;
  totalDebt: string;
  cashReserve: string;
  investmentAmount: string;
  riskPreference: "LOW" | "MEDIUM" | "HIGH";
}

export interface FinancialScoreResult {
  score: number;
  segment: "STRONG" | "BALANCED" | "NEEDS_IMPROVEMENT" | "HIGH_RISK";
}

/*80-100 → STRONG
60-79  → BALANCED
40-59  → NEEDS_IMPROVEMENT
0-39   → HIGH_RISK */