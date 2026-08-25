# ADR-0001: Why Microservices

**Status:** Accepted
**Date:** 2026-08-25

## Context
The thesis report originally specified a 4-service split (Auth, User-Data, Portfolio, AI-Service) in Java only. Microservice literature cited in the report (loose coupling, independent scaling) motivates the architectural direction.

## Decision
Adopt 7 bounded-context services (Identity, Finance Profile, Financial IQ, Market Data, Notification, Edge Gateway, AI/RAG) instead of a monolith or the original 4-service split, to demonstrate real service-boundary design and support the dual-stack (Spring Boot / .NET) requirement from the target internship posting.

## Consequences
More operational complexity (7 deployables, inter-service contracts) but each service owns its data, can be developed/tested independently, and maps cleanly onto the two target languages for portfolio purposes.