# [P1][Trust] Bind citations to exact source/version/span and validate grounding per factual claim

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

A syntactically valid citation may not support a claim. Whole-answer-vs-context grounding can hide unsupported subclaims. KatRAG needs a traceable provenance chain from claim to exact authorized source version/span.

## Current areas to inspect

- `core_backend/src/grounding.py`
- `core_backend/test_grounding.py`
- `core_backend/src/llm_service.py`
- `core_backend/src/chunking_engine.py`
- chunk/document models and response schemas
- generation prompt construction

## Required behavior / implementation

Preserve source metadata where parser supports it:
`document_id`, `document_version_id`, `page_from/to`, `char_start/end`, `section_path`, `original_text`.

Keep retrieval enrichment text separate from source truth.

Assign stable source markers `[S1]...`; model may cite only provided markers. Reject/flag invented markers.

Ground at atomic factual claim level:
1. split answer into factual claims;
2. bind claim to cited evidence;
3. require citation coverage;
4. run NLI/entailment per claim/evidence;
5. record entailed / unsupported / contradicted;
6. according to configured mode, regenerate/remove/flag unsupported claims.

Measure citation precision/completeness, unsupported-claim rate, contradiction rate, entailment coverage.

Never describe NLI as proof of world truth.



## Required tests

- invented citation marker
- factual claim with no citation
- irrelevant cited source
- contradicted claim
- mixed supported/unsupported answer
- historical citation resolves correct version
- display uses original evidence, not enrichment text

## Acceptance criteria

- [ ] Citation metadata includes version and exact location when available.
- [ ] Invented citation IDs are rejected/flagged.
- [ ] Grounding works per atomic claim.
- [ ] Citation completeness is measurable.
- [ ] Original source text is distinct from enrichment text.
- [ ] Docs remove “mathematical proof of truth” semantics.

## Non-goals

- Proving source document truth.
- Hiding unsupported claims behind one aggregate score.

## Invariant

> **Every factual claim presented as grounded traces to authorized original evidence from a specific document version.**
