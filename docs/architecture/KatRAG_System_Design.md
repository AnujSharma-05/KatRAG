# CategoRAG — System Design v2
### Black-box Core Engine · Multi-Tenant Adapter · Orchestration Layer

---

## 0. Design Principles (non-negotiable)

1. **Python owns retrieval intelligence. Forever.** The Core Engine (hybrid search, cross-encoder, confidence gate) is never rewritten. It is treated as a sealed component with a contract, the same way you'd treat a licensed third-party ML service.
2. **Go owns the request boundary, not the logic.** Every Go service in this design is I/O-bound: routing, auth, fan-out, aggregation, streaming. None of them make a retrieval decision.
3. **Kafka owns anything that shouldn't block a request.** Ingestion, indexing, audit logging, usage metering, cross-group event propagation.
4. **Kubernetes owns lifecycle, not architecture.** It doesn't change what your services do — it changes how they're deployed, scaled, and recovered.
5. **The hierarchy is a data-scoping problem before it's an auth problem.** Get the tenancy model right in Postgres/Milvus schema first — RBAC is just the enforcement layer on top of scoping that already has to exist in every query.

---

## 1. Tenancy Hierarchy → Data Model

Your four roles map directly onto a scoping chain. Every retrieval query and every document write must carry this full chain, not just a `group_id`.

```
Super Admin
  └── Organization (Admin)          e.g. "Jio", "Adani"
        └── Group (Group Admin)     e.g. "Legal", "Engineering"
              └── Member
```

### Schema additions to what CaRAG already has

```
organizations
  id, name, plan_tier, created_at, status (active/suspended)

users
  id, email, hashed_password, role (super_admin | org_admin | group_admin | member)
  organization_id (nullable for super_admin)

groups
  id, organization_id (FK), name, retention_policy, created_at

group_members
  user_id, group_id, role_in_group (group_admin | member)

documents
  id, organization_id (FK), group_id (FK), uploaded_by, status, content_hash
```

**Critical rule carried over from CaRAG's existing design, extended one level:** every vector payload in Milvus and every row touched by a query gets **both** `organization_id` and `group_id` as scalar metadata. Org boundary is checked first (cheapest, coarsest filter), group boundary second. This is the same "database-enforced isolation, not application-level filtering" principle your report already proved out — you're just adding a second nesting level, not a new concept.

**Content hashing at ingest** (borrowed from the 10M-doc scaling checklist): every document gets a `content_hash` so re-uploads are idempotent no-ops instead of duplicate vectors. You don't have this yet — add it now, before volume makes it painful to retrofit.

### Role → capability matrix

| Action | Super Admin | Org Admin | Group Admin | Member |
|---|---|---|---|---|
| Create/suspend organizations | ✅ | ❌ | ❌ | ❌ |
| Create groups within org | ✅ | ✅ | ❌ | ❌ |
| Add/remove members | ✅ | ✅ (any group) | ✅ (own group) | ❌ |
| Upload documents | ✅ | ✅ | ✅ | Configurable per group |
| Query / chat | ✅ (any scope) | ✅ (org scope) | ✅ (group scope) | ✅ (group scope) |
| View cross-group analytics | ✅ | ✅ (own org) | ❌ | ❌ |

This table becomes literal middleware in the Go adapter layer — a request either passes the scope check or gets a 403, before it ever reaches the Core Engine.

---

## 2. High-Level Architecture

