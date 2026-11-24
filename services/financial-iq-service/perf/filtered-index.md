# Filtered index: `IX_financial_iq_results_low_segment`

**Problem.** Notification and the Ops panel (Faz 5/8) need "users whose current IQ is LOW, most recently calculated
first". Without an index SQL Server reads the whole `financial_iq_results` table and sorts it, every time.

**Solution.** An index that holds only the LOW rows, already ordered by `updated_at DESC`, with `user_id` and
`score` stored in it (no lookup into the table):

```sql
CREATE INDEX IX_financial_iq_results_low_segment
    ON financial_iq_results (updated_at DESC)
    INCLUDE (user_id, score)
    WHERE segment = N'LOW';
```

The query is `dbo.usp_GetLowSegmentResults @Take` (migration `AddLowSegmentFilteredIndex`).

## Measurement (22 Nov 2026)

Separate database `financial_iq_perf` (the dev database is not touched), 100,000 users seeded with
`seed-results.sql`: 20,000 LOW, 39,972 MEDIUM, 40,028 HIGH. Queries from `measure-low-segment.sql`.
**Logical reads** = 8 KB pages read; unlike time, it does not depend on the machine or on what is cached.

| | No index | Full index `(segment, updated_at DESC)` | **Filtered index** |
|---|---|---|---|
| Rows in the index | — | 100,000 | **20,000** |
| Index size | — | 994 pages (~7.8 MB) | **195 pages (~1.5 MB)** |
| Top 50 LOW, newest first | 6,626 reads, Clustered Index Scan + Sort | 4 reads | **2 reads**, ordered Index Scan, no Sort |
| Count LOW users | 6,626 reads | 197 reads | **179 reads** |
| Same query with a parameter `segment = @s` | 6,626 reads | 4 reads | **cannot be used** (error 8622 when forced) |
| Writes of MEDIUM/HIGH results | — | index updated too | **not touched** |

**Result.** For the LOW query the filtered index is as fast as a full index (2 vs 4 reads; 6,626 without any index,
about 3,300 times more) while being **5 times smaller**, and the 80 % of writes that are not LOW never maintain it.

## Two traps found while measuring

1. **The filter must be a literal.** With `WHERE segment = @s` the plan is cached and reused for `@s = 'HIGH'`
   too, so SQL Server may not use an index that only contains LOW rows: the query scans (6,626 reads), and forcing
   the index with a hint fails with error 8622. That is why `usp_GetLowSegmentResults` has `N'LOW'` written in it.
2. **`QUOTED_IDENTIFIER` must be ON.** Filtered indexes are only used when the session has `QUOTED_IDENTIFIER` (and
   `ANSI_NULLS` etc.) ON. `sqlcmd` starts with it OFF, so the same literal query scanned until `sqlcmd -I` was used.
   EF Core / SqlClient connections have it ON, and a stored procedure keeps the setting it was created with, so
   `usp_GetLowSegmentResults` uses the index even when called from a plain `sqlcmd`.

## Reproduce

```powershell
cd services\financial-iq-service\src\FinancialIQ.Api
$perf = "Server=localhost,1433;Database=financial_iq_perf;User Id=sa;Password=AInvest_Dev_Pw1;TrustServerCertificate=True"
dotnet ef database update AddResultVersionToGetLatest --connection $perf   # schema without the filtered index
cd ..\..\perf
docker cp seed-results.sql ainvest-sqlserver:/tmp/seed-results.sql
docker cp measure-low-segment.sql ainvest-sqlserver:/tmp/measure-low-segment.sql
docker exec ainvest-sqlserver /opt/mssql-tools18/bin/sqlcmd -S localhost -U sa -P AInvest_Dev_Pw1 -C -I -d financial_iq_perf -i /tmp/seed-results.sql
docker exec ainvest-sqlserver /opt/mssql-tools18/bin/sqlcmd -S localhost -U sa -P AInvest_Dev_Pw1 -C -I -d financial_iq_perf -i /tmp/measure-low-segment.sql   # stage 1: no index
cd ..\src\FinancialIQ.Api
dotnet ef database update AddLowSegmentFilteredIndex --connection $perf    # stage 2: filtered index
# run measure-low-segment.sql again; for the full-index column create IX_perf_full_segment in financial_iq_perf only
```
