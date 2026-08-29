# CaRAG Live — Project Plan (v2 — Groups Edition)

> **Goal:** Evolve CaRAG from a stateless single-user FastAPI backend into a multi-user, group-scoped, real-time agentic platform.
> **Three focus areas:** OpenClaw (deep, dev-level), WebSockets, REST APIs.
> **Rule:** No new AI/RAG complexity. The intelligence is already built. This plan is about the platform layer around it.

---

## Architecture in one line

```
Telegram → OpenClaw plugin → CaRAG Live REST/WS → CaRAG engine (scoped to group)
```

---

## Key design decisions (locked)

| Decision | Choice |
|---|---|
| Group membership | Open — anyone can invite anyone. Admin later. |
| Document CRUD | Any group member can do anything |
| Group selection | Smart — skip picker if user has 1 group, show inline keyboard if many |
| Active group memory | Sticky + 24h timeout (like Slack workspace switching) |
| Project structure | Monorepo — `live/` folder inside existing CaRAG repo |

---

## How to read this plan

Each milestone is self-contained — you can stop after any one and have something working.
Each task has: **what you build**, **what you learn**, **acceptance check**.

---

## Milestone 0 — Monorepo Setup

> Get the folder structure right before writing a single feature line.

### Task 0.1 — Create the `live/` layer inside CaRAG repo

**What you build:**
```
CaRAG/
├── backend/                     ← existing CaRAG (untouched forever)
│   └── src/...
├── live/
│   ├── backend/                 ← CaRAG Live API (Python, FastAPI)
│   │   ├── src/
│   │   │   ├── auth/            ← JWT auth, users
│   │   │   ├── groups/          ← group + membership logic
│   │   │   ├── documents/       ← group-scoped document routes
│   │   │   ├── ws/              ← WebSocket manager + handlers
│   │   │   └── main.py          ← mounts all routers
│   │   └── requirements.txt
│   ├── openclaw-plugin/         ← TypeScript OpenClaw plugin
│   │   ├── src/
│   │   │   ├── index.ts         ← plugin entry point
│   │   │   ├── intent.ts        ← LLM intent classifier
│   │   │   ├── groupCtx.ts      ← group context + memory
│   │   │   └── carag.ts         ← REST + WS client for CaRAG Live
│   │   ├── package.json
│   │   └── tsconfig.json
│   └── README.md
└── README.md                    ← root README ties both together
```

**What you learn:**
Monorepo thinking — `live/backend` imports CaRAG's `services.py` directly instead of duplicating it. One git history tells the full v1 → v2 evolution story for recruiters.

**Acceptance check:** Both `backend/` and `live/backend/` start independently without errors.

---

## Milestone 1 — Auth Layer (REST APIs, from scratch)

> CaRAG currently has zero auth. Everything else depends on knowing *who* the user is.

### Task 1.1 — Add a `users` table

**What you build:**
```python
class User(Base):
    __tablename__ = "users"
    id              = Column(Integer, primary_key=True)
    email           = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    created_at      = Column(DateTime, default=datetime.utcnow)
    memberships     = relationship("GroupMember", back_populates="user")
```

**What you learn:**
How SQLAlchemy ORM maps Python classes to Postgres tables. Why `create_all` is idempotent. What `hashed_password` means — you never store plaintext, ever.

**Acceptance check:** `GET /debug/db` shows a `users` table with 0 rows (exists, empty).

---

### Task 1.2 — `POST /auth/register` and `POST /auth/login`

**What you build:**
Register: hash password with `bcrypt`, insert user. Login: verify hash, return signed JWT with `sub: user_id`, `exp: now + 7 days`.

**What you learn:**
- Why passwords are hashed (one-way — verify but never reverse)
- JWT anatomy: base64(header) + base64(payload) + HMAC signature
- `python-jose` for signing, `passlib[bcrypt]` for hashing
- Authentication (who are you) vs authorization (what can you do)

**Acceptance check:** Register → login → paste token on jwt.io → see `user_id` in payload.

