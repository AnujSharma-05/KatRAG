# KatRAG — Engineering Perfection Playbook

> Technical architecture review, improvement roadmap, product positioning guide, security review, evaluation plan, and MAANG-style interview defense.
>
> Review basis: current `main` branch of `AnujSharma-05/KatRAG`, including the root README, `docs/architecture/categorag-engineering-bible.md`, `KatRAG_System_Design.md`, `KatRAG_Verdict_And_Issues.md`, major Core Engine modules, Go gateway/auth/scope code, worker, chunking, Milvus retrieval, cache, grounding, and evaluation scaffolding.
>
> Audience: engineers, senior interviewers, hiring panels, founders, technical buyers.
>
> Principle: **no feature gets credit because it exists. It gets credit only if (1) it solves a real failure mode, (2) the implementation actually enforces the claimed property, and (3) the property can be measured.**

---

# 0. Executive Verdict

KatRAG is **not interesting because it is RAG**.

RAG itself is commodity.

The project becomes interesting only when it is framed as:

> **A reliability-, isolation-, and auditability-oriented retrieval platform for multi-tenant enterprise knowledge, with temporal document history and measurable refusal/grounding behavior.**

That is a defensible engineering story.

The current repository has a strong architectural thesis and several genuinely good implementation choices:

- hybrid dense + sparse retrieval
- RRF fusion
- cross-encoder reranking
- structure-aware chunking work
- parent/child chunking
- category routing
- tenant metadata in vector search
- semantic caching
- temporal supersession primitives
- Go/Python separation
- Kafka/Redpanda worker
- NLI grounding
- evaluation scaffolding
- Kubernetes assets

However, the project currently has a recurring problem:

> **The architecture documentation often describes the target state more strongly than the implementation deserves.**

That is dangerous in a serious interview.

The correct interview strategy is therefore:

1. clearly distinguish **implemented**, **partially implemented**, and **target architecture**;
2. prove improvements using evaluations and load/security tests;
3. aggressively remove overclaims;
4. turn every major feature into a measurable systems-engineering story.

---

# 1. What KatRAG Should Claim — and What It Should Not Claim

## Do claim

> KatRAG is a production-inspired, multi-tenant RAG backend designed around retrieval quality, failure containment, document version history, and observability.

> It combines hybrid dense/BM25 retrieval, category-aware routing, reranking, confidence-based refusal, grounding checks, event-driven ingestion, and scoped retrieval.

> The system treats RAG as a retrieval and reliability problem rather than only an LLM prompt problem.

## Do not claim yet

- “zero hallucination”
- “mathematically proven answer”
- “zero cross-tenant leakage”
- “enterprise-grade security”
- “production-ready”
- “10M chunk scalability”
- “never forgets” without qualification

Better language:

- “designed to reduce hallucinations”
- “returns measurable relevance and grounding signals”
- “enforces tenant scoping in retrieval and tests isolation”
- “production-oriented architecture”
- “validated at X documents / Y chunks / Z QPS”
- “retains superseded document versions and supports point-in-time retrieval”

A senior interviewer rewards precision more than swagger.

---

# 2. System Model

## 2.1 Intended architecture

```text
                         ┌─────────────────────┐
                         │      Clients        │
                         │ Web / Demo / API    │
                         └──────────┬──────────┘
                                    │
                                    ▼
                         ┌─────────────────────┐
                         │    Go API Gateway   │
                         │ JWT / scope / I/O   │
                         └───────┬─────┬───────┘
                                 │     │
                    query path   │     │ ingest event
                                 │     ▼
                                 │  ┌──────────────┐
                                 │  │ Redpanda /   │
                                 │  │ Kafka        │
                                 │  └──────┬───────┘
                                 │         │
                                 ▼         ▼
                      ┌────────────────────────────┐
                      │ Python Core / Worker       │
                      │                            │
                      │ route → hybrid retrieve    │
                      │ → RRF → rerank → gate      │
                      │ → generation → grounding   │
                      └──────┬──────┬──────┬───────┘
                             │      │      │
                    ┌────────┘      │      └────────┐
                    ▼               ▼               ▼
               PostgreSQL         Milvus       Object Store
               metadata/traces    vectors      raw docs
```

## 2.2 The most important architectural rule

**Go owns trust boundaries and transport. Python owns relevance.**

Go should own:

- auth
- scope resolution
- rate limiting
- upload streaming
- public API
- event publication
- WebSockets
- retries around boundary operations

Python should own:

- parsing
- chunking
- embeddings
- category routing
- retrieval
- fusion
- reranking
- confidence
- generation
- grounding

A powerful interview invariant:

> If we bypass Go and call Python with an already validated scope object, retrieval quality should remain byte-for-byte equivalent.

If that invariant breaks, relevance logic has leaked into the gateway.

---

# 3. End-to-End Ingestion Flow

## Current/target logical flow

```text
1. Client uploads a PDF.
2. Gateway authenticates the principal.
3. Gateway resolves canonical organization/group scope.
4. File is streamed to durable object storage.
5. SHA-256 is calculated for idempotency/versioning.
6. PostgreSQL records a pending document version.
7. doc.uploaded is emitted to Kafka/Redpanda.
8. Python worker consumes the event.
9. Worker parses layout.
10. Structural blocks and tables are extracted.
11. Parent/child chunks are produced.
12. Optional contextual enrichment is generated.
13. Dense and sparse representations are produced.
14. Document/category membership is calculated.
15. Vectors are written into Milvus with tenant/version metadata.
16. Relational metadata/status is committed.
17. doc.indexed/doc.failed event is emitted.
18. WebSocket layer surfaces status to the client.
```

## Why `object → row → event` matters

This is a good piece of system design.

Bad ordering:

```text
event → worker wakes → object not uploaded yet → retry storm
```

Better:

```text
durable object
   ↓
durable DB intent
   ↓
replayable event
```

The event should reference state that already exists.

### Real problem?

**Yes. Very real.**

In-process background ingestion fails under:

- pod restart
- deployment
- OOM
- process crash
- replica rebalance
- machine reboot

A queue is justified here because ingestion is:

- long-running
- retryable
- observable
- asynchronous
- naturally idempotent

### Improvement required

Add:

- explicit event schema version
- event ID
- idempotency key
- retry count
- causation/correlation ID
- DLQ
- poison-message handling
- transaction/outbox strategy

### Critical subtlety: DB + Kafka atomicity

The design says:

```text
commit DB row
then
publish Kafka event
```

There is still a failure window:

```text
DB COMMIT succeeds
process dies
Kafka publish never happens
```

Result: a permanently pending document unless repaired.

### Correct solution

Use the **Transactional Outbox Pattern**.

Within one PostgreSQL transaction:

```text
INSERT document_version
INSERT outbox_event(doc.uploaded)
COMMIT
```

