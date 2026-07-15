using Microsoft.EntityFrameworkCore;
using FinancialIQ.Api.Domain.Entities;

namespace FinancialIQ.Api.Infrastructure.EntityFramework;

public class FinancialIqDbContext  : DbContext
{
    public FinancialIqDbContext(DbContextOptions<FinancialIqDbContext > options) : base(options) { }

    public DbSet<FinancialIqResult> FinancialIqResults { get; set; }

    protected override void OnModelCreating(ModelBuilder modelBuilder)
    {
        modelBuilder.Entity<FinancialIqResult>(entity =>
        {
            entity.ToTable("financial_iq_results");

            entity.Property(p => p.Id).HasColumnName("id");
            entity.Property(p => p.UserId).HasColumnName("user_id");
            entity.Property(p => p.Score).HasColumnName("score");
            entity.Property(p => p.Segment).HasColumnName("segment");
            entity.Property(p => p.CreatedAt).HasColumnName("created_at");
            entity.Property(p => p.UpdatedAt).HasColumnName("updated_at");
        });
    }
}