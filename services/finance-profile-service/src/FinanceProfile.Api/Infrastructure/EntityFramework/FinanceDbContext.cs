using Microsoft.EntityFrameworkCore;
using FinanceProfile.Api.Domain.Entities;

namespace FinanceProfile.Api.Infrastructure.EntityFramework;

public class FinanceDbContext : DbContext
{
    public FinanceDbContext(DbContextOptions<FinanceDbContext> options) : base(options) { }

    public DbSet<FinancialProfile> FinancialProfiles { get; set; }

    protected override void OnModelCreating(ModelBuilder modelBuilder)
    {
        // mapping mirrors the hand-made table in Database/finance_db_financial_profiles.sql
        // (same types, defaults and constraint names) so the InitialCreate migration is a true baseline
        modelBuilder.Entity<FinancialProfile>(entity =>
        {
            entity.ToTable("financial_profiles", t =>
            {
                t.HasCheckConstraint("financial_profiles_monthly_income_check", "monthly_income > 0");
                t.HasCheckConstraint("financial_profiles_monthly_expenses_check", "monthly_expenses >= 0");
                t.HasCheckConstraint("financial_profiles_monthly_debt_payment_check", "monthly_debt_payment >= 0");
                t.HasCheckConstraint("financial_profiles_total_debt_check", "total_debt >= 0");
                t.HasCheckConstraint("financial_profiles_cash_reserve_check", "cash_reserve >= 0");
                t.HasCheckConstraint("financial_profiles_investment_amount_check", "investment_amount >= 0");
                t.HasCheckConstraint("financial_profiles_risk_preference_check", "risk_preference IN ('LOW', 'MEDIUM', 'HIGH')");
                t.HasCheckConstraint("financial_profiles_impatience_level_check", "impatience_level BETWEEN 1 AND 5");
            });

            entity.HasKey(p => p.Id).HasName("financial_profiles_pkey");
            entity.HasIndex(p => p.UserId).IsUnique().HasDatabaseName("financial_profiles_user_id_key");

            entity.Property(p => p.Id).HasColumnName("id").HasDefaultValueSql("gen_random_uuid()");
            entity.Property(p => p.UserId).HasColumnName("user_id").HasMaxLength(100);
            entity.Property(p => p.MonthlyIncome).HasColumnName("monthly_income").HasPrecision(18, 2);
            entity.Property(p => p.MonthlyExpenses).HasColumnName("monthly_expenses").HasPrecision(18, 2);
            entity.Property(p => p.MonthlyDebtPayment).HasColumnName("monthly_debt_payment").HasPrecision(18, 2);
            entity.Property(p => p.TotalDebt).HasColumnName("total_debt").HasPrecision(18, 2);
            entity.Property(p => p.CashReserve).HasColumnName("cash_reserve").HasPrecision(18, 2);
            entity.Property(p => p.InvestmentAmount).HasColumnName("investment_amount").HasPrecision(18, 2);
            entity.Property(p => p.RiskPreference).HasColumnName("risk_preference").HasMaxLength(20);
            // default 3 (neutral) also fills existing rows when the column is added
            entity.Property(p => p.ImpatienceLevel).HasColumnName("impatience_level").HasDefaultValue(3).HasSentinel(0);
            entity.Property(p => p.CreatedAt).HasColumnName("created_at").HasDefaultValueSql("now()");
            entity.Property(p => p.UpdatedAt).HasColumnName("updated_at").HasDefaultValueSql("now()");
        });
    }
}
