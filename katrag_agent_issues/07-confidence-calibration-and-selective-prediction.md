# [P1][ML Quality] Replace heuristic sigmoid confidence with fitted calibration and selective-prediction metrics

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

Applying `sigmoid(raw_cross_encoder_score)` is not calibrated Platt scaling. A raw relevance logit is not a probability of correctness, so numeric confidence is misleading unless fitted and validated empirically.

## Current areas to inspect

- `core_backend/src/services.py`
- reranker loading/scoring
- gate thresholds/config
- response schemas
- `tests/evals/`
Search for `sigmoid`, `Platt`, confidence thresholds, answer/hedge/refuse.

## Required behavior / implementation

Use labelled query-candidate relevance pairs from the eval harness.

Fit calibration:

```text
P(relevant | score) = sigmoid(A*score + B)
```

Persist A/B with model ID, dataset version, calibration version.

Define gate states:
`ANSWER`, `HEDGE`, `REFUSE`.

Measure:
- answer coverage
- false-answer rate
- false-refusal rate
- selective accuracy
- Brier score
- Expected Calibration Error
- risk-coverage curve

Trace raw score, calibrated relevance, decision, reason, calibration version.

If calibration artifact is absent/mismatched, fail explicitly or use a clearly documented non-probability fallback. Do not silently label heuristic score as probability.



## Required tests

- fitted params load deterministically
- model/calibration mismatch fails safely
- threshold boundary cases
- missing calibration artifact behavior
- eval outputs ECE/Brier/selective metrics

## Acceptance criteria

- [ ] Raw sigmoid is no longer described as Platt calibration.
- [ ] Calibration is fitted from labelled data.
- [ ] Calibration artifact is versioned.
- [ ] Gate decision is reproducible from trace/config.
- [ ] ECE/Brier + false-answer/false-refusal are reported.
- [ ] Docs distinguish relevance confidence from factual truth.

## Non-goals

- Universal hallucination probability.
- Arbitrary weighted confidence formula without eval.
- LLM self-reported confidence.

## Invariant

> **A probability-like confidence shown by KatRAG corresponds to an empirically calibrated target variable.**
