# CaRAG Live — Complete System Flows & Edge Cases

> This document is the single source of truth for every user flow, happy path,
> failure path, and edge case in the system. Read this before writing any code.

---

## Entities & Their Roles

```
Telegram          ← user's interface. Never changes. telegram_user_id is permanent identity.
OpenClaw Plugin   ← stateful agent. Owns: intent classification, group context, JWT management.
CaRAG Live API    ← REST + WebSocket backend. Owns: auth, groups, documents, query routing.
CaRAG Engine      ← existing RAG core (services.py). Untouched. Receives scoped queries only.
PostgreSQL        ← source of truth for everything.
OpenClaw Memory   ← plugin-local cache only. Never source of truth.
```

---

## 1. First-Time User Flow (Onboarding)

**Trigger:** User sends any message to bot and `telegram_user_id` is not mapped to any CaRAG user.

```
User sends: "hey" (or anything)
      ↓
Plugin checks memory: telegram_user_id → carag_user mapping
      ↓ NOT FOUND
Plugin replies:
  "Welcome to CaRAG Live 👋
   Let's set up your account.
   What's your email?"

User sends: "anuj@pdeu.ac.in"
      ↓
Plugin stores email in temp memory (not DB yet)
Plugin replies: "Choose a password:"

User sends: "••••••"
      ↓
Plugin calls POST /auth/register {email, password}

┌─ SUCCESS ─────────────────────────────────────────┐
│ Plugin receives JWT                                │
│ Plugin stores in memory:                           │
│   telegram_user_id → { carag_user_id, jwt, email }│
│ Plugin replies:                                    │
│   "You're in ✅                                    │
│    Create a group: 'new group <name>'              │
│    Or ask to be invited by an existing member."   │
└───────────────────────────────────────────────────┘

┌─ FAILURE: email already exists ───────────────────┐
│ API returns 409 Conflict                           │
│ Plugin replies:                                    │
│   "That email is already registered.              │
│    Want to log in instead? Send your password."   │
│ User sends password → POST /auth/login            │
│ Continue as returning user flow                    │
└───────────────────────────────────────────────────┘
```

**Edge cases:**
- User sends garbage during email step → plugin validates format client-side, asks again
- User goes silent mid-onboarding → temp memory expires after 10 min → next message restarts onboarding
- User tries to register with a very weak password → API returns 400 → plugin asks again

---

## 2. Returning User Flow

**Trigger:** User sends any message and `telegram_user_id` IS mapped to a CaRAG user.

```
User returns to chat
      ↓
Plugin reads memory: { carag_user_id, jwt, jwt_issued_at }

Case A: JWT still valid (< 7 days old)
      ↓
Continue directly to Intent Classification (Flow 5)

Case B: JWT expired (> 7 days old)
      ↓
Plugin silently calls POST /auth/login with stored credentials
      ↓
┌─ SUCCESS ──────────────────────────────────────────┐
│ New JWT stored in memory                           │
│ User sees nothing — seamless                       │
│ Continue to Intent Classification                  │
└────────────────────────────────────────────────────┘

┌─ FAILURE: login fails (password changed?) ─────────┐
│ Plugin clears stored credentials                   │
│ Plugin replies:                                    │
│   "Your session expired and I couldn't refresh it.│
│    Please send your password to log back in."     │
│ User sends password → re-authenticate             │
└────────────────────────────────────────────────────┘
```

**Edge cases:**
- User is mid-conversation when JWT expires → next API call returns 401 → plugin intercepts, refreshes silently, retries the original request once
- User deliberately sends `/logout` → plugin clears ALL memory for that telegram_user_id → next message triggers fresh onboarding

---

## 3. Intent Classification Flow

**Trigger:** Every incoming message from an authenticated user.

```
Incoming message
      ↓
Plugin sends to LLM intent classifier with schema:

{
  type: "query"       + question: string
  type: "upload"      (file attached)
  type: "new_group"   + name: string
  type: "list_docs"
  type: "list_groups"
  type: "switch_group"
  type: "invite"      + email: string
  type: "remove_doc"  + hint: string  (filename or partial)
  type: "delete_group"
  type: "help"
  type: "unknown"
}

LLM returns structured JSON
      ↓
┌─ VALID INTENT ────────────────────────────────────┐
│ Route to appropriate flow below                   │
└───────────────────────────────────────────────────┘

┌─ type: "unknown" ─────────────────────────────────┐
│ Plugin replies:                                   │
│   "I didn't understand that. Here's what I       │
│    can do: [list of commands]"                    │
└───────────────────────────────────────────────────┘

┌─ LLM returns malformed JSON ──────────────────────┐
│ Plugin falls back to keyword matching:            │
│   message contains "upload" / file attached → upload│
│   message starts with "ask" / "what" / "how" → query│
│   else → unknown                                  │
└───────────────────────────────────────────────────┘
```