```
                         ┌─────────────────────┐
                         │   Web / Mobile Client │
                         └──────────┬───────────┘
                                    │ HTTPS/WSS
                         ┌──────────▼───────────┐
                         │   Go API Gateway       │  ← NEW: Go service #1
                         │  - JWT validation      │
                         │  - RBAC scope checks   │
                         │  - Rate limiting       │
                         │  - Request routing     │
                         └──────────┬───────────┘
                                    │
                ┌───────────────────┼───────────────────┐
                │                   │                   │
     ┌──────────▼─────────┐  ┌──────▼───────┐  ┌────────▼────────┐
     │  Go Ingestion       │  │  Core RAG     │  │  Go WebSocket    │
     │  Producer            │  │  Engine       │  │  Broadcaster     │
     │  (upload → Kafka)     │  │  (Python,     │  │  (Go service #2)│
     └──────────┬─────────┘  │   BLACK BOX)  │  └────────┬────────┘
                │             └──────▲───────┘           │
     ┌──────────▼─────────┐          │                   │
     │   Kafka             │          │           events  │
     │  topics:             │          │                   │
     │  - doc.uploaded       ├──────────┘                   │
     │  - doc.chunked         │                              │
     │  - doc.indexed          │◄─────────────────────────────┘
     │  - query.audit            │
     └──────────┬─────────┘
                │ consumed by
     ┌──────────▼─────────┐
     │  Python Ingestion    │   ← unchanged CaRAG ingestion logic,
     │  Worker (existing     │      now triggered by Kafka message
     │  chunking/embedding)   │      instead of BackgroundTasks
     └──────────┬─────────┘
                │
     ┌──────────▼─────────┐     ┌──────────────┐     ┌──────────────┐
     │  Milvus (vectors)    │     │  PostgreSQL   │     │  Gemini API   │
     │  org_id + group_id     │     │  (identity,    │     │  (generation) │
     │  scalar metadata        │     │   metadata)    │     │               │
     └────────────────────┘     └──────────────┘     └──────────────┘

All of the above running as Kubernetes Deployments/StatefulSets,
with HPA on the Go gateway and the Python retrieval pods independently.
```

### What's genuinely new vs. what's relabeled

| Component | Status |
|---|---|
| Core Engine (hybrid search, cross-encoder, confidence gate) | **Unchanged.** Still Python/FastAPI, still your report's Chapter 6. |
| Live Adapter (JWT, groups, WebSocket) | **Evolves into the Go API Gateway.** Same responsibilities, new language, new tenancy level added. |
| Milvus / PostgreSQL | **Unchanged**, schema extended one level (org → group). |
| Kafka | **New.** Sits between ingestion and the Python worker. |
| K8s | **New.** Replaces "local Dockerized" deployment. |

This is the honest version of the story: two genuinely new pieces of infrastructure (Kafka, K8s), one language migration that's scoped to exactly what needs to be fast (the gateway), zero risk to the retrieval quality work that's your report's actual thesis.

---

## 3. The Go Layer — exactly two services, not a rewrite

**Service 1: API Gateway**
- Terminates JWT, resolves the org/group scope chain, attaches it to the request as headers before forwarding to the Python Core Engine.
- This is where goroutines earn their keep: hundreds of concurrent chat requests, each just waiting on the Python backend — Go handles that fan-out far more cheaply than an equivalent process-pool approach.
- Rate limiting per org (so one tenant's traffic spike doesn't starve another — this becomes a real, demonstrable multi-tenancy concern once you have 2+ orgs on shared infra).

**Service 2: WebSocket Broadcaster**
- Already conceptually a Go problem — you're pushing many small events to many open connections, which is exactly the concurrency model Go was built for, and exactly what your CaRAG report flagged as needing careful async handling in Python.
- Consumes Kafka topics (`doc.indexed`, `doc.failed`) and fans out to the right group's open sockets.

That's it. Resist the urge to add a third Go service just to use more Go. If a future bottleneck shows up in profiling and it's I/O-bound, it's a Go candidate. If it's ML/retrieval-bound, it stays in Python — full stop.

---

## 4. Kafka Topics

| Topic | Producer | Consumer | Purpose |
|---|---|---|---|
| `doc.uploaded` | Go Gateway | Python ingestion worker | Decouples upload response from processing — fixes the event-loop-starvation issue your report documents |
| `doc.chunked` | Python worker | Go Broadcaster | Progress event for WebSocket clients |
| `doc.indexed` | Python worker | Go Broadcaster, analytics consumer | Final "ready" event |
| `doc.failed` | Python worker | Go Broadcaster | Failure notification, retry trigger |
| `query.audit` | Go Gateway | Analytics/compliance consumer | Every query logged async — needed for the citation-traceability requirement below |