---

### Task 1.3 — JWT middleware as a FastAPI dependency

**What you build:**
```python
async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
) -> User:
    payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
    user = db.query(User).filter(User.id == payload["sub"]).first()
    if not user:
        raise HTTPException(status_code=401)
    return user
```
Apply to all protected routes via `Depends(get_current_user)`.

**What you learn:**
How `Depends()` composes — middleware as a reusable function, not a class. What happens when a token is expired vs tampered (two distinct JWT errors). Why stateless auth needs no session table.

**Acceptance check:** `POST /upload` without token → `401`. With valid token → passes through.

---

## Milestone 2 — Groups Layer (REST APIs + relational DB)

> The core new concept. Documents belong to groups. Queries are scoped to groups. Users can be in multiple groups.

### Task 2.1 — `groups` and `group_members` tables

**What you build:**
```python
class Group(Base):
    __tablename__ = "groups"
    id         = Column(Integer, primary_key=True)
    name       = Column(String, nullable=False)
    created_by = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime, default=datetime.utcnow)
    members    = relationship("GroupMember", back_populates="group")
    documents  = relationship("Document", back_populates="group")

class GroupMember(Base):
    __tablename__ = "group_members"
    id        = Column(Integer, primary_key=True)
    group_id  = Column(Integer, ForeignKey("groups.id", ondelete="CASCADE"))
    user_id   = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"))
    joined_at = Column(DateTime, default=datetime.utcnow)
```

**What you learn:**
Many-to-many relationships via a join table. Why `ondelete="CASCADE"` matters — delete a group, all memberships vanish automatically. The difference between a DB-level FK constraint and an ORM-level relationship.

**Acceptance check:** Create a group → inspect Postgres directly → see rows in both `groups` and `group_members`.

---

### Task 2.2 — Group CRUD endpoints

**What you build:**
```
POST   /groups              → create group (creator auto-added as member)
GET    /groups              → list groups current user belongs to
GET    /groups/{id}         → group detail + member list
DELETE /groups/{id}         → delete group (only creator for now)
```

**What you learn:**
RESTful resource design — when to nest (`/groups/{id}/members`) vs flat (`/groups`). How to write a join query: "groups this user belongs to."

```python
groups = db.query(Group).join(GroupMember).filter(
    GroupMember.user_id == current_user.id
).all()
```

**Acceptance check:** Create 2 groups as User A → login as User B → `GET /groups` returns empty list.

---

### Task 2.3 — Invite system: `POST /groups/{id}/invite`

**What you build:**
Accepts `{email}`, looks up user, inserts `GroupMember` row. Any existing member can invite — no role check needed yet.

**What you learn:**
Membership validation before action — "is the requester already in this group?" This is the pattern behind every "you must be a member to invite" feature.

**Acceptance check:** User A invites User B by email → User B's `GET /groups` shows the group.

---

### Task 2.4 — Attach `group_id` to documents

**What you build:**
Add `group_id` FK to `Document`. Update `POST /upload` to require `group_id`. Update `GET /documents` to return only docs from groups the current user belongs to.

```python
docs = db.query(Document).join(Group).join(GroupMember).filter(
    GroupMember.user_id == current_user.id,
    Document.group_id == group_id
).all()
```

**What you learn:**
Multi-tenant data isolation at the query level. One table, filtered by group membership via join. This is the pattern every SaaS uses.

**Acceptance check:** Upload doc to Group A as User A → User B (not in Group A) cannot see it.

---

### Task 2.5 — Group-scoped CaRAG query

**What you build:**
Update `POST /chat` to accept `group_id`. Validate user is a member. Fetch `doc_ids` for that group. Pass them as a filter to CaRAG's `answer_question` (it already supports `doc_ids` — check `services.py`).

**What you learn:**
"Don't touch the engine, control the fuel." CaRAG's search already accepts a `doc_ids` filter — you're just feeding it the right set. This is how you extend an existing system without rewriting it.

