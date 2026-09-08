# [P1][Retrieval] Make categorical routing a soft prior with measurable global recall protection

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

A wrong hard category route can destroy recall before retrieval/reranking can recover. Category routing should improve ranking efficiency/precision without making relevant authorized evidence impossible to retrieve.

## Current areas to inspect

- category logic in `core_backend/src/services.py`
- `core_backend/src/llm_service.py`
- category vectors in `core_backend/src/milvus_store.py`
- category models/summaries
- routing eval cases

## Required behavior / implementation

Return top-k category candidates with scores/uncertainty instead of a single irreversible class.

Use:

```text
routed retrieval over top categories
+
global scoped fallback retrieval
→ union/dedupe
→ fusion/rerank
```

Authorization applies identically to every branch.

Trace route candidates/scores/fallback reason.

Measure:
- route recall@1/@3
- end-to-end Recall@K with/without routing
- latency delta
- fallback frequency

If routing does not provide measurable value on target corpus, support disabling/removing it.



## Required tests

- incorrect top-1 route but correct evidence recovered globally
- low-confidence route uses fallback
- fallback remains org/group scoped
- duplicate candidates dedupe correctly
- no categories => global retrieval
- router model/service failure degrades safely

## Acceptance criteria

- [ ] Routing is not an irreversible single-category filter.
- [ ] Top-k route signals are observable.
- [ ] Global fallback is scope-safe.
- [ ] Eval compares routed vs non-routed pipeline.
- [ ] Router failure does not become total retrieval failure.
- [ ] Docs call routing a relevance prior, not a security boundary.

## Non-goals

- Complex learned router before baseline measurement.
- Mandatory LLM routing when embeddings/centroids suffice.

## Invariant

> **A router error may hurt ranking, but cannot make otherwise retrievable authorized evidence structurally unreachable.**
