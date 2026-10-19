export interface FinancialProfileFormData {
  userId: string;
  monthlyIncome: string;
  monthlyExpenses: string;
  monthlyDebtPayment: string;
  totalDebt: string;
  cashReserve: string;
  investmentAmount: string;
  riskPreference: "LOW" | "MEDIUM" | "HIGH";
  // "1" = can wait years for a return, "5" = wants results right away
  impatienceLevel: "1" | "2" | "3" | "4" | "5";
}

export interface FinancialScoreResult {
  score: number;
  segment: "LOW" | "MEDIUM" | "HIGH";
}

/*0-40   -> LOW
41-70  -> MEDIUM
71-100 -> HIGH */