**Acceptance check:** Two groups with different docs — querying Group A never surfaces Group B's content.

---

## Milestone 3 — WebSockets: Real-Time Ingestion Status

> Replace polling with push. Every group member sees live ingestion status.

### Task 3.1 — Raw WebSocket echo server

**What you build:**
`GET /ws` in FastAPI using built-in `WebSocket`. Accept connection, echo back whatever the client sends.

**What you learn:**
The HTTP Upgrade handshake. `ws.accept()`, `receive_text()`, `send_text()` — the raw lifecycle. Why raw WebSockets over Socket.io for actually understanding what's happening.

**Acceptance check:** `wscat -c ws://localhost:8001/ws` → send "hello" → receive "hello".

---

### Task 3.2 — Connection manager with group-aware rooms

**What you build:**
```python
class ConnectionManager:
    def __init__(self):
        self.user_connections: dict[int, WebSocket] = {}
        self.group_connections: dict[int, set[int]] = {}  # group_id → {user_ids}

    async def connect(self, user_id, group_id, ws): ...
    async def disconnect(self, user_id, group_id): ...
    async def send_to_user(self, user_id, data): ...
    async def broadcast_to_group(self, group_id, data): ...

manager = ConnectionManager()  # singleton
```

**What you learn:**
Targeted push vs group broadcast. Why `group_connections` uses a `set` — O(1) membership check, automatic deduplication. This is the pattern Slack uses for channel notifications.

**Acceptance check:** Two users connect to the same group → `broadcast_to_group` → both receive it. Third user in another group receives nothing.

---

### Task 3.3 — Authenticate WebSocket connections

**What you build:**
`GET /ws?token=...&group_id=...` — verify JWT and group membership before `ws.accept()`. Reject with close code `4001` (bad token) or `4003` (not a member).

**What you learn:**
The classic interview question: "How do you auth a WebSocket?" You can't send `Authorization` headers post-handshake from a browser. Two patterns: token in query param (simpler) vs token as first message (more secure). You implement and understand both tradeoffs.

**Acceptance check:** Invalid token → closed 4001. Valid token, wrong group → closed 4003. Valid token, correct group → stays open.

---

### Task 3.4 — Push ingestion events to group members

**What you build:**
Inside `process_document_task`, after each status change:
```python
await manager.broadcast_to_group(group_id, {
    "event": "doc_processing", "doc_id": doc_id, "filename": filename
})
# then on ready:
await manager.broadcast_to_group(group_id, {
    "event": "doc_ready", "doc_id": doc_id, "category": category
})
```

**What you learn:**
How a background task (outside the request lifecycle) talks to live WebSocket connections. The manager singleton is the bridge. Every group member sees ingestion status — not just the uploader.

**Acceptance check:** User A uploads a doc. User B (same group, connected via WS) sees status events live without polling.

---

### Task 3.5 — Heartbeat: ping/pong

**What you build:**
A background `asyncio` loop that pings every connected client every 30 seconds. No pong within 5 seconds → remove from manager.

**What you learn:**
Why dead connections silently accumulate without this. The ping/pong mechanism at the protocol level. Why `manager.active` slowly fills with dead entries that all throw on send.

**Acceptance check:** Kill a client ungracefully → it disappears from manager within 35 seconds.

---

## Milestone 4 — WebSockets: Streaming Query Responses

> Replace blocking `POST /chat` HTTP with a streaming WebSocket flow.

### Task 4.1 — Switch Gemini to streaming mode

**What you build:**
Update `generate_answer` in `llm_service.py` to use `generate_content(..., stream=True)` and yield chunks as an async generator.

**What you learn:**
How streaming LLM APIs work — token-by-token generation forwarded immediately. This is exactly how ChatGPT's typewriter effect is implemented.

**Acceptance check:** Unit test the generator — chunks print progressively, not all at once.

---

### Task 4.2 — Message type router + streaming over WebSocket

**What you build:**
The single `GET /ws` handler routes on incoming `type` field:

