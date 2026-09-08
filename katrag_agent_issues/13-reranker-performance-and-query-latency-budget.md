# [P2][Performance] Measure and optimize reranker/query latency under an explicit budget

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

Cross-encoder reranking can materially improve ranking but may dominate CPU latency. Performance work must quantify quality gained per unit latency/cost.

## Current areas to inspect

- reranker loading/scoring in `core_backend/src/services.py` or refactored module
- model config
- evaluation harness
- tracing
- container/Kubernetes resource limits

## Required behavior / implementation

First benchmark current hardware/model:
candidate count, token lengths, reranker p50/p95, retrieval p50/p95, TTFT where relevant, CPU/memory.

Evaluate candidate counts such as 10/20/50/100 and plot nDCG/Recall contribution vs p95 latency.

Benchmark, not blindly adopt:
- batching
- input length policy
- ONNX Runtime
- int8 dynamic quantization
- smaller reranker/cascade
- GPU only if economics justify it

Any optimization changing model/runtime behavior must change reproducibility/config metadata.



## Required tests

- benchmark runner deterministic enough for repeated comparison
- candidate-count quality/latency sweep
- at least one optimization compared to baseline
- tenant/security filters unchanged through optimized path

## Acceptance criteria

- [ ] Hardware-qualified latency baseline exists.
- [ ] Quality-vs-candidate-count curve exists.
- [ ] At least one optimization is benchmarked.
- [ ] Selected config is justified by measurement.
- [ ] p50/p95 appear in eval/report.
- [ ] Runtime/model version appears in trace metadata.

## Non-goals

- Arbitrary latency claims.
- GPU solely for resume value.
- Silent quality sacrifice.

## Invariant

> **Reranking remains enabled only when its measured quality gain justifies measured latency/cost.**
