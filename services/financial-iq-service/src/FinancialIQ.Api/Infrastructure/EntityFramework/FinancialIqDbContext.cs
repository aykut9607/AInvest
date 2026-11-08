using Microsoft.EntityFrameworkCore;
using FinancialIQ.Api.Domain.Entities;

namespace FinancialIQ.Api.Infrastructure.EntityFramework;

public class FinancialIqDbContext  : DbContext
{
    public FinancialIqDbContext(DbContextOptions<FinancialIqDbContext > options) : base(options) { }

    public DbSet<FinancialIqResult> FinancialIqResults { get; set; }
    public DbSet<IqHistory> IqHistories { get; set; }

    protected override void OnModelCreating(ModelBuilder modelBuilder)
    {
        modelBuilder.Entity<FinancialIqResult>(entity =>
        {
            entity.ToTable("financial_iq_results");

            entity.Property(p => p.Id).HasColumnName("id");
            // nvarchar(max) cannot be an index key, so the column gets a real size before the index below
            entity.Property(p => p.UserId).HasColumnName("user_id").HasMaxLength(FinancialIqResult.UserIdMaxLength);
            entity.Property(p => p.Score).HasColumnName("score");
            entity.Property(p => p.Segment).HasColumnName("segment").HasMaxLength(FinancialIqResult.SegmentMaxLength);
            entity.Property(p => p.FactorBreakdown).HasColumnName("factor_breakdown");
            entity.Property(p => p.CreatedAt).HasColumnName("created_at");
            entity.Property(p => p.UpdatedAt).HasColumnName("updated_at");

            // lookups by user become an index seek instead of a full scan, and the database itself
            // refuses a second row for the same user (last line of defence against a concurrent insert)
            entity.HasIndex(p => p.UserId)
                  .IsUnique()
                  .HasDatabaseName("UX_financial_iq_results_user_id");
        });

        modelBuilder.Entity<IqHistory>(entity =>
        {
            entity.ToTable("iq_history", t =>
                t.HasCheckConstraint("CK_iq_history_score", "[score] BETWEEN 0 AND 100"));

            // bigint identity: a narrow, ever-increasing clustered key, so new rows always go to the end
            // of the table instead of splitting pages like a random Guid would
            entity.HasKey(p => p.Id);
            entity.Property(p => p.Id).HasColumnName("id").UseIdentityColumn();
            entity.Property(p => p.UserId).HasColumnName("user_id").HasMaxLength(FinancialIqResult.UserIdMaxLength);
            entity.Property(p => p.Score).HasColumnName("score");
            entity.Property(p => p.Segment).HasColumnName("segment").HasMaxLength(FinancialIqResult.SegmentMaxLength);
            entity.Property(p => p.FactorBreakdown).HasColumnName("factor_breakdown");
            entity.Property(p => p.CalculatedAt)
                  .HasColumnName("calculated_at")
                  .HasColumnType("datetime2(3)")
                  .HasDefaultValueSql("SYSUTCDATETIME()");

            // covering index for the trend query: seek on the user, rows already ordered newest first,
            // and score/segment are stored in the index so the table itself is never touched (no key lookup)
            entity.HasIndex(p => new { p.UserId, p.CalculatedAt })
                  .IsDescending(false, true)
                  .IncludeProperties(p => new { p.Score, p.Segment })
                  .HasDatabaseName("IX_iq_history_user_id_calculated_at");
        });
    }
}