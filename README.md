# AInvest

A microservice-based personal finance platform (graduation project, Istanbul University–Cerrahpaşa).
A user enters their financial profile, a rule-based **Financial IQ** score (0–100) is calculated with a
per-factor breakdown, and an AI layer explains the score in plain language.

The backend is a set of independent **Spring Boot** and **.NET** services behind a **YARP API gateway**,
each owning its own database.

## Architecture

```
                            ┌─► Identity (Spring Boot, :8081) ── PostgreSQL identity_db
                            │      register / login / refresh, issues JWT (HS512, iss/aud/sub)
Web (React) ─┐              │
             ├─► Edge Gateway (YARP, :5000) ─┼─► Finance Profile (.NET, :5293) ── PostgreSQL finance_db
Mobile (RN) ─┘   JWT validation, BOLA check, │      │ REST + Polly (timeout, retry, circuit breaker)
                 login rate limit, CORS,     │      ▼
                 correlation id              ├─► Financial IQ (.NET, :5109) ── SQL Server financial_iq_db
                                             │      stored procedures, history table, trend function
                                             └─► AI Explanation (FastAPI, :8001)

Market Data (Spring Boot, :8082) ── external FX rates, protected with Resilience4j
```

Rule: **a service never connects to another service's database**; it calls that service's API.
Architecture decisions are recorded in [`docs/adr/`](docs/adr).

## Services

| Service | Stack | Responsibility |
|---|---|---|
| [Edge Gateway](services/edge-gateway) | .NET 10, YARP | Single entry point: routing, JWT validation, authorization, rate limiting, CORS |
| [Identity](services/identity-service) | Java 21, Spring Boot 3.5, PostgreSQL | Registration, login, refresh-token rotation, JWT issuing, security-event logging |
| [Finance Profile](services/finance-profile-service) | .NET 10, EF Core, PostgreSQL | User financial profile CRUD; asks Financial IQ to score it |
| [Financial IQ](services/financial-iq-service) | .NET 10, EF Core, SQL Server, T-SQL | 6-factor deterministic scoring, latest result, score history and trend |
| [Market Data](services/market-data-service) | Java 21, Spring Boot 3.5, Resilience4j | FX rates from an external provider (minimal skeleton) |
| [AI Explanation](services/ai-explanation-service) | Python, FastAPI | Turns the score into a plain-language explanation (skeleton; LLM/RAG in progress) |
| [Web](apps/web-react) | React, TypeScript, Vite | Profile form, score and explanation |
| [Mobile](apps/mobile) | React Native (Expo) | Login, profile, score ring, factor breakdown, inconsistency card |

## Where to find what

