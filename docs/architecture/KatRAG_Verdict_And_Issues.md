# KatRAG Engineering Bible — Verdict & GitHub Issues Plan

---

## My Verdict: 9/10 Document, 6/10 Feasibility On Your Machine

The bible is genuinely excellent systems engineering writing. The reasoning is tight, the sequencing is correct (eval before infra, retrieval quality before K8s), and the rejected-designs list alone would save 3 months of wrong turns. Whoever wrote it understands what actually makes RAG fail in production.

**The problem: it was written for a machine that isn't yours.**

Here is the honest hardware reality check:

---

## Hardware Constraints — What Actually Fits

Your machine context: consumer-grade laptop/desktop, ~16GB RAM, RTX 2050 GPU (4GB VRAM), ~500GB SSD.
**Goal:** You explicitly want to use Go, Kafka, and Kubernetes as part of the existing stack to prove enterprise architecture skills, without burdening the RTX 2050.

| Feature                                  | Bible Assumes                | Your Reality               | Verdict                                                                                                                              |
| ---------------------------------------- | ---------------------------- | -------------------------- | ------------------------------------------------------------------------------------------------------------------------------------ |
| BGE-M3 self-hosted (1024-dim, 8192-ctx)  | GPU T4+, 16GB VRAM           | RTX 2050 (4GB VRAM)        | **Do not burden the GPU. Use hosted API (Gemini embeddings) or keep `all-MiniLM-L6-v2` on CPU.**                             |
| Cross-encoder ONNX int8                  | Runs on CPU fine             | OK                         | **Feasible. Run this on CPU.**                                                                                                 |
| Milvus Standalone (10M chunks, 60GB RAM) | 64GB server                  | 16GB total RAM             | **Not feasible at 10M. At your real scale (~50k-200k chunks), standard Milvus Lite or Standalone is fine.**                    |
| SQ8 quantisation                         | 60GB → 22GB RAM             | N/A at your scale          | Skip for now.                                                                                                                        |
| Kafka / Redpanda                         | 8GB RAM baseline             | Tight but possible         | **Mandatory requirement. Use Redpanda (single binary) in K8s/Docker to save overhead.**                                        |
| NLI grounding verifier (DeBERTa-v3)      | ~30ms on CPU                 | OK on CPU, slightly slower | **Feasible. Run it async on CPU — never on the critical path.**                                                               |
| Kubernetes (kind/minikube)               | 8-core, 32GB                 | Borderline but required    | **Mandatory requirement. Run a local `minikube` or `kind` cluster with tight resource limits to avoid starving the host.** |
| Contextual enrichment LLM at ingest      | Cheap model + prompt caching | Gemini free tier           | **Feasible. Use Gemini Flash, cache aggressively, batch 150 chunks per doc per call.**                                         |

### Realistic Scale for KatRAG v1

Forget 10M chunks. That is a production enterprise goal, not a portfolio goal.

**Your actual target:**

- 100-500 documents, ~5k-50k chunks
- 2-5 simulated orgs, 5-10 groups
- k6 load test with 50 virtual users

At that scale, Milvus Standalone with HNSW works perfectly, in-memory Milvus Standalone (not Lite) fits in RAM, and Kafka consumer lag monitoring becomes the "wow" factor, not the scale itself.

---

## What to Cut, What to Keep

### Cut (premature for your hardware/scope):

- BGE-M3 self-hosted → keep `all-MiniLM-L6-v2` on CPU or use Gemini embedding API to save the RTX 2050.
- SQ8 quantisation → irrelevant at 50k chunks
- GraphRAG / episodic memory → v2 feature
- Erasure path (GDPR) → design the schema column, skip the worker

### Keep (Mandatory Architecture Goals):

- **Go API Gateway (Phase 2)** — Pure I/O, solves the JWT/RBAC/Routing boundaries.
- **Redpanda/Kafka Ingestion (Phase 3)** — Solves the BackgroundTasks dropping jobs issue.
- **Kubernetes (Phase 5)** — Deploy the entire KatRAG stack on Minikube/Kind to demonstrate enterprise orchestration skills.

### Keep (High value, hardware-compatible):

- Evaluation harness (Phase 0a) — this is non-negotiable. It is what makes every improvement provable.
- Schema migration (Phase 0b) — `document_versions`, `org_id`, `content_hash`, chunk offsets
- Structure-aware chunking (Phase 1) — biggest quality gain, zero hardware cost
- Contextual enrichment (Phase 1) — one Gemini Flash call per doc, batched
- Sparse into Milvus native (Phase 1) — kills the in-memory BM25 isolation hole
- Soft category routing + centroid fast-path (Phase 1)
- Calibrated confidence gate (Phase 1)
- Citations with page+offset (Phase 1)
- NLI grounding verifier async (Phase 4) — CPU, ~30ms, huge story value
- OpenTelemetry + Grafana on K8s (Phase 5)