A separate outbox relay publishes to Kafka and marks the event dispatched.

This removes the dual-write consistency hole.

### How to sell this feature

Do not say:

> “We used Kafka because microservices.”

Say:

> “Document ingestion is a long-running job. In the first version it used in-process background work, so a process crash could lose ingestion. We moved work to an at-least-once event pipeline, made consumers idempotent, and designed an outbox to close the DB/Kafka dual-write window.”

That sounds like engineering.

---

# 4. Structure-Aware Parsing and Chunking

## What is the feature?

Instead of fixed character splitting, KatRAG attempts to retain:

- headings
- sections
- page information
- tables
- parent/child relations

The chunking code extracts tables separately and uses block metadata to build larger parent chunks and smaller retrieval children.

## What problem does it solve?

Naive chunking destroys information.

Example:

```text
Section 8.4 — Refund eligibility
[paragraph]

Table:
Tier | Refund Window
A    | 30 days
B    | 14 days
```

A character splitter may produce:

```text
Chunk 1: Section title + paragraph + half table
Chunk 2: remaining table without heading
```

The embedding no longer knows what the numbers mean.

## Is this a real problem?

**Absolutely.**

For enterprise corpora, document parsing quality often matters more than changing the LLM.

Failures occur in:

- contracts
- invoices
- policies
- technical manuals
- two-column PDFs
- tables
- scanned documents

## Current weakness

The heading heuristic remains simple:

- font size > threshold
- font contains “bold”

That is brittle across document templates.

Parent-child splitting also uses a word-to-token approximation in parts of the code.

## Better implementation

### Parsing tiers

Per page:

1. clean digital PDF → PyMuPDF
2. layout-rich page → Docling/Unstructured
3. scanned page → OCR
4. diagram/form-heavy page → vision model only where required

### Structural representation

Normalize each page into blocks:

```json
{
  "type": "paragraph|heading|table|list|figure",
  "page": 12,
  "bbox": [x1,y1,x2,y2],
  "section_path": ["3", "3.2"],
  "text": "...",
  "char_span": [12003, 12684]
}
```

### Chunking

Retrieve small, synthesize big:

```text
256-token child  → embedding/retrieval
1024-token parent → LLM context
```

Why?

Small chunks improve retrieval precision.

Large chunks improve answer context.

## Evaluation

Create chunking-specific test cases:

- table lookup
- heading-dependent answer
- value requiring previous paragraph
- list item
- multi-column document
- scanned appendix

Compare:

```text
fixed-char baseline
vs
structure-aware
vs
parent-child
```

Measure:

- retrieval recall@50
- MRR
- nDCG@10
- citation span accuracy

## How to sell it

> “We found that retrieval errors were often ingestion errors disguised as embedding errors. We changed the corpus representation from flat character windows to layout-aware, parent-child chunks and measured the change independently.”

---

# 5. Contextual Chunk Enrichment

## What is it?

Before embedding a chunk, prepend a short context describing where it belongs.

Raw:

```text
Employees may carry over a maximum of 10 days.
```

Enriched:

```text
This passage is from the annual leave carry-over section of the 2026 HR Leave Policy.

Employees may carry over a maximum of 10 days.
```

## Problem solved

Detached chunks often lose:

- entity
- document
- section
- timeframe
- policy type

Semantic embeddings then represent an ambiguous fragment.

## Is this real?

Yes, especially for corpora containing many documents with similar wording.

## Weakness

LLM enrichment can itself:

- hallucinate
- alter meaning
- add cost
- add latency during ingest

## Hard rule

**Never display or cite enrichment text as source truth.**

Store separately:

```text
retrieval_text = context_prefix + original_text
display_text   = original_text
```

## Improvements

- use deterministic section metadata first
- only call LLM when metadata is insufficient
- cache document context
- batch chunks
- store enrichment model/version
- evaluate enrichment/no-enrichment through ablation

## Sell

> “The system distinguishes retrieval representation from evidence representation. LLM-generated context can help retrieval, but users only see verbatim source text.”

That is a subtle, good design point.

---

# 6. Dense + Sparse Hybrid Retrieval

## What is it?

Two retrieval channels:

### Dense

Embedding similarity.

Good for:

- paraphrase
- concepts
- semantic equivalence

### Sparse / BM25

Lexical matching.

Good for:

- IDs
- SKUs
- error codes
- contract numbers
- exact terminology

Then combine rankings with RRF.

## Problem solved

Dense retrieval can fail badly on:

```text
AX-4099-B
JPL-2026
RFC 9110
CVE-2026-XXXX
```

while BM25 can fail on paraphrases.

## Is it real?

Yes. This is one of KatRAG’s most defensible features.

## Current implementation positive

The current Milvus code uses native hybrid search and RRF, which is materially better than the earlier in-memory `rank_bm25` architecture.

## Improvements

### Retrieve wider

```text
Dense top 100
Sparse top 100
      ↓
RRF top 50
      ↓
rerank
```

Do not retrieve 5 and ask a reranker to perform magic.

### Dynamic weighting

Detect query class.

If exact identifier detected:

```text
sparse weight ↑
```

If conceptual prose:

```text
dense weight ↑
```

Do not hand tune blindly. Learn on evaluation data.

### Add negative cases

- exact ID with typo
- rare acronym
- semantic paraphrase
- phrase collision
- same SKU across tenants

## Sell

> “Dense retrieval gave strong semantic recall but missed lexical identifiers, so we added native sparse retrieval and rank fusion. We evaluate exact-ID and semantic workloads separately.”

---

# 7. Category Routing

## What is the feature?

KatRAG narrows or biases retrieval toward semantically likely document categories.

Examples:

```text
HR Policies
Engineering Manuals
Legal Contracts
Finance
Security Runbooks
```

## Problem solved

In a heterogeneous corpus, semantically similar terms can exist in unrelated domains.

“termination” could mean:

- employment termination
- cable termination
- contract termination

A category signal can improve precision and reduce search noise.

## Is it truly real?

**Yes, but only at sufficiently heterogeneous scale.**

At 1,000 chunks, routing is usually unnecessary.

At large corpora with strong domains, it can help.

The category feature therefore needs to earn its complexity via evaluation.

## Biggest architectural risk

A hard category filter before retrieval can destroy recall permanently.

```text
router chooses wrong category
        ↓
correct document excluded
        ↓
retriever never sees it
        ↓
reranker cannot recover
        ↓
LLM confidently answers from wrong evidence
```

This is more dangerous than a visible crash.

## Correct design

**Soft routing.**

Example:

```text
top 3 category candidates → retrieve 80
global fallback          → retrieve 40

union
↓
fusion with modest category boost
```

The category is a prior, not a security boundary.

## Current concern

