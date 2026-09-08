# [P1][Security][Cache] Make semantic cache scope-safe and invalidate on corpus mutations

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

Semantic cache can leak stale or unauthorized information even when live retrieval is scoped. A cached answer created before deletion/supersession can resurrect data; a shared semantic cache can cross group boundaries.

## Current areas to inspect

- `core_backend/src/cache.py`
- `core_backend/test_cache_isolation.py`
- query flow in `core_backend/src/services.py`
- document add/update/supersede/erase logic
- cache/vector-store dependencies

## Required behavior / implementation

Cache identity must include at minimum:

```text
organization_id
canonical group scope
corpus/document-set version
index version
query representation
```

Include prompt/model version where answer semantics require it.

Introduce a monotonic corpus/document-set version at the correct isolation level. Increment after successful:
- document add/index
- update/supersede
- erasure
- visibility-changing ACL mutation

Recommended lookup:
exact normalized cache → semantic cache → full pipeline.

Semantic nearest-neighbor lookup itself must be partitioned by canonical scope.



## Required tests

- same query different org => no shared hit
- same org different group => no unauthorized hit
- superseded doc => old current answer not served
- erased doc => old answer not served
- index version change => stale hit bypassed
- group ordering canonicalization
- cached citation still resolves to visible version

## Acceptance criteria

- [ ] Cache partitions include org + canonical groups.
- [ ] Corpus/document-set version participates in lookup.
- [ ] Visibility-changing mutations advance corpus version.
- [ ] Erased/superseded content cannot reappear via stale cache.
- [ ] Cross-org/group + temporal/erasure tests exist.
- [ ] Metrics distinguish exact hit, semantic hit, miss.

## Non-goals

- Global destructive invalidation when versioned keys suffice.
- Personalized caching without user-scope design.

## Invariant

> **A cache hit never reveals evidence that a fresh retrieval under the same canonical scope would forbid.**