---

## GitHub Issues to Create

Copy-paste each block into GitHub Issues. Labels: `phase-0`, `phase-1`, etc.

---

### MILESTONE: Phase 0 — Foundations

**Issue 1: Build the Evaluation Harness (Golden Dataset + per-stage metrics)**

```
Labels: phase-0, evaluation, critical
Body:
Build the golden evaluation dataset and automated eval runner.

Tasks:
- [ ] Write 100-150 questions covering: semantic, exact-id, multi-hop, temporal, unanswerable (20%)
- [ ] Include expected category, relevant_chunk_ids, gold_answer, must_cite_documents per question
- [ ] Implement per-stage metrics: router recall@1/3, retrieval recall@50, nDCG@10, rerank nDCG@5, gate FRR
- [ ] Create make eval (full, ~10 min) and make eval-fast (40q smoke, <90s)
- [ ] Run against CURRENT system to establish the baseline number
- [ ] CI gate: eval-fast on every PR, fail if recall@50 drops >2pts

Acceptance: baseline eval report committed. Every future phase has a before/after number.
```

**Issue 2: Schema Migration — Org Hierarchy, Versioning, Chunk Offsets**

```
Labels: phase-0, schema, critical
Body:
Migrate the PostgreSQL schema to support org-level tenancy, document versioning, and citation offsets.

Tasks:
- [ ] Add organizations table (id, name, plan_tier, status, settings JSONB)
- [ ] Add organization_id FK to users, groups, documents
- [ ] Create document_versions table (version_no, content_hash, valid_from, valid_to, status, authority_score, index_version)
- [ ] Create chunks table (char_start, char_end, page_from, section_path, context_prefix, parent_chunk_id)
- [ ] Add query_traces table for per-query debugging goldmine
- [ ] Write Alembic migration + backfill script for existing data
- [ ] Add organization_id scalar field to Milvus chunk payload
- [ ] Update all milvus_store.py queries to pass org_id as first filter

Acceptance: existing CaRAG features still work. Multi-org isolation is now schema-enforced.
```

---

### MILESTONE: Phase 1 — Retrieval Quality (Highest Value)

**Issue 3: Structure-Aware Chunking + Table Extraction**

```
Labels: phase-1, retrieval-quality
Body:
Replace the fixed 800-char RecursiveCharacterTextSplitter with structure-aware chunking.

Tasks:
- [ ] Integrate PyMuPDF (layout-aware) as default parser, PyPDF as fallback
- [ ] Implement section-boundary splitting (headings, list breaks, table boundaries)
- [ ] Token-budget chunking (~512 tokens, not characters) using the embedding model's tokeniser
- [ ] Never split a table — store each table as its own chunk + a natural-language summary sibling
- [ ] Carry section_path metadata down to every chunk ("3. Leave > 3.2 Sick Leave")
- [ ] Sentence-boundary overlap (~15%)
- [ ] Implement parent-child indexing: embed 256-token child, return 1024-token parent to LLM
- [ ] Populate parent_chunk_id column

Acceptance: eval recall@50 improves vs. baseline on the golden set.
```

**Issue 4: Contextual Chunk Enrichment**

```
Labels: phase-1, retrieval-quality
Body:
Prepend LLM-generated situating context to each chunk before embedding.

Tasks:
- [ ] Implement batch contextual enrichment at ingest time (one cached Gemini call per doc)
- [ ] Prompt: "Here is the document: <doc>. Here is a chunk: <chunk>. Give a 1-2 sentence context."
- [ ] Store in context_prefix column; embed (context_prefix + "\n\n" + content); display content only
- [ ] Use Gemini Flash (cheapest). Use prompt caching for the document body across all chunks.
- [ ] Batch chunks per document to minimise API calls
- [ ] Gate behind bypass_llm flag for development speed

Acceptance: eval faithfulness score improves vs baseline.
```

**Issue 5: Move BM25 into Milvus Native Sparse (Kill rank_bm25)**

