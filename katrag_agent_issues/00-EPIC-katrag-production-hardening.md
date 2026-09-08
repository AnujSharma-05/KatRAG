# EPIC: Turn KatRAG into a measurable, secure, production-oriented retrieval system

> Primary reference: `KatRAG_Perfection_Playbook_README.md`

## Goal

Do **not** add features for resume value. Make existing KatRAG claims defensible through correctness, security, evaluation, durability, observability, and reproducibility.

A component gets to exist only if it solves a concrete failure mode and its value is measured or tested.

## Dependency order

### P0 — foundations
1. `01-security-auth-and-scope-hardening.md`
2. `02-retrieval-datastore-tenant-group-isolation.md`
3. `03-evaluation-golden-set-and-ablation-harness.md`

### P1 — correctness/reliability
4. `04-semantic-cache-isolation-and-corpus-versioning.md`
5. `05-transactional-outbox-for-ingestion-events.md`
6. `06-worker-idempotency-state-machine-and-dlq.md`
7. `07-confidence-calibration-and-selective-prediction.md`
8. `08-soft-category-routing-with-global-fallback.md`
9. `09-citation-provenance-and-claim-grounding.md`
10. `10-temporal-versioning-consistency-and-erasure.md`

### P2 — operability/performance
11. `11-query-tracing-metrics-and-observability.md`
12. `12-refactor-core-service-boundaries-and-versioned-config.md`
13. `13-reranker-performance-and-query-latency-budget.md`
14. `14-load-chaos-and-recovery-test-suite.md`

### P3 — public presentation
15. `15-public-claims-benchmarks-and-technical-demo.md`

## Epic definition of done

A skeptical technical reviewer can determine:

- exactly which failure mode each stage solves;
- whether org/group A can ever retrieve/cache B;
- whether ingestion survives worker/process failure;
- why a bad answer occurred;
- whether current/historical/erased document state is correct;
- whether hybrid/routing/reranking improve labelled metrics;
- whether refusal improves false-answer rate without unacceptable false refusals;
- whether citations resolve to exact authorized evidence;
- whether performance claims are reproducible;
- whether README claims match tested behavior.