The Python hot path uses category similarity and a low-confidence global fallback, but the complete intended “routed union global with measured recall floor” should be verified and benchmarked.

## Betterments

- category centroid per tenant/group
- top-k routes, not single category
- uncertainty margin
- global fallback
- router recall@1 / recall@3
- confusion matrix
- category drift monitor
- human correction workflow

## Sell

Do not say:

> “Hierarchical RAG searches faster.”

Say:

> “Category routing is a soft relevance prior. We intentionally avoid hard filtering because routing errors above retrieval are irreversible. Its continued existence is conditional on measured recall/latency benefit.”

A good interviewer will like that sentence.

---

# 8. Cross-Encoder Reranking

## What is it?

Bi-encoder retrieval independently embeds query and chunk.

Cross-encoder reranking jointly evaluates:

```text
(query, candidate passage)
```

It is slower but more accurate.

## Problem solved

ANN search optimizes candidate generation, not final relevance ordering.

## Is it real?

Yes. This is probably one of the strongest quality features.

## Current weakness

CPU reranking can dominate latency.

## Betterments

1. ONNX Runtime
2. int8 dynamic quantization
3. batch inference
4. cap input length
5. fast→strong cascade
6. GPU when justified

## Measurements

- rerank nDCG@5
- p50/p95 latency
- quality gain per millisecond

## Sell

> “Vector search is candidate generation. We retrieve wide, then spend compute only on a small candidate set using a stronger interaction model.”

---

# 9. Confidence Gate

## What is it?

The system decides:

```text
ANSWER
HEDGE
REFUSE
```

before blindly generating.

## Problem solved

Most RAG demos answer every question, even when retrieval is garbage.

## Is this real?

Yes. In enterprise systems, **knowing when not to answer** is a core quality problem.

## Critical implementation issue

The current code applies a sigmoid directly to the raw cross-encoder score and calls it a “Platt scaling approximation”.

That is **not calibrated Platt scaling**.

True Platt scaling learns:

```text
P(y=1 | score) = sigmoid(A*score + B)
```

where A and B are fitted from labelled data.

`sigmoid(raw_score)` assumes:

```text
A = 1
B = 0
```

without evidence.

That means a displayed “0.82 relevance probability” may not be an 82% probability at all.

## Fix

Create labelled relevance pairs.

Fit calibration:

```python
LogisticRegression().fit(raw_scores, labels)
```

Then verify using:

- reliability diagram
- Expected Calibration Error
- Brier score

## Composite confidence

Potential signals:

```text
reranker calibrated relevance
dense/sparse agreement
margin to second candidate
source authority
freshness
retrieval diversity
router uncertainty
```

But do not add a fancy weighted formula unless evals prove it helps.

## Measure both sides

Never publish only hallucination reduction.

Also publish:

- false refusal rate
- answer rate
- selective accuracy
- risk-coverage curve

## Sell

> “We optimize selective prediction, not raw answer rate. The system is allowed to abstain, and we measure the cost of abstention using false-refusal rate.”

That sounds significantly more sophisticated than “confidence score.”

---

# 10. Citation System

## What is it?

Answer claims should map to:

```text
document
document version
page
chunk
character span
```

## Problem solved

“Grounded” is meaningless if the user cannot verify evidence.

## Is it real?

Yes.

Especially for:

- legal
- compliance
- policy
- audit
- research

## Correct design

At ingestion:

```text
page_from
page_to
char_start
char_end
section_path
version_id
```

At generation:

```text
[S1]
[S2]
```

At postprocessing:

- accept only known source markers
- reject invented source IDs
- map marker → source metadata
- surface exact quote/span

## Betterments

### Claim-level citation validation

Split response into claims.

For each factual claim:

```text
does it contain ≥1 citation?
does cited span entail claim?
```

Metric:

```text
citation precision
citation recall
citation completeness
```

## Sell

> “A citation is not decoration. It is part of the answer contract and is validated against the exact version/page/span used to generate the response.”

---

# 11. NLI Grounding Verifier

## What is it?

After generation, compare generated claims against cited evidence using an entailment classifier.

Output roughly:

```text
entailed
neutral
contradicted
```

## Problem solved

An LLM can produce a perfectly formatted citation that does not support the claim.

## Is this real?

Yes.

But the verifier is not a “mathematical proof”.

It is another learned model with its own error distribution.

## Correct framing

> “Independent post-generation grounding signal.”

Not:

> “mathematical receipt proving truth.”

## Better implementation

1. split answer into atomic claims
2. bind each claim to its cited chunks
3. run NLI
4. aggregate:
   - entailment coverage
   - contradiction rate
5. if blocking mode:
   - regenerate/remove unsupported claims
6. if async mode:
   - flag traces and feed evaluation

## Important distinction

Grounding verifies:

```text
answer is supported by source
```

It does not verify:

```text
source itself is true
```

Garbage source → faithfully grounded garbage.

## Sell

> “We separate relevance from groundedness. Retrieval score answers ‘did we fetch something relevant?’ NLI answers ‘does the cited evidence actually support the generated claim?’”

---

# 12. Multi-Tenancy and Scope Isolation

## What is it?

A query should only retrieve documents the principal is authorized to access.

## Problem solved

Cross-tenant data leakage is existential for enterprise knowledge systems.

## Is it real?

Yes. This is one of the most commercially relevant features in the project.

## Current serious blockers

### Blocker A — hard-coded JWT secret

The Go JWT implementation currently contains a literal shared HMAC secret in source.

This is unacceptable for anything described as production or enterprise.

### Blocker B — mock scope resolver

Current Go scope resolution is mocked and maps unknown users to a default org/group.

Unknown identity must never receive a fallback authorization scope.

Correct behavior:

```text
unknown principal → deny
```

not:

```text
unknown principal → DEFAULT_ORG
```

### Blocker C — default org in Python

The query function has a default organization argument.

Security-sensitive scope should never have a permissive default.

Make it required.

### Blocker D — group-level filtering

The shown Milvus hot path scopes on organization ID and version state.

The architecture claims org→group isolation.

Group IDs must be enforced by the datastore query, not only by application routing.

## Required redesign

### Authentication

Use:

- OIDC/OAuth2 provider
- asymmetric JWT: RS256/EdDSA
- JWKS
- issuer validation
- audience validation
- expiry
- not-before
- token ID
- key rotation

### Authorization

Construct immutable:

```text
Scope {
  principal_id
  organization_id
  permitted_group_ids
  role
  as_of
  index_version
}
```

No defaults.

### Internal trust

Python must not be publicly reachable.

Prefer:

- private Kubernetes service
- NetworkPolicy
- mTLS between gateway and Core
- signed/internal identity
- header stripping at ingress

Never let clients send trusted:

```text
X-Scope-Org
X-Scope-Group
```

and reach Python directly.

### Vector query

Every dense and sparse arm must share exactly the same filter:

