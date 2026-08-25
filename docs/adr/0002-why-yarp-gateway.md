# ADR-0002: Why YARP Gateway (not Spring Cloud Gateway / Ocelot)

**Status:** Accepted
**Date:** 2026-08-25

## Context
A single entry point is needed for JWT validation, routing, and rate limiting across 7 services split between Spring Boot and .NET.

## Decision
Use YARP (.NET reverse proxy) as the Edge Gateway rather than Spring Cloud Gateway. This keeps the Gateway in the .NET column (balancing the 3 Spring / 3 .NET split) and YARP is config-driven, actively maintained by Microsoft, and integrates directly with ASP.NET Core middleware for JWT auth.

## Consequences
Ocelot was considered and rejected as less actively maintained than YARP. Gateway ownership requires .NET familiarity.