```
# Incoming:
{type: "chat", question: "...", group_id: 5}
{type: "ping"}
{type: "subscribe_doc", doc_id: 12}

# Outgoing:
{event: "chunk", text: "..."}          ← streaming answer token
{event: "done", citations: [...]}      ← end of stream
{event: "error", message: "..."}
{event: "doc_ready", doc_id: ...}      ← ingestion update
```

**What you learn:**
How to design a message protocol on top of raw WebSocket. This is exactly what Slack, Figma, and Linear do internally — a typed event system over a persistent connection. Building it from scratch means you can explain every design decision.

**Acceptance check:** Send `{type: "chat", question: "what are the risks?", group_id: 1}` via wscat → chunks stream in → `done` received with citations.

---

## Milestone 5 — OpenClaw Plugin (Dev Level)

> Everything wires together here. TypeScript plugin that orchestrates: intent → group context → CaRAG → Telegram reply.

### Task 5.1 — Scaffold plugin, connect to Telegram

**What you build:**
OpenClaw running locally with a Telegram bot. Minimal plugin that replies "CaRAG Live is online 🟢" to any message.

**What you learn:**
OpenClaw's plugin SDK — `onMessage(ctx)`, `ctx.reply()`, `ctx.memory`. How the gateway routes Telegram messages to plugins.

**Acceptance check:** DM anything → bot replies online message.

---

### Task 5.2 — LLM-powered intent classifier

**What you build:**
`intent.ts` — sends raw Telegram message to LLM with structured output prompt. Returns:
```typescript
type Intent =
  | { type: "query"; question: string }
  | { type: "upload" }
  | { type: "list_docs" }
  | { type: "switch_group" }
  | { type: "invite"; email: string }
  | { type: "unknown" }
```

**What you learn:**
Agentic orchestration at code level — an LLM deciding which tool to invoke. Why constrained JSON output schemas matter for preventing hallucinated intents. How to write a deterministic fallback when the LLM goes off-schema.

**Acceptance check:** 10 varied natural language messages → at least 8 correctly classified.

---

### Task 5.3 — Group context manager with sticky memory + timeout

**What you build:**
`groupCtx.ts`:
```typescript
async function getActiveGroup(ctx): Promise<number | null> {
  const mem = await ctx.memory.get("active_group")
  if (mem && (Date.now() - mem.set_at) < 24 * 60 * 60 * 1000)
    return mem.group_id
  return null
}

async function setActiveGroup(ctx, group_id: number) {
  await ctx.memory.set("active_group", { group_id, set_at: Date.now() })
}
```

Main flow:
```
groups = GET /groups
if groups.length == 1 → use directly
if active_group in memory + not expired → use it
else → show Telegram inline keyboard → wait for tap → store in memory
```

**What you learn:**
How OpenClaw's memory layer works (Markdown files, SDK abstraction). Stateless vs stateful plugins. Why timeout-based memory is better than permanent for context that should refresh.

**Acceptance check:** User with 3 groups queries → picker appears → tap one → next query skips picker → 24h later → picker appears again.

---

### Task 5.4 — Plugin calls CaRAG Live REST API

**What you build:**
`carag.ts` — typed REST client. Login on startup, store JWT, refresh on `401`. Methods: `listGroups()`, `listDocs(groupId)`, `inviteMember(groupId, email)`, `uploadFile(groupId, fileUrl)`.

**What you learn:**
Building a typed API client from scratch in TypeScript. Token refresh in a long-running process. `multipart/form-data` uploads from Node.js — Telegram gives a file URL, plugin fetches it and re-POSTs to CaRAG.

**Acceptance check:** DM "list my docs" → bot replies with filenames from active group, live from CaRAG.

---

### Task 5.5 — Plugin streams query response over WebSocket

**What you build:**
For query intent:
1. Open `ws://localhost:8001/ws?token=...&group_id=...`
2. Send `{type: "chat", question: "...", group_id: ...}`
3. Buffer incoming `chunk` events
4. On `done` → close WS → send full answer + citations to Telegram

