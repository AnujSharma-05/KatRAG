# [P1][Distributed Systems] Close the PostgreSQL ↔ Kafka dual-write gap with a transactional outbox

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

The intended flow `persist DB state → publish doc.uploaded` has a failure window: DB commit can succeed and the process can die before Kafka publish, leaving a permanently pending document.

## Current areas to inspect

- Go upload handlers under `live/backend/`
- Kafka/Redpanda producer code
- document/version DB models
- `core_backend/src/worker.py`
- event contracts

## Required behavior / implementation

Use transactional outbox.

Inside one DB transaction:

```text
INSERT document/document_version
INSERT outbox_event
COMMIT
```

Relay process:
- reads undispatched rows in bounded batches;
- supports concurrent relays safely (`FOR UPDATE SKIP LOCKED` or equivalent);
- publishes to Kafka;
- marks row published only after broker acknowledgment;
- retries with backoff;
- exposes pending count/oldest age/error metrics.

Suggested outbox fields:
`id`, aggregate type/id, event type, schema version, JSON payload, timestamps, attempts, last error, trace ID.

At-least-once publication is expected; worker idempotency handles duplicates.



## Required tests

- DB commit succeeds while broker unavailable
- relay publishes then crashes before marking published
- two relay replicas race
- malformed payload does not poison whole loop
- broker recovers and pending event drains

## Acceptance criteria

- [ ] Domain state + outbox event commit atomically.
- [ ] Durable ingestion no longer depends on direct commit-then-publish.
- [ ] Relay is retry-safe and concurrency-safe.
- [ ] Duplicate publication is tolerated.
- [ ] Pending/age/failure metrics exist.
- [ ] Integration test proves eventual publish after broker/process failure.

## Non-goals

- Exactly-once end-to-end semantics.
- Event-sourcing whole application.
- Replacing Kafka.

## Invariant

> **If durable document intent exists in Postgres, a corresponding ingestion event remains eventually publishable.**
