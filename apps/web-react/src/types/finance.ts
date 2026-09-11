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
  segment: "LOW" | "MEDIUM" | "HIGH";
}

/*0-40   -> LOW
41-70  -> MEDIUM
71-100 -> HIGH */