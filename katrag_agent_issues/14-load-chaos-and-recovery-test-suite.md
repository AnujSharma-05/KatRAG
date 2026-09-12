# [P2][Reliability][Scale] Add load, crash, replay, and recovery tests that prove infrastructure value

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

Kafka, Kubernetes, Milvus, and multi-service architecture are only impressive if they demonstrate real recovery/scaling properties. Architecture diagrams are not evidence.

## Current areas to inspect

- `infra/k8s/base/`
- gateway/Core/worker deployments
- Kafka/Redpanda config
- probes/resources/autoscaling/NetworkPolicy
- existing e2e tests
- outbox/worker metrics

## Required behavior / implementation

Create a documented scale ladder:
- L0 ~5k chunks, one org, one worker
- L1 ~50k chunks, multiple org/groups, ~50 VUs where environment allows
- L2 scripts capable of 500k–1M synthetic chunks

Do not claim levels not actually run.

Crash tests:
- kill worker during parse;
- kill during vector indexing;
- restart;
- verify eventual completion + no duplicate active chunks;
- broker outage → outbox accumulates → broker recovers → backlog drains;
- query/Core restart behaves correctly with readiness.

Capture QPS, p50/p95/p99, error rate, Milvus/reranker/DB latency, Kafka lag, throughput, CPU/memory.

Validate K8s readiness/liveness, resources, graceful shutdown, internal NetworkPolicy, and meaningful autoscaling signal.



## Required tests

- worker kill during parsing
- worker kill during indexing
- broker outage/recovery
- readiness during Core restart
- scope security under concurrent load
- no duplicate chunks after recovery

## Acceptance criteria

- [ ] Reproducible load generator exists.
- [ ] Crash/restart ingest test proves no lost job/duplicate final chunks.
- [ ] Broker recovery test exists.
- [ ] K8s probes/resources are meaningful.
- [ ] Results distinguish tested from designed-for.
- [ ] No scale claim exceeds executed evidence.

## Non-goals

- Inflating infrastructure complexity.
- Claiming cloud scale from local tests.

## Invariant

> **Every infrastructure component corresponds to a demonstrated recovery or scaling property.**