Partitioning key: `organization_id`. This guarantees ordering within a tenant's event stream without forcing global ordering — and it's a clean story for "why partition this way" if anyone asks in an interview.

---

## 5. Retrieval-at-Scale Roadmap (the actual heart of the project)

You're right that infra is the adoption vision, but retrieval quality at scale is the vision. Mapping the 10M-doc checklist against what CaRAG already has:

| Stage | CaRAG status | Gap to close |
|---|---|---|
| 1. Ingest & normalize | Partial — PyPDF extraction exists | Add content-hash idempotency, Unicode normalization, per-org language detection |
| 2. Hybrid retrieval (BM25 + embeddings) | **Done** — RRF fusion already implemented | Tune fusion weight α per document category instead of one global constant |
| 3. ANN + reranking | **Done** — HNSW + cross-encoder | None significant — this is your strongest stage |
| 4. Source confidence scoring | Partial — single threshold gate exists | Extend to the weighted formula (retrieval + freshness + authority + agreement), not just top cross-encoder score |
| 5. Constrained generation | Partial — implicit in prompting | Make the "cite or refuse" contract explicit and enforced in the prompt template |
| 6. Citation-backed responses | Partial — sources are retrieved but not surfaced with page/offset | Add page number + character offset storage per chunk; return inline `[Source N]` citations |
| 7. Hallucination fallback layer | **Missing** | This is your best next differentiator — an async post-generation grounding check |
| 8. Continuous evals | **Missing** | Log context relevance / faithfulness / answer relevance per query |
| 9. Caching | **Missing** | Exact-match query cache is a cheap win once multi-org traffic exists |
| 10. Observability | Partial — WebSocket events exist, no tracing | OpenTelemetry spans per retrieval stage, feeding Prometheus/Grafana on K8s |

**This table is your actual roadmap**, not the Go/Kafka/K8s migration. The infra work makes rows 1 and 9 possible at real scale; it doesn't touch rows 2–8, which is where the retrieval-quality story lives. If you have to choose where to spend limited time, rows 4, 6, and 7 (confidence scoring, citations, hallucination fallback) are higher-value for a "RAG that never forgets" narrative than any amount of additional infra polish.

---

## 6. Build Order

**Phase 0 — Schema & scoping (1 week)**
Extend Postgres/Milvus for the org→group hierarchy. No new infra yet. This has to be right before anything else is built on top of it.

**Phase 1 — Go Gateway (2–3 weeks)**
Build the gateway in front of the *existing* Python Core Engine, unchanged. Prove JWT + RBAC scope enforcement works end-to-end. This alone is a legitimate, demoable milestone.

**Phase 2 — Kafka ingestion decoupling (2–3 weeks)**
Move upload → chunk → embed → index behind a queue. Python worker logic barely changes — it just gets triggered differently. Load test before/after to get a real latency number for your report.

**Phase 3 — Retrieval quality hardening (2–3 weeks, can overlap with Phase 2)**
Confidence scoring formula, citation offsets, hallucination fallback pass. This is where the "zero hallucination at scale" claim actually gets earned.

**Phase 4 — Kubernetes (2 weeks)**
Containerize everything from Phases 0–3, write real manifests (resource limits, HPA, liveness probes), local cluster via kind/minikube.

**Phase 5 — Evals + observability (ongoing)**
OpenTelemetry tracing, eval logging, caching. This is the layer that turns "it works in a demo" into "here's the dashboard proving it works under load," which is the single most convincing thing you can show a technical recruiter.

---

## 7. What I'd push back on if you tried to skip

- Skipping Phase 0 to jump straight to Kafka/K8s — you'll be retrofitting tenancy into a system that's already got queues and pods, which is strictly harder.
- Treating Phase 4 (K8s) as more important than Phase 3 (retrieval hardening) — orchestration is legible to any recruiter skimming a resume, but retrieval quality is the part that survives a real technical interview question.
- Adding a third Go service "for symmetry" — every Go service should exist because something was I/O-bound and slow, not because the stack diagram looks incomplete without it.