---

## 4. Group Context Resolution

**Trigger:** Before any group-scoped action (query, upload, list docs, invite, etc.)

```
Plugin calls GET /groups (current user's groups)
      ↓
┌─ 0 groups ────────────────────────────────────────┐
│ Plugin replies:                                   │
│   "You're not in any group yet.                  │
│    Create one: 'new group <name>'                 │
│    Or ask someone to invite you."                 │
│ STOP — do not proceed with action                 │
└───────────────────────────────────────────────────┘

┌─ 1 group ─────────────────────────────────────────┐
│ Use it directly. No picker. No memory write.      │
│ Continue to intended action.                      │
└───────────────────────────────────────────────────┘

┌─ 2+ groups ───────────────────────────────────────┐
│ Check memory: active_group_id + active_group_set_at│
│                                                   │
│ Memory hit + age < 24h:                           │
│   Verify group still exists + user still member  │
│   → YES → use it, continue                       │
│   → NO  → clear memory, show picker              │
│                                                   │
│ Memory miss or age > 24h:                         │
│   Show Telegram inline keyboard:                  │
│   [ Group A ] [ Group B ] [ Group C ]            │
│   "Which group for this action?"                  │
│                                                   │
│   User taps → store in memory:                    │
│   { active_group_id, active_group_set_at: now }  │
│   Continue with selected group                    │
└───────────────────────────────────────────────────┘
```

**Edge cases:**
- User was removed from their active group since last session → memory hit but API returns 403 → clear memory, show picker with remaining groups
- Group was deleted entirely → same as above, group won't appear in picker
- User taps picker but then immediately sends another message before tapping → queue the second message, resolve picker first
- User ignores the picker for 5 minutes → picker expires → next message re-triggers picker

---

## 5. Query Flow (Happy Path + Edge Cases)

**Trigger:** Intent = `query`

```
Resolve group context (Flow 4)
      ↓
Plugin opens WebSocket:
  ws://localhost:8001/ws?token=JWT&group_id=GROUP_ID
      ↓
CaRAG Live backend:
  → Validates JWT (signature + expiry)
  → Validates user is member of group_id
  → ws.accept()
      ↓
Plugin sends:
  { type: "chat", question: "...", group_id: GROUP_ID }
      ↓
Backend fetches doc_ids for this group from Postgres
      ↓
┌─ 0 docs in group ─────────────────────────────────┐
│ Backend sends: { event: "error",                  │
│   message: "This group has no documents yet." }   │
│ Plugin replies to Telegram with the message       │
│ Close WS                                          │
└───────────────────────────────────────────────────┘

┌─ docs exist ──────────────────────────────────────┐
│ Backend runs CaRAG pipeline:                      │
│   classify_query_category()                       │
│   → route to matching category chunks             │
│   → retrieve top_k doc chunks (scoped to group)   │
│   → stream generate_answer()                      │
│                                                   │
│ Backend sends chunk events:                       │
│   { event: "chunk", text: "The contract..." }    │
│   { event: "chunk", text: " states that..." }    │
│   ...                                             │
│   { event: "done", citations: [...] }            │
│                                                   │
│ Plugin buffers all chunks                         │
│ On "done" → close WS                             │
│ Plugin sends full answer + citations to Telegram  │
└───────────────────────────────────────────────────┘
```

**Edge cases:**
- **WS drops mid-stream:** Plugin detects `onclose` before receiving `done`. Reply: "Connection dropped mid-response. Please ask again." Do NOT send partial answer.
- **Gemini 429 during streaming:** CaRAG engine falls back to keyword-based answer (already built). Backend sends `{ event: "fallback", message: "..." }`. Plugin adds a note: "⚠️ AI quota reached, showing keyword match."
- **Query returns no relevant chunks:** Backend sends `{ event: "done", citations: [], text: "I couldn't find relevant information in this group's documents." }`
- **JWT expires exactly during WS session:** WS auth happens on connect only. Mid-session expiry is fine — connection stays open. Next WS connection will catch the expiry.
- **User sends another message while waiting for stream:** Plugin queues it. Responds: "⏳ Processing your previous question first..."
- **Very long answer:** Telegram has a 4096 char limit. Plugin chunks the reply into multiple messages if needed.

