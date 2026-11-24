-- Seeds 100,000 users into dbo.financial_iq_results of the PERF database (financial_iq_perf), never the dev one.
-- About 1 in 5 rows is LOW (score 0-40), the rest MEDIUM/HIGH; updated_at spread over the last year.
-- Set-based: one INSERT ... SELECT over a generated number list, no loop (a WHILE loop would be 100,000 statements).
-- Run: sqlcmd -S localhost -U sa -C -d financial_iq_perf -i seed-results.sql
SET NOCOUNT ON;

IF DB_NAME() <> N'financial_iq_perf'
    THROW 50000, 'Run this only in financial_iq_perf.', 1;

-- sys.all_objects has ~2,000 rows; joined with itself it gives millions, TOP keeps the first 100,000
WITH numbers AS (
    SELECT TOP (100000) ROW_NUMBER() OVER (ORDER BY (SELECT NULL)) AS i
    FROM sys.all_objects AS a
    CROSS JOIN sys.all_objects AS b
)
INSERT INTO dbo.financial_iq_results (id, user_id, score, segment, factor_breakdown, created_at, updated_at)
SELECT NEWID(),
       CONCAT(N'perf-user-', n.i),
       s.score,
       CASE WHEN s.score <= 40 THEN N'LOW' WHEN s.score <= 70 THEN N'MEDIUM' ELSE N'HIGH' END,
       -- a realistic v2 breakdown, so the rows are as wide as real ones (the table scan cost depends on it)
       N'{"version":"v2","factors":{"CashReserveMonths":15,"DebtToIncomeRatio":8,"SavingsRate":15,"ExpenseRatio":9,"Impatience":5},"warnings":["Low cash reserve","High debt burden"],"appliedRule":null}',
       s.updated_at,
       s.updated_at
FROM numbers AS n
CROSS APPLY (
    SELECT CASE WHEN n.i % 5 = 0 THEN ABS(CHECKSUM(NEWID())) % 41         -- LOW
                ELSE 41 + ABS(CHECKSUM(NEWID())) % 60 END AS score,       -- MEDIUM / HIGH
           DATEADD(MINUTE, -(ABS(CHECKSUM(NEWID())) % 525600), SYSUTCDATETIME()) AS updated_at
) AS s;

SELECT segment, COUNT(*) AS users
FROM dbo.financial_iq_results
GROUP BY segment
ORDER BY segment;
