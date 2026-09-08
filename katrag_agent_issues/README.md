# KatRAG Agent-Facing GitHub Issue Pack

These files convert the human-facing `KatRAG_Perfection_Playbook_README.md` into implementation contracts for coding agents.

## Agent workflow

1. Read `00-EPIC-katrag-production-hardening.md`.
2. Read the Perfection Playbook.
3. Read current KatRAG architecture docs.
4. Inspect the current code before starting an issue.
5. Follow dependency order unless current code already satisfies a dependency.
6. Treat **invariants and acceptance criteria as authoritative**.
7. Add tests in the same PR as behavior.
8. Do not report an issue complete unless acceptance criteria are demonstrably met.

## Dependency map

```text
01 Auth/scope
  ↓
02 Retrieval isolation ──→ 04 Cache isolation
  │
  └──────────────→ 10 Temporal/erasure

03 Eval harness ──→ 07 Calibration
      ├──────────→ 08 Soft routing
      ├──────────→ 09 Citation/grounding
      └──────────→ 13 Performance

05 Transactional outbox
  ↓
06 Worker idempotency/DLQ
  ↓
14 Load/chaos

11 Observability supports all workstreams.
12 Refactor should follow tests, not precede them.
15 Public claims/demo comes after measurable evidence.
```

## Issue files
- [00-EPIC-katrag-production-hardening.md](00-EPIC-katrag-production-hardening.md) — EPIC: Turn KatRAG into a measurable, secure, production-oriented retrieval system
- [01-security-auth-and-scope-hardening.md](01-security-auth-and-scope-hardening.md) — [P0][Security] Replace development auth/scope scaffolding with deny-by-default identity and authorization
- [02-retrieval-datastore-tenant-group-isolation.md](02-retrieval-datastore-tenant-group-isolation.md) — [P0][Security][Retrieval] Enforce organization + group authorization in every retrieval path
- [03-evaluation-golden-set-and-ablation-harness.md](03-evaluation-golden-set-and-ablation-harness.md) — [P0][Evaluation] Build a reproducible golden-set and retrieval ablation harness
- [04-semantic-cache-isolation-and-corpus-versioning.md](04-semantic-cache-isolation-and-corpus-versioning.md) — [P1][Security][Cache] Make semantic cache scope-safe and invalidate on corpus mutations
- [05-transactional-outbox-for-ingestion-events.md](05-transactional-outbox-for-ingestion-events.md) — [P1][Distributed Systems] Close the PostgreSQL ↔ Kafka dual-write gap with a transactional outbox
- [06-worker-idempotency-state-machine-and-dlq.md](06-worker-idempotency-state-machine-and-dlq.md) — [P1][Reliability] Make ingestion worker idempotent, stateful, retry-safe, and DLQ-aware
- [07-confidence-calibration-and-selective-prediction.md](07-confidence-calibration-and-selective-prediction.md) — [P1][ML Quality] Replace heuristic sigmoid confidence with fitted calibration and selective-prediction metrics
- [08-soft-category-routing-with-global-fallback.md](08-soft-category-routing-with-global-fallback.md) — [P1][Retrieval] Make categorical routing a soft prior with measurable global recall protection
- [09-citation-provenance-and-claim-grounding.md](09-citation-provenance-and-claim-grounding.md) — [P1][Trust] Bind citations to exact source/version/span and validate grounding per factual claim
- [10-temporal-versioning-consistency-and-erasure.md](10-temporal-versioning-consistency-and-erasure.md) — [P1][Data Model] Make temporal versioning transactionally correct and define explicit erasure semantics
- [11-query-tracing-metrics-and-observability.md](11-query-tracing-metrics-and-observability.md) — [P2][Operability] Add stage-level tracing, structured metrics, and failure attribution
- [12-refactor-core-service-boundaries-and-versioned-config.md](12-refactor-core-service-boundaries-and-versioned-config.md) — [P2][Maintainability] Split core orchestration into testable stages and version retrieval configuration
- [13-reranker-performance-and-query-latency-budget.md](13-reranker-performance-and-query-latency-budget.md) — [P2][Performance] Measure and optimize reranker/query latency under an explicit budget
- [14-load-chaos-and-recovery-test-suite.md](14-load-chaos-and-recovery-test-suite.md) — [P2][Reliability][Scale] Add load, crash, replay, and recovery tests that prove infrastructure value
- [15-public-claims-benchmarks-and-technical-demo.md](15-public-claims-benchmarks-and-technical-demo.md) — [P3][Documentation][Interview] Align public claims with measured evidence and build a technical demo

## Recommended PR description format

```text
Problem:
Invariant:
Implementation:
Tests:
Migration/compatibility:
Security impact:
Observability:
Benchmark/evaluation impact:
Known remaining gaps:
```

## Completion discipline

The playbook explains *why*. These issues define *what must be true after implementation*.

Agents should not optimize for matching prose literally. They should satisfy the issue invariant and acceptance criteria against the current repository.
