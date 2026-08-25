# ADR-0005: Why Couchbase (not MongoDB)

**Status:** Accepted
**Date:** 2026-08-25

## Context
Market Data ingests variable-shape external API payloads (prices, rates, news) that do not fit a fixed relational schema well and benefit from TTL-based auto-expiry. AI/RAG separately needs a document store for chat history.

## Decision
Use Couchbase over MongoDB. N1QL provides SQL-like query syntax, and built-in TTL plus sub-document updates fit the market-snapshot use case directly.

## Consequences
A less common choice than MongoDB in most tutorials and job postings, but demonstrates comfort with a schema-flexible store beyond the default choice, and keeps a consistent SQL-like mental model across the polyglot-persistence layer (Postgres, SQL Server, Couchbase).