```
Labels: phase-1, retrieval-quality, security
Body:
Replace in-memory rank_bm25 with Milvus 2.5+ native sparse float vectors. This is both a scaling fix and a security fix (BM25 currently filters in app memory, violating the isolation principle).

Tasks:
- [ ] Upgrade Milvus to 2.5+
- [ ] Add sparse SPARSE_FLOAT_VECTOR field to the collection schema
- [ ] Enable BM25 function on the content field in Milvus
- [ ] Replace two-call (dense + BM25) retrieval with single client.hybrid_search() call
- [ ] Use Milvus RRFRanker(k=60) — remove custom Python RRF code
- [ ] Scope expression (org_id + group_id + is_current) applied identically to both dense and sparse arms
- [ ] Delete bm25_store.py

Acceptance: eval recall@50 unchanged or better. No rank_bm25 import anywhere in the codebase.
```

**Issue 6: Soft Multi-Category Routing + Centroid Fast-Path**

```
Labels: phase-1, retrieval-quality
Body:
Fix the hard category gate — the single most dangerous component in the current system. A misroute produces a confident, cited, wrong answer with no error signal anywhere.

Tasks:
- [ ] Maintain a centroid vector per category (running mean, recomputed nightly)
- [ ] Replace LLM routing call on every query with centroid cosine (sub-millisecond, free)
- [ ] Fall back to LLM only when top centroid similarity < 0.4 or margin < 0.1
- [ ] Route to top-3 categories, not 1
- [ ] Implement soft routing: retrieve 80 from routed categories UNION 40 from global, apply 1.25x score boost to routed results during RRF — do NOT hard-filter
- [ ] If router confidence is low (flat distribution), skip routing and search globally
- [ ] Add router recall@1 and recall@3 to eval suite
- [ ] Alert if recall@3 drops below 0.95

Acceptance: router recall@3 >= 0.95 on golden set. False-answer rate from misroutes measurably reduced.
```

**Issue 7: Calibrated Composite Confidence Gate**

```
Labels: phase-1, retrieval-quality
Body:
Replace the single hardcoded cross-encoder logit threshold with a calibrated, multi-signal composite confidence score.

Tasks:
- [ ] Collect labelled (query, chunk, relevant?) pairs from the golden eval set
- [ ] Fit Platt scaling (logistic regression on raw cross-encoder score) to get P(relevant|score)
- [ ] Implement composite C = w_r*relevance + w_a*agreement + w_f*freshness + w_u*authority + w_m*margin
- [ ] Learn weights via logistic regression against eval labels (scikit-learn, 20 lines)
- [ ] Implement three outcomes: ANSWER / ANSWER_HEDGED / REFUSE
- [ ] On REFUSE: return near-miss document titles and which categories were searched
- [ ] Store thresholds in organizations.settings JSONB (per-org overridable)
- [ ] Track and dashboard false-refusal rate alongside hallucination rate — report both always

Acceptance: Gate FRR <= 8% on eval set. Calibrated score replaces raw logit everywhere.
```

**Issue 8: Citations with Page Number + Character Offset**

```
Labels: phase-1, retrieval-quality
Body:
Surface source citations with page and character-level offsets so grounded answers are verifiable.

Tasks:
- [ ] Store char_start, char_end, page_from per chunk at ingestion time (NOT derived post-hoc)
- [ ] Update generation prompt: "Cite every factual claim with [S1],[S2]. Omit unsupported claims."
- [ ] Post-process response: parse [Sn] markers, map to chunk_id, strip invented markers
- [ ] Return structured: {text, citations: [{marker, chunk_id, doc_title, page, char_start, char_end}]}
- [ ] Update demo UI to show citations as clickable footnotes

Acceptance: Every answer includes at least one verifiable citation. No invented [Sn] markers in responses.
```

---

### MILESTONE: Phase 2 — Go API Gateway

**Issue 9: Go API Gateway (JWT + RBAC + Scope Resolution)**

```
Labels: phase-2, go-layer
Body:
Build the Go gateway as the single internet-facing entry point. Core Engine Python service becomes internal only.

Tasks:
- [ ] Go service with JWT validation (HS256 → plan RS256 migration)
- [ ] Scope chain resolution: user → org → groups → effective_doc_scope, cached in Redis (60s TTL)
- [ ] RBAC middleware: role-capability matrix as a literal policy struct
- [ ] Per-org token-bucket rate limiting (Redis)
- [ ] HTTP reverse proxy to Core Engine (Phase 2), upgrade to gRPC in Phase 3
- [ ] Attach scope as headers before forwarding; Core Engine trusts these completely, never re-parses JWT
- [ ] test_black_box_boundary: calling Core Engine directly with hand-built scope = identical results to gateway path

Acceptance: eval scores IDENTICAL before and after introducing the gateway. Proves no retrieval logic leaked into Go.
```

---

### MILESTONE: Phase 3 — Kafka Ingestion Decoupling

