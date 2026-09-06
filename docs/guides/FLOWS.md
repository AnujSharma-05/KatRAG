# KatRAG v1 — Authoritative Flow Diagrams (Source of Truth)

> **Policy:** This document supersedes all previous flow descriptions.
> Update here first, then update code.
> Every label maps 1-to-1 to a real function, route, or table in the codebase.

---

## Section 1: System Index & Error Matrix

### Error Reference

| Error | Code | Service | Description |
|---|---|---|---|
| Successful Operation | 200 | Go Gateway / Python Core | Query executed or operation succeeded |
| Ingestion Queued | 202 | Go Gateway | Document uploaded, saved to MinIO, and `doc.uploaded` published to Kafka |
| Bad Request | 400 | Go Gateway | Invalid input payload or missing fields |
| Unauthorized / Bad JWT | 401 | Go Gateway | Expired/malformed JWT, signature mismatch, missing token |
| Forbidden | 403 | Go Gateway | User is not a member of the requested group |
| Not Found | 404 | Go Gateway / Python Core | Group or document does not exist |
| Rate Limited (Fallback) | 429 | Python Core | LLM API rate limit exceeded (handled gracefully via fallback if configured) |
| Service Unavailable | 503 | Go Gateway | Python Core Engine is unreachable or crashed |

---

## Section 2: Diagram 1 — Asynchronous Ingestion & Document Versioning

**WHY this exists:** Synchronous FastAPI background tasks drop data on pod restarts. This event-driven ingestion loop decouples file upload from heavy ML processing. Go handles the network and storage boundary (MinIO), and Redpanda guarantees delivery to the headless Python worker.

```mermaid
sequenceDiagram
    autonumber
    actor Client
    participant GW  as Go Gateway (live/backend)
    participant S3  as MinIO S3
    participant PG  as PostgreSQL
    participant RP  as Redpanda Broker
    participant WRK as Python Worker (core_backend)
    participant MV  as Milvus 2.5
    participant WS  as Go WebSocket Broadcaster

    %% ══════════════════════════════════════════════════════════
    %% INGESTION INITIATION (Go Gateway)
    %% ══════════════════════════════════════════════════════════
    Client->>GW: POST /groups/{id}/documents (JWT)
    GW->>GW: Authenticate JWT & Extract organization_id
    GW->>PG: Check Group Membership

    GW->>S3: PutObject (Stream multipart to 'katrag-docs' bucket)
    
    GW->>PG: Check if filename exists in group
    alt Document Supersession (Exists)
        GW->>PG: UPDATE documents SET is_current = false, valid_to = now()
        GW->>RP: Produce doc.superseded (Key: organization_id)
    end
    
    GW->>PG: INSERT documents (status='pending', is_current=true, valid_from=now())
    GW->>RP: Produce doc.uploaded (Key: organization_id)
    GW-->>Client: 202 Accepted (Upload complete, processing queued)

    %% ══════════════════════════════════════════════════════════
    %% ASYNC ML PIPELINE (Python Worker)
    %% ══════════════════════════════════════════════════════════
    RP-->>WRK: Consume doc.uploaded (Idempotent poll)
    WRK->>PG: Verify status='pending' (Idempotency guard)
    
    WRK->>S3: GetObject (Download PDF)
    WRK->>WRK: PyMuPDF Text Extraction & Structure-Aware Chunking
    WRK->>WRK: Anthropic Contextual Enrichment (LLM prefixing)
    WRK->>WRK: Generate Dense Embeddings (all-MiniLM-L6-v2) & Sparse term maps

    WRK->>MV: Insert chunks (HNSW dense + BM25 sparse + organization_id scalar)

    alt Handling doc.superseded
        WRK->>MV: milvus_store.deprecate_document_vectors (Mutate old chunk scalars to is_current=false)
    end

    WRK->>WRK: cache.invalidate_scope(org_id, group_id)
    WRK->>PG: UPDATE documents SET status='indexed'
    WRK->>RP: Produce doc.indexed (Key: organization_id)

    %% ══════════════════════════════════════════════════════════
    %% BROADCAST COMPLETION
    %% ══════════════════════════════════════════════════════════
    RP-->>WS: Consume doc.indexed
    WS->>WS: Match active WebSocket connections for group_id
    WS-->>Client: Push WebSocket Event (Document Ready)
```

---

## Section 3: Diagram 2 — Retrieval, Scoped Caching & Grounded Generation

**WHY this exists:** A multi-stage retrieval funnel that mathematically guarantees isolation across tenants while protecting the generative LLM from hallucination via Cross-Encoder gating and NLI entailment scoring.