---

## 6. Document Upload Flow

**Trigger:** Intent = `upload`, file attached to Telegram message

```
Resolve group context (Flow 4)
      ↓
Telegram gives plugin a file_id + file_url
      ↓
Plugin fetches file bytes from Telegram CDN
      ↓
┌─ File too large (> 20MB) ─────────────────────────┐
│ Plugin replies: "File too large. Max 20MB."       │
│ STOP                                              │
└───────────────────────────────────────────────────┘

┌─ Not a PDF ────────────────────────────────────────┐
│ Plugin replies: "Only PDF files supported."       │
│ STOP                                              │
└───────────────────────────────────────────────────┘

Plugin calls POST /upload (multipart/form-data):
  { file: <bytes>, group_id: GROUP_ID }
      ↓
Backend:
  → saves file to disk (uploads/)
  → inserts Document row: status="uploaded", group_id
  → fires process_document_task() in background
  → returns { doc_id, filename }
      ↓
Plugin replies: "📄 anuj_report.pdf uploaded.
                Processing started... I'll notify you when ready."
      ↓
Background task runs (CaRAG engine):
  → extract text
  → chunk
  → embed
  → classify category
  → upsert to Milvus
  → update status = "ready"
  → broadcast to group via WS manager
      ↓
All group members connected via WS receive:
  { event: "doc_ready", doc_id, filename, category }
      ↓
Plugin receives WS event → sends Telegram message:
  "✅ anuj_report.pdf is ready! Category: Legal"
```

**Edge cases:**
- **Duplicate filename in same group:** Backend checks for existing doc with same filename + group_id. If found: "A doc with this name exists. Replace it? (yes/no)". Yes → delete old doc + re-ingest. No → cancel.
- **Ingestion fails mid-way:** `process_document_task` catches exception → status = "failed" → broadcasts `{ event: "doc_failed" }` → Plugin notifies: "❌ anuj_report.pdf failed to process. Try uploading again."
- **Partial ingestion (chunks inserted, Milvus upsert fails):** The existing idempotent chunk deletion in `process_document_task` handles re-runs. Just re-upload.
- **No file attached but intent = upload:** Plugin replies: "Please attach a PDF file."
- **User uploads while another ingestion is running:** Fine — each runs in its own background task. Both notify independently.
- **Group deleted while ingestion running:** Background task completes → tries to broadcast to group → manager finds no connections → silently skips. Doc is orphaned. Cleanup: cascade delete handles DB. File on disk needs a periodic cleanup job (future).

---

## 7. Group Management Flows

### 7a. Create Group

```
Intent: new_group, name: "Legal Team"
      ↓
Plugin calls POST /groups { name: "Legal Team" }
      ↓
Backend:
  → inserts Group row
  → inserts GroupMember row: user_id, group_id, role="owner"
  → returns { group_id, name }
      ↓
Plugin sets active_group in memory to new group
Plugin replies: "✅ Group 'Legal Team' created.
                You're the owner.
                Invite members: 'invite <email>'"
```

**Edge cases:**
- Group name already exists for this user → backend returns 409 → "You already have a group with that name."
- Name too short/long → Pydantic validation → 422 → "Group name must be 3–50 characters."

---

### 7b. Invite Member

```
Intent: invite, email: "hritik@pdeu.ac.in"
      ↓
Resolve group context (Flow 4)
      ↓
Plugin calls POST /groups/{id}/invite { email }
      ↓
Backend:
  → looks up user by email
  → checks inviter IS a member of the group
  → checks invitee is NOT already a member
  → inserts GroupMember: role="member"
      ↓
Plugin replies: "✅ hritik@pdeu.ac.in added to Legal Team."
```

