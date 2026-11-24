using FinanceProfile.Api.Domain.Common;

namespace FinanceProfile.Api.DTOs;

    public class UpsertFinancialProfileRequest: IDto
    {
        public decimal MonthlyIncome { get; set; }

        public decimal MonthlyExpenses { get; set; }

        public decimal MonthlyDebtPayment { get; set; }

        public decimal TotalDebt { get; set; }

        public decimal CashReserve { get; set; }

        public decimal InvestmentAmount { get; set; }

        // optional (scoring v2 does not use it); when sent it must still be LOW, MEDIUM or HIGH
        public string? RiskPreference { get; set; }

        public int ImpatienceLevel { get; set; } = 3;
    }