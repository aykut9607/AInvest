# ADR-0003: Why No Go

**Status:** Accepted
**Date:** 2026-08-25

## Context
An earlier prototype (crypto-wallet-service) was started in Go for a Market-Data-style service, then abandoned in favor of a broader Market Data Service scope.

## Decision
Remove Go entirely from the stack. Market Data Service is implemented in Spring Boot instead. Infrastructure images (Kafka, Redis, etc.) that happen to be written in Go are unrelated — they are used as pre-built containers only; no Go code is authored or maintained in this project.

## Consequences
Keeps the codebase to exactly three authored languages (Java, C#, Python), matching the 3 Spring / 3 .NET / 1 Python balance goal. The Go prototype's auth-related files (unrelated to wallet logic) were deleted on 2026-08-25; Identity Service (Spring) supersedes them.