**Issue 10: Redpanda + Async Ingestion Pipeline**

```
Labels: phase-3, kafka
Body:
Move document ingestion from BackgroundTasks (in-process, lost on restart) to Redpanda-backed durable queue.

Tasks:
- [ ] Deploy Redpanda in Docker Compose (single binary, no ZooKeeper)
- [ ] Topics: doc.uploaded, doc.chunked, doc.indexed, doc.failed, query.audit — all keyed by org_id
- [ ] Gateway: on upload, write object store + DB row first, THEN produce doc.uploaded to Kafka
- [ ] Python worker: consume doc.uploaded, run full ingestion pipeline, emit progress events
- [ ] Idempotent consumer: key on content_hash, no-op on duplicate
- [ ] DLQ: after N retries, route to doc.failed.dlq — never block the partition
- [ ] Go broadcaster: consume doc.chunked / doc.indexed / doc.failed → fan-out to group WebSockets
- [ ] WS reconnect: replay events from last-seen Kafka offset on reconnect
- [ ] Alert on consumer lag > 5 min
- [ ] Load test: measure API latency under ingest load BEFORE and AFTER — get a real number

Acceptance: Pod kill during ingest = job resumes from Kafka on restart. Zero lost ingestions.
```

---

### MILESTONE: Phase 4 — Grounding & Memory

**Issue 11: NLI Grounding Verifier**

```
Labels: phase-4, grounding, hallucination
Body:
Implement an async grounding verifier that measures whether generated claims are supported by cited sources.

Tasks:
- [ ] Load a DeBERTa-v3-base MNLI checkpoint locally (CPU, ~30ms per claim)
- [ ] After generation: split answer into atomic claims (sentence-level)
- [ ] For each claim, run NLI against its cited chunks: {entailment, neutral, contradiction}
- [ ] grounding_score = fraction of claims with entailment > 0.7
- [ ] Persist to query_traces.grounding_score
- [ ] Async by default (does not block response). If score < 0.6, flag trace for review.
- [ ] Show grounding score distribution on the quality dashboard

Acceptance: grounding_score populated on every query. p50 grounding_score >= 0.85 on eval set.
```

**Issue 12: Document Versioning + Temporal Queries**

```
Labels: phase-4, memory
Body:
Implement supersession so re-uploading a document creates a new version rather than overwriting.

Tasks:
- [ ] On re-upload: compute content_hash. If identical, return 200 {status: duplicate}. If new, create version N+1.
- [ ] Set version N: valid_to = now, status = superseded. In Milvus: set is_current=false on old vectors.
- [ ] Default retrieval: filter is_current == true
- [ ] Temporal query: if as_of is set, filter valid_from_ts <= as_of AND valid_to_ts > as_of
- [ ] Emit doc.superseded Kafka event → cache invalidator
- [ ] Demo: "what did the leave policy say in March?" returns the right version

Acceptance: Re-upload works. Superseded versions are reachable via as_of but not by default retrieval.
```

---

### MILESTONE: Phase 5 — Observability

**Issue 13: OpenTelemetry Tracing + Quality Dashboards**

```
Labels: phase-5, observability
Body:
End-to-end distributed tracing from gateway through Core Engine, feeding Grafana dashboards.

Tasks:
- [ ] Add OpenTelemetry SDK to Go gateway and Python Core Engine
- [ ] One trace per query: spans for auth, cache lookup, routing, hybrid_search, rerank, gate, generation, grounding
- [ ] Every span carries org_id
- [ ] Prometheus metrics: per-stage latency histograms, cache hit rates, Kafka consumer lag
- [ ] Grafana dashboards: Quality (eval scores over time, grounding dist, refusal rate), Performance (stage latency, cache), Corpus health (retrieval coverage)
- [ ] Retrieval coverage dashboard: documents never retrieved in 30 days = "functionally forgotten" — the metric that most directly measures the product thesis

Acceptance: Can answer "why did it say that?" for any query from the past 7 days using traces.
```

---

## Branch Strategy Going Forward

Old branches (feature/categorical-routing, feature/m3-websocket, etc.) are being deleted — they were CaRAG-era work that is now on main.

New branch convention:

```
phase-0/eval-harness
phase-0/schema-migration
phase-1/chunking
phase-1/bm25-milvus-sparse
phase-1/category-routing
phase-1/confidence-gate
phase-1/citations
phase-2/go-gateway
phase-3/kafka-ingestion
phase-4/grounding-verifier
phase-4/versioning
phase-5/observability
```

One branch per GitHub issue. Merge to main when the acceptance criteria in the issue passes eval-fast.