```text
organization_id == X
AND group_id in [...]
AND temporal/version filter
```

### Defense in depth

After retrieval:

```python
assert every_result.organization_id == scope.organization_id
assert every_result.group_id in scope.group_ids
```

If false:

- return error
- increment security counter
- page/alert

## Security tests

- org A cannot retrieve org B
- group A cannot retrieve group B
- cache isolation
- temporal isolation
- erased document unreachable
- forged scope header ignored
- malformed JWT rejected
- expired JWT rejected
- algorithm confusion rejected
- unknown principal denied

## Sell

> “Prompt boundaries are not security boundaries. Authorization is applied before the LLM, inside the retrieval datastore, and asserted again after retrieval.”

This is one of the best lines in the whole project.

---

# 13. Semantic Cache

## What is it?

Return a cached answer for a semantically equivalent previous query.

## Real problem solved

Repeated enterprise questions:

```text
“What is our maternity leave policy?”
“How many maternity leave days are allowed?”
```

can avoid full retrieval/reranking/generation.

## Is it real?

Yes, but it introduces a major data-leak risk.

## Cache identity must include

```text
org
group set
query representation
index version
document-set version
model/prompt version when necessary
```

## Why `doc_set_version` matters

Suppose:

1. answer cached
2. policy document deleted
3. query repeated
4. stale answer returned

Now deletion did not actually remove access.

Increment a monotonic corpus version after:

- add
- update
- supersede
- erase

## Betterments

- exact cache before semantic cache
- tenant-partitioned ANN cache
- TTL
- negative cache for repeated unanswerable queries
- invalidation events
- cache hit quality audit
- never cache highly personalized answers without user scope

## Sell

> “Caching is part of the security model because stale or cross-scope cache hits are equivalent to retrieval leaks.”

---

# 14. Document Versioning and Temporal Retrieval

## What is it?

Instead of overwriting a policy:

```text
Leave Policy v1
Leave Policy v2
Leave Policy v3
```

retain version validity windows.

Default:

```text
retrieve current
```

Temporal:

```text
retrieve version active at time T
```

## Problem solved

Questions such as:

> What policy was in force on the day this incident occurred?

A normal current-state RAG cannot answer reliably.

## Is this a real problem?

**Yes, and this is one of the best potential product differentiators.**

Strong verticals:

- compliance
- legal
- HR
- finance
- security policy
- regulated operations

## Hard parts

### Atomic supersession

Ensure:

```text
new.valid_from = T
old.valid_to = T
```

without overlapping or empty temporal windows.

Use transaction + exclusion/consistency constraints.

### Index semantics

Old vectors remain available for temporal queries but not default retrieval.

### Erasure

Retention and “never forget” conflict.

You need two different operations:

```text
supersede → retain
erase      → destroy
```

## Build a killer demo

Upload:

```text
Policy v1: leave = 20 days
Policy v2: leave = 25 days
```

Ask:

```text
“What is the current leave entitlement?”
→ 25

“What was it on 2025-05-01?”
→ 20

“What changed?”
→ +5 days, with citations to both versions
```

This demo is much stronger than “chat with PDF.”

## Sell

> “Most RAG systems answer over the current corpus. KatRAG models knowledge as time-varying state.”

---

# 15. Event-Driven Worker

## Real value

The Kafka worker is justified only if the project demonstrates:

- replay
- idempotency
- DLQ
- lag metrics
- recovery after crash
- partitioning behavior

Otherwise Kafka is resume-decoration.

## Must implement

### Event envelope

```json
{
  "event_id": "...",
  "event_type": "doc.uploaded",
  "schema_version": 1,
  "organization_id": "...",
  "document_version_id": "...",
  "idempotency_key": "...",
  "trace_id": "...",
  "created_at": "..."
}
```

### Consumer

```text
read
→ check idempotency
→ transition state
→ process
→ commit result
→ acknowledge
```

### State machine

```text
pending
parsing
chunking
enriching
embedding
indexing
indexed
failed
superseded
erased
```

Validate legal transitions.

## Chaos test

During a 100-document ingest:

```text
kill -9 worker
restart
```

Expected:

- no lost docs
- no duplicated active versions
- eventual completion
- consumer lag recovers

## Sell

Show the failure video.

> “I killed the worker during indexing. The job resumed because state and work were durable.”

Much more impressive than showing a Kafka diagram.

---

# 16. Go Gateway

## Why Go?

Go must earn its presence.

Bad answer:

> “Go is fast.”

Better:

- boundary service has high I/O concurrency
- upload streaming
- WebSockets
- low-memory concurrency
- simple static deployment
- explicit separation from ML runtime

## When Go is overengineering

If system traffic is tiny and the gateway only proxies three routes, Python could do it.

Interviewers may challenge this.

Correct answer:

> “For the current portfolio scale, Go is not strictly necessary. I introduced it to enforce a language/process boundary between public edge concerns and retrieval intelligence, and because the gateway also owns large upload streaming, WebSocket fan-out, auth and event publication. If those responsibilities disappeared, I would remove the second language.”

That is a mature answer.

---

# 17. Evaluation Harness — Highest Priority

The repo currently has evaluation scaffolding, but the sample dataset is tiny.

A serious project cannot claim retrieval improvement from three example questions.

## Required golden set

Minimum:

```text
150–300 manually curated questions
```

Breakdown:

- 25% semantic
- 15% exact ID
- 10% lexical ambiguity
- 10% cross-category
- 10% temporal
- 10% tables
- 10% unanswerable
- 5% adversarial injection
- 5% multi-hop

Each case:

```yaml
query:
org:
groups:
answerable:
expected_category:
relevant_document_versions:
relevant_chunk_ids:
gold_answer:
required_facts:
forbidden_facts:
```

## Retrieval metrics

### Recall@K

Did the correct evidence appear anywhere?

### MRR

How early did the first relevant item appear?

### nDCG

How good is the complete ranking?

## Routing metrics

- recall@1
- recall@3
- global fallback rate

## Gate metrics

- false refusal rate
- false answer rate
- selective accuracy
- coverage

## Generation metrics

- claim correctness
- citation precision
- citation completeness
- grounding entailment
- contradiction rate

## Performance

- p50 / p95 / p99
- TTFT
- full completion latency
- rerank latency
- vector query latency
- cache hit ratio

## Infrastructure

- ingest throughput
- Kafka lag
- worker recovery
- duplicate rate
- failed ingest rate

## Security

- cross-org leak count = 0
- cross-group leak count = 0
- stale-cache-after-erasure = 0

## The most useful experimental table

```text
                         Recall@50   nDCG@5   False-answer   p95
Baseline dense
+ sparse
+ structure chunking
+ contextual enrichment
+ routing
+ reranker
+ confidence gate
```

This turns the project into an engineering experiment.