**Edge cases:**
- **Email not registered:** API returns 404 → Plugin: "That email isn't registered on CaRAG Live yet. Ask them to sign up first."
- **Already a member:** API returns 409 → Plugin: "They're already in this group."
- **Inviting yourself:** API returns 400 → Plugin: "You're already in this group."
- **Group doesn't exist anymore:** API returns 404 → Plugin clears memory, prompts group selection.

---

### 7c. Remove Document

```
Intent: remove_doc, hint: "anuj_report"
      ↓
Resolve group context
      ↓
Plugin calls GET /documents?group_id=X&search=anuj_report
      ↓
┌─ 0 matches ───────────────────────────────────────┐
│ "No document matching 'anuj_report' found."       │
└───────────────────────────────────────────────────┘

┌─ 1 match ─────────────────────────────────────────┐
│ Plugin: "Delete anuj_report.pdf? (yes/no)"        │
│ User: "yes"                                       │
│ Plugin calls DELETE /documents/{id}               │
│ Backend: disk delete + Milvus delete + DB delete  │
│ Plugin: "🗑️ Deleted."                             │
└───────────────────────────────────────────────────┘

┌─ 2+ matches ──────────────────────────────────────┐
│ Plugin shows inline keyboard with matches         │
│ User taps one → confirmation → delete             │
└───────────────────────────────────────────────────┘
```

**Edge cases:**
- User says "yes" to confirmation but then the doc is already deleted (race condition with another member) → 404 → "Already deleted."
- Delete while ingestion in progress → backend cancels background task (set a cancel flag on the Document row), then deletes.

---

### 7d. Delete Group

```
Intent: delete_group
      ↓
Resolve group context (must be owner)
      ↓
Plugin: "⚠️ Delete 'Legal Team'? This removes all
         documents and cannot be undone. Type DELETE to confirm."
      ↓
User sends: "DELETE"
      ↓
Plugin calls DELETE /groups/{id}
      ↓
Backend:
  → cascade: group_members deleted
  → cascade: documents deleted
  → Milvus: delete all chunks for group's doc_ids
  → disk: delete all files for group
  → broadcast: { event: "group_deleted" } to all connected members
      ↓
Plugin clears active_group memory
Plugin: "Group deleted."
```

**Edge cases:**
- **Non-owner tries to delete:** API returns 403 → Plugin: "Only the group owner can delete it."
- **User sends anything other than "DELETE":** Plugin: "Deletion cancelled."
- **Confirmation timeout (5 min):** Plugin: "Deletion timed out. Send 'delete group' again if you still want to."

---

## 8. Multi-User Simultaneous Flow

```
Group: "Legal Team"
Members: Anuj (connected via WS), Hritik (connected via WS), Priya (offline)

Anuj uploads doc
      ↓
Backend ingests → status: processing
      ↓
WS broadcast to group:
  Anuj receives:   { event: "doc_processing", filename: "contract.pdf" }
  Hritik receives: { event: "doc_processing", filename: "contract.pdf" }
  Priya: offline, receives nothing (no connection in manager)
      ↓
Ingestion completes
      ↓
WS broadcast:
  Anuj receives:   { event: "doc_ready", filename: "contract.pdf", category: "Legal" }
  Hritik receives: same
  Priya: still offline → misses event (acceptable — can check via GET /documents)

Simultaneously, Hritik sends a query
      ↓
Backend runs CaRAG (non-blocking async)
Both ingestion + query run concurrently — FastAPI handles this fine
      ↓
Hritik's query completes → streams to Hritik's WS only
Anuj is unaffected
```

**Edge cases:**
- **Same user connected from two Telegram sessions:** `user_connections` dict stores one WS per user_id. Second connection overwrites first. Old connection gets a `{ event: "replaced" }` message, then closed. Effectively "last device wins."
- **Group member count grows large (100+ members):** `broadcast_to_group` iterates over all connected user_ids in the group set. Slow if many are connected. Acceptable for learning; Redis PubSub is the production fix.

---

## 9. WebSocket Lifecycle Edge Cases

```
Connection established
      ↓
Heartbeat loop starts (server pings every 30s)
      ↓
Client goes silent (tab closed, network drop):
  Server sends ping
  No pong within 5s
  → remove from manager
  → WS silently closed server-side

Client reconnects (exponential backoff):
  1s → 2s → 4s → 8s → 16s → 30s (cap)
  On reconnect:
    → re-authenticate (send token in query param)
    → re-join group room
    → server sends: { event: "reconnected",
                      missed_events: [...] }  ← optional, future feature
```

