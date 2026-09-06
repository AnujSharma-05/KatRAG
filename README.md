# KatRAG v1: Enterprise Categorical RAG Architecture

KatRAG is an enterprise-grade, multi-tenant Retrieval-Augmented Generation (RAG) system built to strictly adhere to the first principles of asynchronous data streaming, hallucination prevention, and rigorous data isolation. 

## The Pitch: Enterprise-Ready RAG
1. **Zero-Data Leakage:** End-to-end multi-tenant isolation. From the Go JWT Middleware down to the Milvus partition keys and Scoped Semantic Caches, cross-tenant data bleed is mathematically eliminated.
2. **Hallucination Prevention:** The generative engine is shielded by a **Calibrated Confidence Gate** that intercepts poor retrievals. Post-generation, an independent **DeBERTa-v3 NLI Grounding Verifier** mathematically measures entailment, ensuring hallucination is a measured metric, not a guess.
3. **Temporal Memory ("Never Forgets"):** Append-only document versioning backed by PostgreSQL and Milvus logical deprecation. The system can execute precise point-in-time queries (e.g., *"What was the parental leave policy as of March 2024?"*) without erasing historical intelligence.

---

## The Architecture: Event-Driven & Decoupled

KatRAG operates as a 2-layer decoupled system, communicating entirely through Redpanda (Kafka) and MinIO (S3):

1. **Go API Gateway (Port 8080):** 
   - Owns the network boundary, handles JWT Auth + RBAC, streams file uploads directly to MinIO, and publishes doc.uploaded events to Redpanda.
   - Hosts the WebSocket Broadcaster to push real-time indexing status to clients.
2. **Python Headless Workers:**
   - Idempotent Kafka consumers reading doc.uploaded. They execute heavy ML ingestion (Document Parsing -> Contextual Enrichment -> Embedding -> Milvus) without blocking the API layer.
3. **Python Core Engine (Port 8000):**
   - The heavy synchronous intelligence layer serving nswer_question queries.

`mermaid
graph LR
    Client -->|HTTPS| Go_Gateway
    Go_Gateway -->|Upload| MinIO
    Go_Gateway -->|doc.uploaded| Redpanda
    Redpanda -->|Poll| Python_Worker
    Python_Worker -->|Embed| Milvus
    Client -->|Query| Go_Gateway -->|gRPC/HTTP| Python_Core
`

---

## The Retrieval Pipeline (The Intelligence Core)

KatRAG employs a massive, multi-stage retrieval funnel engineered for maximum recall and deterministic precision:

1. **Scoped Semantic Cache:** Dual-layer Exact (SHA256) & Semantic (Cosine >= 0.97) hit resolution.
2. **Soft Multi-Category Routing:** Queries are dynamically routed to the top-3 most likely domain categories, eliminating the "silent recall collapse" of hard gating.
3. **Milvus Native Hybrid Search:** Concurrent Dense Embedding Search + Sparse BM25 Search.
4. **Reciprocal Rank Fusion (RRF):** C++ engine-level merging of Dense and Sparse vectors.
5. **Cross-Encoder Reranking:** Re-scores the top hits using a pairwise Transformer.
6. **Calibrated Confidence Gate:** Sigmoid-normalized probability intercepts the flow (ANSWER vs. HEDGED vs. REFUSE) before tokens are wasted on the LLM.
7. **Generation & Citations:** LLM generates a response accompanied by exact database chunk origins, page numbers, and character offsets.
8. **NLI Grounding:** A local DeBERTa-v3 NLI model runs an entailment check ([Context, Answer]) to score the final output.

---

## Quickstart

### Prerequisites
- Docker & Docker Compose
- 16GB RAM + Modern multi-core CPU (or CUDA GPU)

### Booting the Topology

The system is containerized into a frictionless local development topology.

`ash
# 1. Navigate to the Docker compose directory
cd core_backend/Docker

# 2. Boot the infrastructure (Postgres, MinIO, Redpanda, etcd, Milvus) + Microservices
docker compose up -d

# 3. Verify all 7 containers are healthy
docker ps
`

**Service Ports:**
- **Go API Gateway:** http://localhost:8080 (Primary Front Door)
- **Python Core API:** http://localhost:8000
- **MinIO Console:** http://localhost:9001 (user/pass: minioadmin/minioadmin123)
- **PostgreSQL:** localhost:5432

---

*KatRAG v1 is architecturally locked and feature complete.*
