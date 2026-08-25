# ADR-0006: Why Kafka (not RabbitMQ)

**Status:** Accepted
**Date:** 2026-08-25

## Context
An asynchronous backbone is needed for the transactional outbox pattern, the IQ-to-AI saga chain, and fan-out of market/sentiment events to multiple consumers.

## Decision
Use Kafka over RabbitMQ. Log-based retention lets new consumers replay history, which is useful for the saga_instances table and observability dashboards. Partitioning by userId gives the required per-user event ordering directly.

## Consequences
A heavier operational footprint than RabbitMQ for a project of this size, but matches what enterprise job postings actually expect and supports the replay/audit story the saga design depends on.