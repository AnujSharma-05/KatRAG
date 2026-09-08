# [P3][Documentation][Interview] Align public claims with measured evidence and build a technical demo

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

The public README uses strong claims such as “never forgets” and “mathematical receipts.” Technical readers will challenge claims stronger than the implementation/test evidence. Sell the project through reproducible behavior, not adjectives.

## Current areas to inspect

- root `README.md`
- `docs/architecture/**`
- `demo_core.html`
- `demo_live.html`
- eval/security/load result artifacts

## Required behavior / implementation

Position KatRAG as a production-oriented, multi-tenant retrieval platform focused on retrieval quality, temporal document history, abstention, and auditable evidence.

Avoid unqualified:
- zero hallucination
- zero leakage
- mathematically proven truth
- enterprise-grade
- production-ready
- 10M scale

README structure:
1. What KatRAG is
2. Failure modes
3. Current architecture
4. Retrieval funnel
5. Security model
6. Temporal demo
7. Measured evaluation
8. Reproducible setup
9. Known limitations
10. Roadmap

Clearly label current vs target architecture.

Create deterministic demo cases:
1. exact identifier where hybrid helps;
2. unanswerable query refused;
3. historical v1 vs current v2;
4. tenant/group A cannot retrieve B;
5. optional worker-kill recovery.

Publish only executed benchmark results and commands.



## Required tests

- README links to reproducible eval/security commands
- demo cases deterministic
- claims checked against implemented/tested behavior
- limitations remain visible
- no placeholder number rendered as real measurement

## Acceptance criteria

- [ ] README claims match tested properties.
- [ ] Current vs target architecture is explicit.
- [ ] Benchmark methodology is reproducible.
- [ ] Demo covers retrieval, refusal, temporal, and isolation.
- [ ] Known limitations section exists.
- [ ] Every headline claim has evidence or qualified wording.

## Non-goals

- Making the README timid.
- Hiding limitations.
- Optimizing marketing language over technical credibility.

## Invariant

> **A skeptical interviewer can reproduce the evidence behind every headline technical claim.**
