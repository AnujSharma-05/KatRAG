# [P1][Data Model] Make temporal versioning transactionally correct and define explicit erasure semantics

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

Temporal retrieval is a strong differentiator but creates consistency/privacy requirements. Supersession must preserve history; erasure must make data inaccessible even through historical retrieval/cache.

## Current areas to inspect

- `core_backend/src/models.py`
- `core_backend/src/services.py`
- `core_backend/src/milvus_store.py`
- `core_backend/test_temporal_retrieval.py`
- Go upload/update/delete routes
- cache invalidation
- `as_of` handling

## Required behavior / implementation

Define explicit validity semantics:
- `valid_from` inclusive
- `valid_to` exclusive/null
- at most one active non-erased version per logical document at a time

Create new version and close old version atomically. Use DB constraints where practical to prevent overlapping current windows.

Historical retrieval:
```text
valid_from <= as_of
AND (valid_to IS NULL OR as_of < valid_to)
```
plus authorization scope.

Define `erase` separately from `supersede`.

Erasure must:
1. mark relational state erased;
2. remove/invalidate vectors;
3. advance corpus/cache version;
4. prevent historical resurrection;
5. define object-store cleanup;
6. retain only safe audit metadata.



## Required tests

- v1 then v2 supersession
- exact boundary timestamp
- current sees v2 only
- historical sees v1
- concurrent update cannot create two current versions
- erased v1 unavailable even with historical as_of
- stale cache cannot resurrect erased version
- group auth still applies historically

## Acceptance criteria

- [ ] Supersession is transactionally consistent.
- [ ] Temporal boundary semantics are documented/tested.
- [ ] Concurrent updates cannot create two current versions.
- [ ] Erasure is distinct from supersession.
- [ ] Erased content is unreachable from current, historical, vector and cache paths.
- [ ] Corpus/cache version updates on supersede/erase.

## Non-goals

- Regulatory certification.
- “Never forgets” semantics that conflict with deletion obligations.

## Invariant

> **Superseded history remains queryable by time; erased data does not.**
