-- Measures the "LOW users, most recent first" query in financial_iq_perf: plan shape + logical reads
-- (8 KB pages read from memory; the number that does not depend on the machine or the cache, unlike time).
-- Run the same file at every stage (no index / full index / filtered index) and compare the output.
-- Run: sqlcmd -S localhost -U sa -C -d financial_iq_perf -i measure-low-segment.sql
SET NOCOUNT ON;
IF DB_NAME() <> N'financial_iq_perf'
    THROW 50000, 'Run this only in financial_iq_perf.', 1;
GO

PRINT '=== Indexes on financial_iq_results: rows and size (8 KB pages)';
SELECT i.name AS index_name, i.filter_definition, ps.row_count, ps.used_page_count
FROM sys.indexes AS i
JOIN sys.dm_db_partition_stats AS ps ON ps.object_id = i.object_id AND ps.index_id = i.index_id
WHERE i.object_id = OBJECT_ID(N'dbo.financial_iq_results')
ORDER BY i.index_id;
GO

PRINT '=== Q1 plan: literal filter (what usp_GetLowSegmentResults runs)';
GO
SET SHOWPLAN_TEXT ON;
GO
SELECT TOP (50) user_id, score, updated_at FROM dbo.financial_iq_results WHERE segment = N'LOW' ORDER BY updated_at DESC;
GO
SET SHOWPLAN_TEXT OFF;
GO
PRINT '=== Q1 reads';
SET STATISTICS IO ON;
SELECT TOP (50) user_id, score, updated_at INTO #q1 FROM dbo.financial_iq_results WHERE segment = N'LOW' ORDER BY updated_at DESC;
SET STATISTICS IO OFF;
DROP TABLE #q1;
GO

PRINT '=== Q2 plan: same query with a parameter (@s = N''LOW'')';
GO
SET SHOWPLAN_TEXT ON;
GO
EXEC sp_executesql N'SELECT TOP (50) user_id, score, updated_at FROM dbo.financial_iq_results WHERE segment = @s ORDER BY updated_at DESC',
                   N'@s nvarchar(10)', @s = N'LOW';
GO
SET SHOWPLAN_TEXT OFF;
GO
PRINT '=== Q2 reads';
SET STATISTICS IO ON;
CREATE TABLE #q2 (user_id nvarchar(100), score int, updated_at datetime2);
INSERT INTO #q2
EXEC sp_executesql N'SELECT TOP (50) user_id, score, updated_at FROM dbo.financial_iq_results WHERE segment = @s ORDER BY updated_at DESC',
                   N'@s nvarchar(10)', @s = N'LOW';
SET STATISTICS IO OFF;
DROP TABLE #q2;
GO
