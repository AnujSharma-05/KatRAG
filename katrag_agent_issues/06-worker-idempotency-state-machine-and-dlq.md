# [P1][Reliability] Make ingestion worker idempotent, stateful, retry-safe, and DLQ-aware

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

At-least-once delivery means duplicates, crash mid-stage, poison messages, partial Milvus writes, and stale events are normal conditions. The worker must converge rather than duplicate/corrupt state.

## Current areas to inspect

- `core_backend/src/worker.py`
- ingestion functions in `core_backend/src/services.py`
- chunking/enrichment modules
- `core_backend/src/milvus_store.py`
- status/version models
- event producer contracts

## Required behavior / implementation

Version the event envelope with stable `event_id`, `schema_version`, `document_version_id`, `idempotency_key`, org, trace ID, timestamp.

Use an explicit state machine such as:
`pending → parsing → chunking → enriching → embedding → indexing → indexed`, with `failed/superseded/erased` terminal/special states.

Validate legal transitions.

Use deterministic chunk/vector identity derived from stable inputs, e.g. document version + logical chunk index + chunker version.

Classify transient vs permanent failures. Transient failures retry with bounded backoff. Permanent failures reach DLQ with enough metadata to debug/replay.

Define partial-index recovery through deterministic upsert or version-scoped reconciliation.



## Required tests

- duplicate event delivered twice
- kill worker during parsing
- kill during vector indexing
- partial insert then retry
- stale event after newer version
- poison event reaches DLQ
- DLQ record can be replayed/debugged

## Acceptance criteria

- [ ] Consumer is explicitly idempotent.
- [ ] Stable event/chunk identities exist.
- [ ] Legal state transitions are enforced.
- [ ] Duplicate events converge to one final indexed version.
- [ ] Partial writes do not create duplicate active chunks.
- [ ] Permanent failures reach DLQ.
- [ ] Retry/DLQ metrics exist.
- [ ] Crash/restart integration test passes.

## Non-goals

- Exactly-once broker semantics.
- Infinite retries.
- Hiding failed jobs.

## Invariant

> **Replaying the same ingestion event N times converges to one correct indexed document version.**