---

# 18. Ablation Study

A MAANG interviewer may ask:

> How do you know each feature helps?

Answer using ablation.

Run:

```text
A = dense-only baseline
B = A + BM25
C = B + structure-aware chunking
D = C + contextual enrichment
E = D + soft routing
F = E + reranker
G = F + calibrated gate
```

Report deltas.

If a feature has:

```text
+1 ms
+0.0 quality
+complexity
```

delete it.

This is extremely important.

The goal is **not maximum architecture**.

The goal is **minimum architecture that proves value**.

---

# 19. Observability

## Required trace

Every query should create a trace:

```text
auth
scope
cache
rewrite
route
dense
sparse
fusion
rerank
gate
generation
grounding
```

Fields:

```text
trace_id
org
group
models
index_version
candidate IDs
scores
latencies
gate result
citations
grounding result
```

## Golden debugging question

For any bad answer:

> Why did the system say this?

You should be able to determine whether failure came from:

1. parse
2. chunk
3. route
4. retrieve
5. rank
6. gate
7. generate
8. grounding

If you cannot identify the failed stage, the system is not operable.

## Dashboard set

### Quality

- recall
- nDCG
- grounding
- refusal
- answer coverage
- category confusion

### Performance

- p95 stage latency
- cache
- CPU/GPU
- DB latency
- Milvus latency

### Ingest

- job state
- failures
- lag
- throughput

### Tenancy

- per-org QPS
- cost
- storage
- errors

### Corpus health

A particularly interesting metric:

```text
documents never retrieved during a defined evaluation/probe period
```

This measures “functionally forgotten” knowledge.

---

# 20. Security Threat Model

## P0 — Tenant isolation

Failure = confidential data leak.

Mitigation:

- deny-by-default scope
- datastore filters
- private Core network
- group filters
- post-retrieval assertions
- cache scoping
- security CI

## P0 — Scope-header spoofing

If Python accepts internal scope headers and is network reachable, an attacker could forge them.

Mitigation:

- Python internal-only
- ingress cannot route to it
- NetworkPolicy
- mTLS / workload identity
- gateway overwrites/strips external scope headers

## P0 — Hard-coded JWT secret

Remove from code immediately.

Rotate any secret ever used outside local dev.

## P1 — Indirect prompt injection

Retrieved document:

```text
IGNORE SYSTEM MESSAGE...
```

Mitigation layers:

- treat retrieved content as untrusted data
- no privileged tools available to generation model
- source delimiters
- injection detector
- output grounding
- datastore scope

## P1 — Malicious PDF

- decompression bomb
- huge pages
- parser exploit
- embedded file
- pathological OCR

Mitigation:

- max size
- max page count
- timeout
- sandbox parsing
- CPU/memory cgroup
- MIME validation
- antivirus where relevant

## P1 — Resource exhaustion

- huge query rate
- expensive multi-query expansion
- repeated reranker calls
- ingest flood

Mitigation:

- rate limit
- quotas
- concurrency limits
- token budget
- circuit breakers

## P1 — Sensitive telemetry

Query traces contain user questions and source IDs.

Apply:

- retention
- encryption
- RBAC
- redaction
- audit access

---

# 21. Production Correctness Gaps to Fix

## Critical

### 1. Replace hard-coded JWT secret

Use asymmetric identity/JWKS.

### 2. Replace mocked scope resolution

Real DB-backed membership.

Unknown user → 403.

### 3. Make scope mandatory in Python

Remove default org.

### 4. Add group filtering to every retrieval arm

Dense and sparse must be identical.

### 5. Close DB/Kafka dual-write gap

Transactional outbox.

### 6. Expand isolation testing

Org + group + cache + temporal + erasure.

## High

### 7. True confidence calibration

Not `sigmoid(logit)`.

### 8. Expand evaluation dataset

Three questions are not evidence.

### 9. Make routing provably soft

Measure router recall.

### 10. Citation validation

Marker → exact source span.

### 11. Grounding at claim level

Not whole-answer-vs-whole-context only.

### 12. Versioning transaction correctness

Prevent temporal overlap.

## Medium

### 13. Replace print debugging

Structured logs.

### 14. Split `services.py`

Suggested modules:

```text
retrieval/
  router.py
  hybrid.py
  reranker.py
  confidence.py

ingestion/
  parser.py
  chunker.py
  enrichment.py
  indexer.py

generation/
  synthesize.py
  citations.py
  grounding.py

application/
  query_service.py
  ingest_service.py
```

A 600+ LOC orchestration file becomes difficult to test.

### 15. Explicit config/version object

Every trace should record exact:

- embedding model
- reranker
- chunker version
- thresholds
- prompt version
- fusion params

---

# 22. Performance Plan

## Query budget example

```text
Gateway/auth        20 ms
Embedding           20 ms
Routing             10 ms
Milvus hybrid       80 ms
Reranking          150 ms
Gate                 5 ms
LLM TTFT            600 ms
--------------------------------
TTFT target         <1 s–1.5 s
```

Do not quote targets as achieved until measured.

## Key optimizations

1. embed queries in batch where possible
2. warm model process
3. ONNX reranker
4. retrieve wide but bound candidates
5. semantic/exact cache
6. connection pooling
7. avoid LLM category call on every query
8. async grounding if product semantics permit
9. precompute category centroids
10. profile before optimizing

---

# 23. Scalability Story

Do not pretend a laptop test proves 10M chunks.

Use a scale ladder.

## L0

```text
5k chunks
1 org
single worker
```

## L1

```text
50k chunks
5 orgs
50 VUs
```

## L2

```text
500k–1M synthetic chunks
load-test environment
multiple workers
```

## L3

Production cluster:

- distributed Milvus
- multi-broker Kafka
- HA Postgres
- object storage
- autoscaling

Interview answer:

> “The repository demonstrates architectural scaling properties locally. It does not claim empirical 10M-chunk validation until a test environment actually runs that load.”

---

# 24. Kubernetes — Make It Earn Its Place

Do not pitch Kubernetes because “enterprise uses K8s.”

Demonstrate:

- readiness
- liveness
- resource requests/limits
- PodDisruptionBudget
- worker autoscaling from Kafka lag
- NetworkPolicy
- secrets
- rolling deployments
- graceful shutdown
- persisted external state

Killer demo:

```text
start ingest
kill worker pod
watch Kubernetes restart it
watch Kafka redeliver
watch document finish
```

That connects Kubernetes to a reliability property.

---

# 25. What Can Actually Be Sold?

## Weak pitch

> AI document chatbot.

Commoditized.

## Better product wedge

### Temporal Compliance Knowledge Engine

Target:

- HR/compliance
- legal
- regulated enterprise ops

Promise:

> “Ask not only what policy says now, but what version was in force at a past point in time, with exact citations.”