**Edge cases:**
- **WS drops exactly when a chunk is being sent:** `send_json` throws. Backend catches, marks the stream as aborted. Next connection from same user can re-ask.
- **Server restarts:** All WS connections drop. Clients reconnect via backoff. Manager is fresh — all clients re-register. No state lost (Postgres is truth).
- **Client sends malformed JSON:** Backend catches `JSONDecodeError`, sends `{ event: "error", message: "Invalid message format" }`, keeps connection open.
- **Client sends unknown message type:** Backend sends `{ event: "error", message: "Unknown type: foo" }`, keeps connection open.

---

## 10. Complete State Machine: A User's Journey

```
NEW USER
  ↓
[ONBOARDING] → register/login → JWT stored in plugin memory
  ↓
[NO GROUPS] → create group or get invited
  ↓
[HAS GROUPS] → active_group resolved (1 group: auto, many: picker)
  ↓
[ACTIVE SESSION]
  ├── query      → WebSocket → scoped RAG → stream → Telegram reply
  ├── upload     → REST → background ingest → WS push → Telegram notify
  ├── invite     → REST → member added
  ├── list docs  → REST → formatted reply
  ├── switch grp → picker → new active_group in memory
  └── delete     → confirmation → cascade delete
  ↓
[SESSION CONTINUES] ← JWT auto-refreshed silently
  ↓
[24H INACTIVITY ON GROUP] → active_group memory expires → picker on next action
  ↓
[/logout] → all memory cleared → back to ONBOARDING
```

---

## 11. What Lives Where (Final Authority)

| Data | Source of Truth | Plugin Memory Role |
|---|---|---|
| User identity | Postgres `users` | Cache: telegram_id → user_id mapping |
| JWT | Issued by API | Cache: stored for reuse, refreshed on expiry |
| Group membership | Postgres `group_members` | NOT cached — always fetched fresh |
| Active group | Postgres `user_preferences` | Cache: optimization, expires in 24h |
| Documents | Postgres `documents` + Milvus | NOT cached |
| Ingestion status | Postgres `documents.status` | Pushed via WS, not cached |

**Rule:** If plugin memory and Postgres disagree, Postgres wins. Always.

---

## 12. API Contract Summary

```
AUTH
  POST /auth/register     { email, password } → { user_id, jwt }
  POST /auth/login        { email, password } → { jwt }

GROUPS
  POST   /groups                    → { group_id, name }
  GET    /groups                    → [ { group_id, name, role, member_count } ]
  GET    /groups/{id}               → { group_id, name, members, doc_count }
  DELETE /groups/{id}               → 204 (owner only)
  POST   /groups/{id}/invite        { email } → 200
  DELETE /groups/{id}/members/{uid} → 204 (owner only, future)

DOCUMENTS
  POST   /upload           { file, group_id } → { doc_id, filename }
  GET    /documents        ?group_id=X        → [ { doc_id, filename, status, category } ]
  DELETE /documents/{id}                      → 204

QUERY
  POST /chat    { question, group_id, top_k? } → { answer, citations }  ← REST fallback
  WS   /ws      ?token=...&group_id=...        ← primary interface

USER PREFERENCES
  GET   /me/preferences            → { active_group_id, active_group_set_at }
  PATCH /me/preferences            { active_group_id } → 200
```

---

## 13. Errors That Must Never Reach the User Raw

Every one of these must be caught and translated to a human message:

| Raw Error | User sees |
|---|---|
| 401 Unauthorized | "Session expired. Logging you back in..." (then retry) |
| 403 Forbidden | "You don't have permission to do that." |
| 404 Not Found | "That [group/document] doesn't exist anymore." |
| 409 Conflict | Context-specific (already member, duplicate name, etc.) |
| 422 Validation | "Something about your input was invalid: [detail]" |
| 429 Too Many Requests | "Slow down a bit — try again in a moment." |
| 500 Server Error | "Something went wrong on our end. Try again." |
| WS close 4001 | (transparent to user — plugin re-auths silently) |
| WS close 4003 | "You're no longer a member of that group." |
| Gemini 429 | "⚠️ AI quota hit — showing keyword-based result." |
| Network timeout | "Connection timed out. Please try again." |

---

*This document supersedes all previous flow descriptions. Update here first, then update code.*
