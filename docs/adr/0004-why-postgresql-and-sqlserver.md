# ADR-0004: Why Both PostgreSQL and SQL Server

**Status:** Accepted
**Date:** 2026-08-25

## Context
T-SQL proficiency (window functions, CTEs, stored procedures) is a project learning goal. The original architecture used PostgreSQL exclusively.

## Decision
Financial IQ Service uses SQL Server with T-SQL-specific features (window functions, recursive CTEs, stored procedures, execution-plan tuning). Identity, Finance Profile, and Notification keep PostgreSQL.

## Consequences
Accepts the operational cost of running two RDBMS engines locally. This is a deliberate learning- and job-requirement-driven tradeoff, not a general "best practice" recommendation, and is documented as such. Financial IQ's existing EF Core code migrates database providers (Npgsql to SqlServer); the scoring business logic under Rules/ is LINQ-based and provider-agnostic, so it is unaffected.