This makes use of the strongest unique architecture.

## Second wedge

### Secure Internal Knowledge Platform

Promise:

> “One RAG platform across departments while enforcing group/tenant document boundaries before generation.”

## Third wedge

### Auditable Technical Support Knowledge

Target:

- manufacturing
- network operations
- equipment manuals

Strengths:

- exact identifier BM25
- semantic search
- citations
- refusal

## What a technical buyer wants

Not architecture buzzwords.

They want:

- data boundary
- SSO
- audit logs
- retention
- deletion
- citations
- latency
- accuracy
- deployment model
- cost
- failure behavior

---

# 26. Demo Script for Interview

## 8-minute version

### Minute 0–1 — problem

> “A naive RAG system fails in three places: it can retrieve the wrong context, it answers when evidence is weak, and shared indexes create serious authorization risk.”

### Minute 1–2 — architecture

Show only:

```text
Gateway
→ Core retrieval funnel
→ Milvus/Postgres
→ async ingestion
```

### Minute 2–4 — retrieval failure demo

Ask exact-ID question.

Show:

```text
dense rank
BM25 rank
RRF
reranker
```

### Minute 4–5 — refusal

Ask unanswerable question.

Show gate refusing.

### Minute 5–6 — temporal

Ask current policy vs old policy.

### Minute 6–7 — security

Org A query cannot retrieve Org B chunk.

### Minute 7–8 — metrics

Show ablation/eval dashboard.

Finish:

> “The project is not an attempt to invent RAG. It is an attempt to engineer the failure modes around RAG.”

---

# 27. Resume Bullet

Weak:

> Developed RAG application using Python, Go, Milvus, Kafka and Kubernetes.

Better, once measured:

> Built a multi-tenant retrieval platform combining dense/BM25 hybrid search, cross-encoder reranking, temporal document versioning and confidence-based abstention; implemented durable Kafka ingestion and datastore-level tenant scoping, then evaluated retrieval quality and failure behavior with an automated golden-set harness.

Best version needs real numbers:

> Improved Recall@50 from X→Y and reduced false-answer rate from A→B at p95 latency C ms across N evaluation questions; built crash-safe event ingestion and zero-leak org/group security tests.

Never invent the numbers.

---

# 28. MAANG-Style Interview Loop

The following loop assumes 5–6 technical rounds.

---

## Round 1 — Project Deep Dive

### Q1. Give me the project in 60 seconds.

**Answer**

KatRAG is a production-oriented RAG backend for multi-tenant document knowledge. The core idea is that reliable RAG is mostly a retrieval and systems problem. Queries go through scoped hybrid dense/BM25 retrieval, optional category priors, RRF, cross-encoder reranking and a confidence gate before generation. Answers carry source metadata and can be post-checked using NLI. Ingestion is separated from the request process through an event pipeline, and document versions are retained for point-in-time retrieval. Go owns the internet-facing boundary and Python owns retrieval intelligence.

### Q2. What did you invent?

**Answer**

I did not invent RAG, BM25, RRF, HNSW or cross-encoders. The engineering contribution is the system composition and the way failure modes are handled: soft routing instead of recall-destroying hard routing, hybrid retrieval for lexical/semantic workloads, abstention when evidence is weak, tenant enforcement before generation, durable ingestion, and temporal corpus semantics. The value has to be demonstrated through evaluation rather than novelty claims.

### Q3. What is the strongest feature?

**Answer**

For product differentiation, temporal document retrieval. For retrieval quality, hybrid retrieval plus reranking. For enterprise viability, datastore-level scope isolation.

### Q4. What is currently weakest?

**Answer**

Evaluation depth and security hardening. The architecture is ahead of the proof. The current eval dataset is too small to support strong quality claims, and the gateway still contains dev-level auth/scope code that must be replaced before production positioning.

### Q5. Why not LangChain?

**Answer**

A framework could orchestrate parts of the flow, but I wanted retrieval stages and contracts to remain explicit. The critical behavior—scope filters, fusion, reranking, confidence, traces—should be independently testable. I would use a framework where it reduces undifferentiated integration work, but not if it obscures security/retrieval invariants.

---

## Round 2 — Information Retrieval / ML

### Q1. Why hybrid search?

**Answer**

Dense retrieval optimizes semantic similarity and sparse retrieval handles lexical exactness. Enterprise corpora contain both. Product codes, CVEs and clause identifiers are high-information tokens that dense encoders may not preserve reliably. Hybrid retrieval increases candidate recall across both query types.

### Q2. Why RRF?

**Answer**

Dense cosine and BM25 live on unrelated score scales. RRF combines rankings instead of raw scores, so I do not need brittle normalization. It is robust and simple. If evaluation demonstrates category-specific benefit, I can replace it with learned or weighted fusion.

### Q3. Why retrieve 100 then rerank?

**Answer**

The reranker cannot recover evidence that candidate generation excluded. Early retrieval is recall-oriented. Cross-encoder is precision-oriented. I spend cheap ANN computation to preserve candidate recall, then expensive attention on a bounded set.

### Q4. Explain HNSW.

**Answer**

HNSW is a graph-based approximate nearest-neighbor index. Vectors form layered proximity graphs. Search begins in sparse upper layers to move rapidly toward a promising region and descends into denser lower layers. `efSearch` controls the exploration width: higher values generally improve recall at higher latency.

### Q5. Why not pure vector search?

**Answer**

Because the embedding geometry is not the corpus truth. Identifiers and lexical constraints are a common failure class. Also, vector similarity is candidate relevance, not authorization, freshness or factual grounding.

### Q6. What is wrong with sigmoid(cross_encoder_logit)?

**Answer**

A raw transformer relevance logit is not calibrated probability. Sigmoid alone assumes calibration slope 1 and intercept 0. Proper Platt scaling learns those parameters on labelled relevance data and should be validated with ECE/Brier/reliability curves.

### Q7. How do you pick the gate threshold?

**Answer**

I would use a validation set and optimize for the product’s risk tradeoff. For compliance, false answers cost more than false refusals. I would examine a risk-coverage curve, selective accuracy and false-refusal rate instead of choosing an arbitrary constant.

### Q8. What happens when routing is wrong?

**Answer**

If routing hard-filters before retrieval, recall can become zero and nothing downstream can fix it. Therefore routing is a soft prior: search top categories plus a global fallback and measure router recall@k.

### Q9. Why NLI after generation?

**Answer**

Retrieval relevance and answer support are different properties. A relevant chunk may not support a generated claim. NLI adds an independent estimate of entailment/contradiction between cited evidence and claim.

### Q10. Is NLI proof of correctness?

**Answer**

No. It is a learned verifier. It can fail and it only checks support relative to the source, not source truth.

---

## Round 3 — Backend / Distributed Systems

### Q1. Why Kafka?