```mermaid
sequenceDiagram
    autonumber
    actor Client
    participant GW  as Go Gateway
    participant CA  as ScopedQueryCache
    participant PY  as Python Core API (services.py)
    participant MV  as Milvus 2.5
    participant CX  as Cross-Encoder / Gate
    participant LLM as Gemini LLM
    participant NLI as DeBERTa-v3 NLI Verifier
    participant PG  as PostgreSQL (query_traces)

    %% ══════════════════════════════════════════════════════════
    %% REQUEST AND CACHE RESOLUTION
    %% ══════════════════════════════════════════════════════════
    Client->>GW: POST /groups/{id}/chat (JWT, text, optional as_of)
    GW->>GW: Validate Token, Inject X-Scope-Org & X-Scope-Group headers
    GW->>PY: Proxy Request

    PY->>PY: start_time = time.time()
    PY->>CA: cache.get(org_id, group_id, query, as_of)
    
    alt Cache Hit (Exact or Semantic cosine >= 0.97)
        CA-->>PY: Cached Payload
        PY-->>GW: Return Cached Response
        GW-->>Client: 200 OK
    end

    %% ══════════════════════════════════════════════════════════
    %% HYBRID RETRIEVAL AND CONFIDENCE GATE
    %% ══════════════════════════════════════════════════════════
    alt Temporal Query (as_of provided)
        PY->>PG: resolve_active_document_ids()
    end

    PY->>MV: Cosine similarity vs category centroids (Soft Router)
    PY->>MV: Hybrid Search (Dense + Native Sparse BM25)
    Note over PY,MV: Scalar Filter: organization_id == org_id AND (is_current == true OR document_id IN [...])
    MV-->>PY: Candidates
    PY->>PY: RRF (Reciprocal Rank Fusion) + 1.25x soft-route category multiplier
    
    PY->>CX: ms-marco-MiniLM-L-6-v2 re-ranks top 15
    CX->>CX: Normalize top logit to probability C (Confidence Gate)

    alt C < 0.35 (REFUSE)
        PY-->>GW: Return near-miss explanation (No LLM Call)
    else 0.35 <= C < 0.70 (HEDGED)
        PY->>PY: Mark state as HEDGED
    else C >= 0.70 (ANSWER)
        PY->>PY: Mark state as ANSWER
    end

    %% ══════════════════════════════════════════════════════════
    %% SYNTHESIS & NLI GROUNDING
    %% ══════════════════════════════════════════════════════════
    opt Not REFUSED
        PY->>LLM: Synthesize answer with structured provenance (document_id, page_from, offsets)
        LLM-->>PY: Generated Answer
        PY->>NLI: cross-encoder/nli-deberta-v3-small check([Context, Answer])
        NLI-->>PY: Entailment Probability (grounding_score)
        
        PY->>CA: cache.set(org_id, group_id, payload)
    end

    PY->>PG: INSERT query_traces (latency_ms, gate_decision, grounding_score, chunk_ids) [try/except safe]
    PY-->>GW: Return payload
    GW-->>Client: 200 OK
```

---

## Section 4: Diagram 3 — Multi-Tenant Security & Cache Isolation Boundary

**WHY this exists:** A semantic cache that keys solely on query text is a P0 vulnerability in a multi-tenant system. KatRAG strictly prefixes keys, ensuring Tenant A and Tenant B never cross-pollinate.

```mermaid
flowchart TD
    subgraph Multi-Tenant Security Boundary
        Q1["Tenant A Query:<br/>'What is the return policy?'"] --> RouterA[Cache Router]
        Q2["Tenant B Query:<br/>'What is the return policy?'"] --> RouterB[Cache Router]

        RouterA --> KeyA["Generated Key:<br/>katrag:{org_A}:{group_1}:exact:{sha256}"]
        RouterB --> KeyB["Generated Key:<br/>katrag:{org_B}:{group_1}:exact:{sha256}"]
        
        KeyA --> CacheA[(Tenant A Cache Partition)]
        KeyB --> CacheB[(Tenant B Cache Partition)]
        
        CacheA -- HIT --> AnswerA["Return Policy A"]
        CacheB -- MISS --> EngineB["Python Core Engine"]
        
        EngineB --> MilvusSearch["Milvus Hybrid Search"]
        MilvusSearch -- "Defense in Depth" --> Filter["Enforce Filter:<br/>organization_id == {org_B}"]
        Filter --> AnswerB["Return Policy B"]
    end
```
