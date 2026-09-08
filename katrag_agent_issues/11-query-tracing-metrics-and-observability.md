# [P2][Operability] Add stage-level tracing, structured metrics, and failure attribution

> **Primary reference:** `KatRAG_Perfection_Playbook_README.md`
>
> **Repository:** `AnujSharma-05/KatRAG`
>
> **Agent rule:** Inspect the current repository before editing. Paths/signatures may evolve. Treat the invariants and acceptance criteria in this issue as authoritative; implementation suggestions are guidance.
>
> **Read first**
> - `docs/architecture/categorag-engineering-bible.md`
> - `docs/architecture/KatRAG_System_Design.md`
> - `docs/architecture/KatRAG_Verdict_And_Issues.md`
> - root `README.md`
>
> **Global constraints**
> - Do not add frameworks/infrastructure/models unless required by acceptance criteria.
> - Do not weaken tenant isolation, temporal correctness, provenance, or observability.
> - Prefer typed contracts and deterministic tests over prompt-only behavior.
> - Every reliability/security claim must be backed by a test or reproducible benchmark.
> - Preserve compatibility where reasonable; document intentional breaking changes.
> - Never invent benchmark numbers.


## Problem

A wrong RAG answer is not diagnosable if the system only says “the LLM hallucinated.” Operators need to identify whether failure occurred in auth, cache, routing, retrieval, fusion, reranking, gate, generation, or grounding.

## Current areas to inspect

- `core_backend/test_query_tracing.py`
- `core_backend/src/services.py`
- Go gateway middleware
- worker/outbox logs
- Kubernetes manifests
- any existing metrics/tracing code

## Required behavior / implementation

Propagate one correlation/trace ID across gateway→Core and ingestion operations.

Create spans for:
`auth`, `scope_resolution`, `cache_lookup`, `query_embedding`, `category_route`, `dense_search`, `sparse_search`, `fusion`, `rerank`, `confidence_gate`, `generation`, `grounding`.

Record safe metadata:
trace ID, tenant IDs according to policy, model/config/index versions, candidate stable IDs, scores, duration, gate decision, citations, grounding/cache status.

Metrics:
- request rate/errors/p50/p95/p99
- stage latency
- cache hit types
- answer/hedge/refuse
- empty retrieval/fallback
- worker success/failure/lag/retry/DLQ
- security assertion failures

Replace ad hoc prints with structured logging where present. Do not log tokens/secrets/full confidential evidence by default.



## Required tests

- trace ID propagates Go→Python
- stage duration present
- secret/token not logged
- scope assertion emits security signal
- failed query identifies failed stage

## Acceptance criteria

- [ ] Structured stage tracing exists.
- [ ] Stage p50/p95 metrics can be produced.
- [ ] Worker/outbox/DLQ metrics use same observability approach.
- [ ] Auth secrets are not logged.
- [ ] A bad answer can be attributed to a pipeline stage.
- [ ] Investigation workflow is documented.

## Non-goals

- Building a custom observability vendor/platform.
- Logging every prompt/source indiscriminately.

## Invariant

> **Every externally visible bad answer can be attributed to a pipeline stage from trace signals.**