**Answer**

For ingestion durability, replay and horizontal workers. A PDF ingestion job can take seconds or minutes and must survive process restarts. Kafka/Redpanda provides at-least-once work delivery and observable lag. I would not use it merely to make the architecture look distributed.

### Q2. Exactly-once?

**Answer**

I do not assume exactly-once processing. I design for at-least-once delivery and idempotent consumers. Document content hash/version IDs provide idempotency boundaries.

### Q3. DB commit succeeds but Kafka publish fails. What happens?

**Answer**

That is a dual-write inconsistency. The correct production solution is a transactional outbox: write domain state and an outbox event in one Postgres transaction, then asynchronously relay the outbox to Kafka.

### Q4. Kafka publishes twice?

**Answer**

Consumer checks idempotency key/state before mutation. A repeated event must converge to the same final state.

### Q5. Worker fails halfway through Milvus insert?

**Answer**

The operation must be restartable. The database document version remains in a transitional status. On retry, indexing should use deterministic chunk identities or delete/reconcile partial writes rather than creating duplicates. The state transition is committed only after the full index operation succeeds.

### Q6. Ordering?

**Answer**

Key events by document/version where strict per-document ordering matters; organization-level keys may cause unnecessary serialization. For supersession, the consumer must prevent an older event from overriding a newer version using version numbers/state checks.

### Q7. Why Go + Python?

**Answer**

Python is the natural ML runtime. Go is good for the edge because the gateway is I/O-heavy: streaming uploads, WebSockets, auth and event publication. More importantly, the split creates a clear architecture boundary. At small scale one language is simpler, so the second runtime must earn its complexity.

### Q8. REST or gRPC internally?

**Answer**

gRPC is attractive for typed contracts and streaming. For a portfolio implementation HTTP is easier to debug. I would choose based on whether independent deployments and streaming justify the contract complexity. Either way, version the contract.

---

## Round 4 — Security

### Q1. What is the worst possible bug?

**Answer**

Cross-tenant retrieval. A wrong answer is a quality incident. Cross-tenant confidential data is a security incident that can kill the product.

### Q2. Why not instruct the LLM not to reveal other tenant data?

**Answer**

Because authorization cannot depend on model compliance. The LLM should never receive unauthorized evidence. Scope must be enforced by the retrieval datastore before generation.

### Q3. What is currently wrong with auth?

**Answer**

The current Go implementation contains a hard-coded HMAC secret and mocked scope resolution. Both are development scaffolding. Production should use OIDC with asymmetric JWT verification/JWKS, strict issuer/audience/expiry validation and deny-by-default database-backed scope resolution.

### Q4. What if an attacker sends X-Scope-Org?

**Answer**

The public edge must strip all internal scope headers and generate its own canonical scope. The Core service should be private and ideally authenticate the gateway workload via mTLS or service identity.

### Q5. Prompt injection from a document?

**Answer**

Retrieved content is untrusted data. Delimit it, prohibit instructions from retrieved content, ensure generation has no privileged tools, enforce tenant filters below the model, and validate output against sources. There is no single perfect prompt-injection defense.

### Q6. Embeddings are safe to expose?

**Answer**

No. Embeddings can leak semantic information and are a sensitive derived artifact. Milvus should not be public and vectors should follow data retention/encryption controls.

### Q7. How do you test isolation?

**Answer**

Generate adversarial pairs across organizations and groups. For every query, assert no unauthorized chunk appears at candidate, rerank, cache or answer level. Run this suite on releases and maintain runtime post-retrieval assertions.

---

## Round 5 — System Design / Scale

### Q1. Design this for 100M chunks.

**Answer outline**

- shard/partition by tenant or balanced tenancy key
- distributed vector store
- sparse + dense indexes
- tier large tenants separately
- stateless query workers
- model serving tier
- distributed Kafka
- object storage
- HA relational metadata
- caching
- asynchronous ingest
- observability
- per-tenant quotas
- dual-index migrations

Important: first ask scale distribution. 100M across 100k tenants is different from one tenant with 100M.

### Q2. Large tenant creates noisy neighbor?

**Answer**

Per-org quotas, rate limits, query concurrency limits, worker fairness, partition strategy, metering and dedicated isolation tier for very large tenants.

### Q3. Change embedding dimension?

**Answer**

Do not mutate live collection in place. Create `index_version=2`, dual-write new ingests, backfill, shadow read, evaluate, per-tenant cut over, then retire old index.

### Q4. Zero downtime model migration?

**Answer**

Version all corpus representations. New and old indexes coexist. Reads are controlled by tenant feature/config flag. Rollback means switching the read index, not rebuilding.

### Q5. How would you make semantic cache correct?

**Answer**

Key by tenant/group scope plus corpus/index version. Semantic neighbor search itself must be partition scoped. Any corpus mutation increments a document-set version.

---

## Round 6 — Code Quality / Ownership / Behavioral Technical

### Q1. What would you refactor first?

**Answer**

The large orchestration service. Separate ingestion, retrieval, ranking, confidence and generation into modules with narrow typed interfaces. This makes ablation and stage-level tests possible.

### Q2. Tell me about a design you would remove.

**Answer**

Any component that cannot show a measurable quality, latency, security or operability gain. For example category routing should be removed for small homogeneous corpora if its recall/latency benefit does not justify complexity.

### Q3. What tradeoff did you make?

**Answer**

Cross-encoder reranking increases latency to improve precision. The right question is not “is it better?” but “how many nDCG points per added p95 millisecond?” I would keep it only if that tradeoff fits the product budget.

### Q4. What did you get wrong initially?

**Answer**

A mature answer: “I initially treated confidence as a threshold on a model score. I later realized the score was not calibrated probability, so the correct solution required labelled data and calibration rather than another magic constant.”

### Q5. What would productionize last?

**Answer**

GraphRAG/episodic memory. They are attractive demos but should come after core retrieval, evaluation, security, observability and temporal correctness.

---

# 29. Interview Trap Questions

## “Isn’t this just RAG plus microservices?”

Good answer:

> Yes, if the system cannot demonstrate that each component changes a measurable failure mode. That is why the project should be presented through ablation, isolation tests, crash recovery and temporal queries rather than its technology list.

## “Why Kafka for a student project?”

> It is overkill if the only goal is asynchronous execution. It becomes justified when I demonstrate durable replay under process failure, consumer lag monitoring, idempotency and horizontal worker semantics. Otherwise a job table or task queue would be simpler.

## “Why Kubernetes?”

> Not because RAG needs Kubernetes. It is useful to demonstrate failure recovery, internal network boundaries and autoscaling. If I cannot show those properties, Docker Compose is the better choice.

## “Why Milvus?”

> Native dense/sparse retrieval and metadata filtering fit the workload. The choice should still be benchmarked against alternatives if production constraints change.

