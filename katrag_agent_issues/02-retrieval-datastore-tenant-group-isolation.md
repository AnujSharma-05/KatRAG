# [P0][Security][Retrieval] Enforce organization + group authorization in every retrieval path

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

Multi-tenancy is secure only when unauthorized evidence is excluded **inside datastore retrieval** before ranking/generation. Prompt restrictions and late filtering are not security boundaries.

Audit the current Milvus path because the architecture claims org→group isolation while the visible hot path primarily demonstrates organization/version filtering.

## Current areas to inspect

- `core_backend/src/milvus_store.py`
- `core_backend/src/services.py`
- `core_backend/src/cache.py`
- `core_backend/src/schemas.py`
- `core_backend/src/models.py`
- temporal and cache isolation tests
- every direct Milvus `search`, `hybrid_search`, and `query` call

## Required behavior / implementation

Each indexed record must carry enough authorization metadata to enforce:

```text
organization_id == scope.organization_id
AND group_id IN scope.permitted_group_ids
```

plus temporal/version predicates.

Create one shared scope filter builder, e.g.:

```python
build_scope_filter(scope, as_of, version_policy) -> str
```

Apply it identically to:
- dense retrieval
- sparse/BM25 retrieval
- hybrid search
- category retrieval when scoped
- temporal retrieval
- fallback/global retrieval
- debug retrieval endpoints

Add defense-in-depth post-retrieval assertions. On mismatch:
- abort;
- never pass chunk to reranker/LLM;
- emit security log/metric with trace ID.



## Required tests

Use adversarially similar content across:
- Org A / HR
- Org A / ENG
- Org B / HR

Test:
- A/HR cannot retrieve A/ENG
- Org A cannot retrieve Org B
- dense and sparse both honor scope
- category/global fallback honors scope
- temporal retrieval honors scope
- direct helper honors scope
- injected invalid result triggers post-retrieval assertion

## Acceptance criteria

- [ ] Group-level metadata (or equivalent secure ACL representation) exists in indexed records.
- [ ] One shared authorization filter builder is used by all Milvus retrieval arms.
- [ ] No authenticated production path silently performs unscoped global search.
- [ ] Dense/sparse/hybrid authorization semantics match.
- [ ] Runtime scope assertions exist.
- [ ] Regression tests fail if group filtering is removed.

## Non-goals

- Arbitrary per-document ACL engine unless already required.
- Prompt-based isolation.
- Cross-org sharing model.

## Invariant

> **The LLM is structurally incapable of seeing unauthorized chunks because they are excluded before ranking.**
