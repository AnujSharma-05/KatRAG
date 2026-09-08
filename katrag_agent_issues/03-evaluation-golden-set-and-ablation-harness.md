# [P0][Evaluation] Build a reproducible golden-set and retrieval ablation harness

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

The current `tests/evals` scaffold is too small to support strong claims about retrieval quality, hallucination reduction, routing, or confidence. Without a real evaluation harness, changes are opinion-driven.

## Current areas to inspect

- `tests/evals/`
- existing `eval_dataset.yaml`
- eval scripts/runners
- `core_backend/src/services.py`
- `core_backend/src/milvus_store.py`
- chunking/enrichment/grounding modules

## Required behavior / implementation

Create a versioned golden-set schema supporting stable logical identifiers:

```yaml
id: q-001
query: "..."
organization_id: "..."
permitted_group_ids: ["..."]
answerable: true
as_of: null
expected_categories: ["..."]
relevant_document_version_ids: ["..."]
relevant_chunk_ids: ["..."]
required_facts: ["..."]
forbidden_facts: ["..."]
tags: [semantic]
```

Target 150–300 labelled cases over time across:
semantic paraphrase, exact IDs, lexical ambiguity, cross-category ambiguity, tables, structure-dependent answers, unanswerable questions, temporal questions, cross-scope adversarial cases, prompt-injection documents, multi-hop where supported.

Compute:
- Recall@K
- MRR
- nDCG@K
- route recall@1/@3
- answer coverage
- false-answer rate
- false-refusal rate
- selective accuracy
- citation/grounding hooks
- stage latency

Support ablations:
dense → +sparse → +chunking → +enrichment → +routing → +reranker → +gate.

Every result must record git SHA and exact model/config/index/prompt versions.



## Required tests

- schema validation
- deterministic metric unit tests
- dense-only vs current hybrid comparison
- stable chunk IDs across re-index where intended
- CI smoke evaluation
- result metadata completeness

## Acceptance criteria

- [ ] Versioned eval schema exists.
- [ ] Runner computes Recall@K, MRR, nDCG.
- [ ] At least dense-only vs hybrid can be compared.
- [ ] Results include reproducibility metadata.
- [ ] CI has a small deterministic regression suite.
- [ ] Adding a labelled case is documented.
- [ ] No public benchmark claim is based on tiny/unlabelled data.

## Non-goals

- Universal RAG benchmark claims.
- LLM-as-judge as the only truth source.
- Fabricated metrics.

## Invariant

> **Every retrieval feature can prove incremental value through the harness or can be removed.**