## “Why not PostgreSQL + pgvector?”

> For the current scale, pgvector could simplify the stack significantly. Milvus becomes more compelling when vector workload/scale and native hybrid retrieval justify a separate serving system. I would not pretend a specialized DB is automatically superior.

That answer is excellent because it shows no attachment to tools.

---

# 30. Prioritized Roadmap to “Perfect”

## P0 — Stop dangerous claims

- remove “mathematically proven”
- remove “zero leak” unless test evidence accompanies it
- label target vs implemented architecture

## P0 — Security

- [ ] remove hardcoded JWT secret
- [ ] rotate leaked/dev key
- [ ] OIDC/JWKS
- [ ] strict JWT validation
- [ ] DB-backed scope
- [ ] deny unknown principal
- [ ] required Python scope
- [ ] group filter in Milvus
- [ ] internal-only Core
- [ ] NetworkPolicy
- [ ] tenant/group security matrix tests

## P0 — Evaluation

- [ ] 150–300 question golden set
- [ ] relevant chunk labels
- [ ] ablation runner
- [ ] retrieval metrics
- [ ] refusal metrics
- [ ] citation metrics
- [ ] CI regression gate

## P1 — Retrieval quality

- [ ] validate structure chunker
- [ ] parent-child retrieval
- [ ] contextual enrichment ablation
- [ ] soft routing with global fallback
- [ ] true calibrated confidence
- [ ] reranker latency optimization

## P1 — Durability

- [ ] transactional outbox
- [ ] versioned events
- [ ] idempotent indexing
- [ ] DLQ
- [ ] worker crash test
- [ ] legal state transitions

## P1 — Temporal system

- [ ] transactional supersession
- [ ] point-in-time tests
- [ ] diff query demo
- [ ] cache invalidation on supersede

## P1 — Citations/grounding

- [ ] exact page/span
- [ ] citation marker validation
- [ ] atomic claim split
- [ ] claim-level NLI
- [ ] grounding dashboard

## P2 — Observability

- [ ] OpenTelemetry
- [ ] structured logs
- [ ] Prometheus
- [ ] Grafana
- [ ] query trace explorer
- [ ] corpus coverage

## P2 — Scale

- [ ] load generator
- [ ] 50k / 500k / 1M corpus tests
- [ ] capacity report
- [ ] cost report
- [ ] dual-index migration rehearsal

## P3 — Product

- [ ] SSO
- [ ] admin audit log
- [ ] retention policy
- [ ] deletion
- [ ] connectors
- [ ] version diff UX

---

# 31. Definition of Done for Every Feature

A feature is not done because code exists.

Use this template.

## Feature: ______

### Hypothesis

> We believe X will improve Y because Z.

### Real failure example

Concrete reproducible case.

### Baseline

Measured old result.

### Implementation

Exact mechanism.

### Correctness invariant

Property that must always hold.

### Failure modes

Known ways it breaks.

### Security impact

What new trust/data boundary exists?

### Metrics

Quality / latency / cost.

### Test

Unit + integration + adversarial.

### Ablation result

Before/after.

### Product value

Who pays for this and why?

### Interview sentence

One precise explanation.

This template should be used for every future KatRAG feature.

---

# 32. Recommended Repository Reorganization

```text
/
├── README.md                    # product + demo + measured results
├── ARCHITECTURE.md              # current architecture only
├── ROADMAP.md                   # target architecture
├── SECURITY.md                  # threat model / disclosure
├── BENCHMARKS.md                # reproducible numbers
├── docs/
│   ├── decisions/
│   │   ├── ADR-001-hybrid-search.md
│   │   ├── ADR-002-go-gateway.md
│   │   ├── ADR-003-kafka-ingest.md
│   │   └── ADR-004-temporal-versioning.md
│   ├── interview/
│   │   └── project-defense.md
│   └── architecture/
├── core_backend/
├── live/backend/
├── tests/
│   ├── unit/
│   ├── integration/
│   ├── security/
│   ├── evals/
│   └── load/
└── infra/
```

## Why ADRs?

An interviewer wants:

> Why did you choose this?

An ADR gives:

- context
- alternatives
- decision
- consequences
- reversal criteria

This is more credible than a giant Bible alone.

---

# 33. README Structure for Public Presentation

The public README should be shorter than this playbook.

Use:

1. What KatRAG is
2. The failure modes
3. Current architecture
4. Measured results
5. Temporal demo
6. Security model
7. Retrieval funnel
8. Reproducible local setup
9. Benchmarks
10. Limitations
11. Roadmap

Move the long engineering Bible to docs.

The first screen should not contain a dramatic origin story. Technical readers want signal immediately.

---

# 34. What Would Make This Project Exceptional?

Not another model.

Not more agents.

Not GraphRAG.

The project becomes exceptional if the author can show:

```text
1. A strong baseline.
2. A reproducible evaluation dataset.
3. An ablation table proving why each retrieval stage exists.
4. A real cross-tenant adversarial security suite.
5. A worker crash/replay demo.
6. Temporal document queries across superseded versions.
7. Clickable exact citations.
8. Claim-level grounding measurement.
9. Distributed traces explaining bad answers.
10. An embedding migration with shadow reads and rollback.
```

Those are software-engineering artifacts.

---

# 35. Final Positioning

## To a recruiter

> Built a production-oriented multi-tenant RAG platform with hybrid retrieval, reranking, temporal document history, durable event ingestion and measurable grounding.

## To an ML engineer

> Retrieval funnel with dense/BM25 candidates, RRF, cross-encoder reranking, calibrated abstention and claim-level grounding evaluation.

## To a backend engineer

> Go edge gateway, Python intelligence service, durable event ingestion, idempotency, transactional outbox, scoped caches and versioned contracts.

## To a security engineer

> Retrieval-time authorization, tenant/group isolation tests, deny-by-default scopes, private core service, prompt-injection containment and auditable source binding.

## To a staff engineer

> The important part is not the stack. The system is designed around explicit invariants: no unauthorized evidence crosses the retrieval boundary, early recall loss is measurable, asynchronous work is recoverable, corpus representation is versioned, and every quality optimization has an ablation result.

---

# 36. Final Verdict

**Today:** strong student/portfolio architecture, incomplete production proof.

**Potential:** very strong interview project.

**Commercially interesting wedge:** temporal, auditable enterprise knowledge and secure departmental retrieval.

**Most important next step:** not Kubernetes, not a new LLM, not GraphRAG.

It is:

> **Build the evaluation/security harness and publish reproducible before/after evidence.**

Because once the project can answer:

```text
What failed?
Why did it fail?
What changed?
Did the change improve quality?
What did it cost?
Can another tenant ever see this result?
Can I reproduce the result?
```

it stops being “another RAG project.”

It becomes a serious engineering system.