**What you learn:**
Using `ws` npm package from Node.js. Why you buffer instead of sending partial Telegram messages (Telegram has no streaming API). The architectural tradeoff: real-time on the backend, batched on delivery.

**Acceptance check:** DM "what does the contract say about termination?" → Telegram replies with full answer + citations.

---

### Task 5.6 — Invite flow end-to-end

**What you build:**
Handle `invite` intent → call `POST /groups/{id}/invite` → reply with success/failure.

**What you learn:**
The full three-entity flow wired together: Telegram → plugin → CaRAG Live REST → Postgres → confirmation back. Every hop is something you built and understand.

**Acceptance check:** DM "invite someone@email.com to my group" → that user sees the group on their next `GET /groups`.

---

## Milestone 6 — Polish and Interview-Ready

### Task 6.1 — Consistent REST error responses
Global FastAPI exception handler. Every error returns `{error, code, detail}`. Handlers for `401`, `403`, `404`, `422`, `500`.

### Task 6.2 — Pydantic v2 input validation
`Field` constraints on all schemas. `question` max 500 chars. `group_name` 3–50 chars. `email` validated with `EmailStr`. Tests for invalid payloads → `422`.

### Task 6.3 — Rate limiting on auth endpoints
`slowapi` — 5 login attempts per minute per IP. `429` with `Retry-After` header.

### Task 6.4 — WebSocket reconnect with exponential backoff
Client-side: on `onclose` → wait 1s → 2s → 4s → 8s → (capped 30s). Reset counter on success. Re-authenticate and re-join group room after reconnect.

### Task 6.5 — README
Architecture diagram + what each milestone adds + "what I learned" in your own words. This is what interviewers read before they meet you.

---

## Complete flow recap (fully wired)

```
1. User DMs: "what does the NDA say about confidentiality?"

2. OpenClaw plugin fires
   → intent.ts: {type: "query", question: "..."}

3. groupCtx.ts checks memory:
   → active_group found + not expired → use Group 3 "Legal Team"
   → (if not) → GET /groups → show inline keyboard → user taps → memory set

4. carag.ts opens WebSocket:
   → ws://localhost:8001/ws?token=...&group_id=3
   → sends {type: "chat", question: "...", group_id: 3}

5. CaRAG Live backend:
   → validates JWT + membership for group 3
   → fetches doc_ids belonging to group 3
   → runs CaRAG: classify → route → retrieve (group-scoped) → stream

6. Plugin buffers chunks → on "done" → sends answer + citations to Telegram

7. Meanwhile: other group 3 members connected via WS see
   {event: "query_running", user: "Anuj"} in real time
```

---

## What each milestone teaches

| Milestone | Core Concept | Interview Topic |
|---|---|---|
| 0 — Setup | Monorepo structure | "How do you organize multi-service projects?" |
| 1 — Auth | JWT, bcrypt, middleware as dependency | "How does auth work in your API?" |
| 2 — Groups | Relational joins, multi-tenancy, cascade deletes | "How do you isolate data between tenants?" |
| 3 — WS Ingestion | WebSocket lifecycle, group rooms, heartbeat | "Have you built with raw WebSockets?" |
| 4 — WS Streaming | Async generators, message protocols | "How did you implement streaming?" |
| 5 — OpenClaw | Agentic orchestration, memory, tool calling | "Explain your agentic system" |
| 6 — Polish | Error handling, validation, rate limiting, backoff | "How do you handle failures?" |

---

## What you are NOT building (and why)

- **New RAG logic** — CaRAG's core (`services.py`, `milvus_store.py`) is untouched. You control the inputs, not the engine.
- **Frontend UI** — wscat + Swagger + Telegram is enough for every milestone.
- **Docker / deployment** — Local only until Milestone 6 is done.
- **Admin roles** — Explicitly deferred. Open membership now, RBAC later.

---

*CaRAG Live — built on top of CaRAG (Categorical Routing Augmented Generation)*