| Topic | Implementation |
|---|---|
| **API gateway (YARP)** | Routes and clusters in [`appsettings.json`](services/edge-gateway/src/EdgeGateway.Api/appsettings.json); pipeline in [`Program.cs`](services/edge-gateway/src/EdgeGateway.Api/Program.cs) |
| **JWT at the edge** | Signature (HS512 only), issuer, audience and lifetime validated in the gateway; the token is issued by [`JwtService.java`](services/identity-service/src/main/java/com/ainvest/identity/config/JwtService.java) |
| **Broken object level authorization (BOLA)** | `sameUser` policy in the gateway: the `{userId}` in the URL must equal the token's `sub`, otherwise `403`. A client-sent `X-User-Id` is removed and rewritten from the token |
| **Rate limiting** | `POST /auth/login`: 5 requests per minute per IP, then `429` with `Retry-After` |
| **Correlation id** | [`CorrelationIdMiddleware.cs`](services/edge-gateway/src/EdgeGateway.Api/Middleware/CorrelationIdMiddleware.cs): generated if missing, unsafe values replaced, forwarded to every service |
| **Polly (.NET resilience)** | [`FinancialIqResilience.cs`](services/finance-profile-service/src/FinanceProfile.Api/Infrastructure/External/FinancialIqResilience.cs): per-attempt and total timeout, retry with exponential backoff and jitter, circuit breaker on Finance → IQ calls |
| **Resilience4j (Spring resilience)** | [`FxRateClient.java`](services/market-data-service/src/main/java/com/ainvest/marketdata/infrastructure/client/FxRateClient.java) + [`application.properties`](services/market-data-service/src/main/resources/application.properties): timeouts, `@Retry` (5xx and network errors only), `@CircuitBreaker`, fallback to `503`; breaker state in `/actuator/health` |
| **T-SQL stored procedures** | [`usp_SaveIqResult`](services/financial-iq-service/src/FinancialIQ.Api/Migrations/20261108201823_AddSaveIqResultProcedure.cs): `MERGE ... WITH (HOLDLOCK)` upsert, `OUTPUT INTO`, latest result + history row in one transaction, `TRY/CATCH/THROW`. [`usp_GetLatestIqResult`](services/financial-iq-service/src/FinancialIQ.Api/Migrations/20261108234401_AddGetLatestIqResultProcedure.cs): read side |
| **CTE + window functions** | [`fn_IqTrend`](services/financial-iq-service/src/FinancialIQ.Api/Migrations/20261108203041_AddIqTrendFunction.cs): inline table-valued function with a CTE, `LAG` (score change), `AVG ... OVER (ROWS BETWEEN 2 PRECEDING AND CURRENT ROW)` (moving average), `ROW_NUMBER` (last N) |
| **Indexing** | Unique index on `user_id`; covering index `(user_id, calculated_at DESC) INCLUDE (score, segment)` on `iq_history` ([migrations](services/financial-iq-service/src/FinancialIQ.Api/Migrations), [`FinancialIqDbContext.cs`](services/financial-iq-service/src/FinancialIQ.Api/Infrastructure/EntityFramework/FinancialIqDbContext.cs)). Measured: Clustered Index Scan → Index Seek |
| **CQRS-lite** | Financial IQ splits writes ([`FinancialIqCommandManager`](services/financial-iq-service/src/FinancialIQ.Api/Application/Concrete/FinancialIqCommandManager.cs)) from reads ([`FinancialIqQueryManager`](services/financial-iq-service/src/FinancialIQ.Api/Application/Concrete/FinancialIqQueryManager.cs)); the read side returns DTOs straight from SQL Server. Same database for both ("lite") |
| **Layered architecture, generic repository, Result pattern** | .NET services: `Controllers` → `Application` (managers, `Result`/`DataResult`) → `Infrastructure` (`EfEntityRepositoryBase<TEntity, TContext>`) |
| **Security-event logging** | [`SecurityEventLogger.java`](services/identity-service/src/main/java/com/ainvest/identity/logging/SecurityEventLogger.java): login / registration / refresh success and failure with a reason, as ECS JSON (`event.action`, `event.outcome`, masked e-mail, client IP, correlation id). Passwords, tokens and full e-mails are never logged |
| **Scoring engine** | 6 weighted factors (cash reserve, debt-to-income, savings rate, expense ratio, risk alignment, impatience) with warnings and a stated-vs-actual risk inconsistency flag |

## Running locally

Requirements: Docker Desktop, .NET SDK 10, JDK 21, Node.js 22+, Python 3.13.

```powershell
# databases only (PostgreSQL + SQL Server); dev passwords are in docker-compose.yml
docker compose up -d postgres sqlserver

# Financial IQ (connection string via user-secrets, then apply migrations)
cd services/financial-iq-service/src/FinancialIQ.Api
dotnet user-secrets set "ConnectionStrings:FinancialIqDb" "<SQL Server connection string>"
dotnet ef database update
dotnet run --launch-profile http

# Finance Profile: same pattern with ConnectionStrings:FinanceDb (PostgreSQL)
# Identity:        cd services/identity-service;  .\mvnw.cmd spring-boot:run
# Gateway:         set Jwt:Secret (user-secrets) to the same value as Identity's JWT_SECRET, then dotnet run
# Market Data:     cd services/market-data-service; .\mvnw.cmd spring-boot:run
```

Secrets are never committed: .NET uses user-secrets, Spring uses environment variables.
Ready-made requests are in the `.http` files next to each service (e.g. [`EdgeGateway.Api.http`](services/edge-gateway/src/EdgeGateway.Api/EdgeGateway.Api.http)).

## Tests

| Project | Command | Tests |
|---|---|---|
| .NET (Gateway, Finance Profile, Financial IQ) | `dotnet test AInvest.slnx` | 95 (xUnit) |
| Identity | `cd services/identity-service; .\mvnw.cmd test` | 29 (JUnit 5, Mockito) |
| Market Data | `cd services/market-data-service; .\mvnw.cmd test` | 7 (against a local fake provider) |

Gateway tests run the real pipeline against a fake downstream (routing, 401/403/404, spoofed headers,
rate limit, CORS). Resilience tests script failures (503 → 503 → 200, slow responses, repeated 500s)
and assert how many calls actually reached the dependency.

## Roadmap

- Event-driven flow with Kafka (outbox, saga, idempotent consumers) between Finance Profile, Financial IQ and AI
- AI/RAG service with tool-calling (developed by a teammate)
- Market Data snapshots in Couchbase, notifications
- Dockerfiles, CI, and observability (OpenTelemetry, Grafana)
