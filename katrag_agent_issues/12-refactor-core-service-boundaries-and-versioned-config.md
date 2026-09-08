# [P2][Maintainability] Split core orchestration into testable stages and version retrieval configuration

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

`core_backend/src/services.py` owns too many responsibilities. That makes unit testing, ablation, security review, and reproducibility harder. Refactor only after critical behavior has tests; do not refactor for folder aesthetics.

## Current areas to inspect

- `core_backend/src/services.py`
- `milvus_store.py`
- `grounding.py`
- `chunking_engine.py`
- `enrichment_engine.py`
- `llm_service.py`
- tests importing service internals

## Required behavior / implementation

Move toward narrow domains such as:

```text
retrieval/{router,hybrid,fusion,reranker,confidence}
ingestion/{parser,chunker,enrichment,indexer}
generation/{synthesize,citations,grounding}
application/{query_service,ingest_service}
```

Exact names are flexible.

Introduce typed contracts such as:
`CanonicalScope`, `QueryContext`, `RetrievalCandidate`, `RerankedCandidate`, `GateDecision`, `CitationEvidence`.

Create a serializable retrieval configuration recording:
- embedding model
- chunker/enrichment version
- routing/fusion params
- reranker
- calibration
- prompt
- index version

Rules:
- no behavior change without tests;
- no DI framework unless necessary;
- datastore security filtering stays centralized;
- public API remains compatible where reasonable;
- refactor incrementally.



## Required tests

- existing tests remain green
- stages can be unit tested without full external stack where appropriate
- eval harness can instantiate multiple configs
- trace records exact config/version
- retrieval service cannot omit canonical scope

## Acceptance criteria

- [ ] Query orchestration reads as explicit stage composition.
- [ ] Retrieval boundaries are typed.
- [ ] Security filter ownership is obvious/centralized.
- [ ] Eval can toggle stages through config.
- [ ] Every trace/result identifies exact retrieval/model config.
- [ ] No unnecessary framework is introduced.

## Non-goals

- Wholesale rewrite.
- Aesthetic folder-only refactor.
- Dependency-injection framework adoption.

## Invariant

> **A developer can replace/disable one retrieval stage without changing unrelated ingestion or authorization logic.**
