# High-Level Design (HLD) & Low-Level Design (LLD)

## Real-Time Discussion Forum

---

# Part 1 — High-Level Design (HLD)

## 1.1 System Overview

The Real-Time Discussion Forum is a microservices-based web application that enables users to create discussion threads, post nested comments, like content, @mention other users, and receive real-time notifications — all with role-based access control.

**Key properties:**
- 3 independently deployable backend services + 1 SPA frontend
- Asynchronous, event-driven notification pipeline
- Zero-downtime event delivery via outbox pattern
- Sub-second real-time updates over a unified WebSocket

---

## 1.2 Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                        CLIENT (Browser)                             │
│                                                                     │
│   React 19 SPA  ─── Zustand stores ─── Axios HTTP ─── WebSocket    │
│   Vite 8             (auth, notif,      (3 clients)    (1 conn)     │
│   Tailwind CSS 4      theme)                                        │
└────────┬──────────────────┬──────────────────────┬──────────────────┘
         │ REST             │ REST                  │ WS + REST
         ▼                  ▼                       ▼
┌──────────────┐   ┌──────────────┐       ┌──────────────────┐
│  Auth        │   │  Forum       │       │  Notification    │
│  Service     │   │  Service     │       │  Service         │
│              │   │              │       │                  │
│  Django 6.0  │   │  FastAPI     │       │  FastAPI         │
│  DRF + JWT   │   │  async       │       │  async           │
│  Port 8001   │   │  Port 8000   │       │  Port 8003       │
└──────┬───────┘   └──────┬───────┘       └───────┬──────────┘
       │                  │                        │
       │            ┌─────┴──────┐           ┌─────┴──────┐
       │            │   Redis 7  │◄──────────│  Consumer  │
       │            │   :6379    │  XREADGROUP│  Group     │
       │            │            │           └────────────┘
       │            │  • Cache   │
       │            │  • Streams │
       │            └────────────┘
       │                  │
  ┌────┴─────┐    ┌───────┴──────┐    ┌────────────────┐
  │ auth_db  │    │  forum_db    │    │ notification_db │
  │ (PG 15)  │    │  (PG 15)     │    │ (PG 15)         │
  └──────────┘    └──────────────┘    └────────────────┘
```

---

## 1.3 Service Responsibilities

| Service | Responsibility | Framework | Database |
| --- | --- | --- | --- |
| **Auth Service** | User registration, login, JWT issuance, profile management, role management, password reset | Django 6.0 + DRF + SimpleJWT | `auth_db` |
| **Forum Service** | Thread CRUD, comment CRUD (nested), likes, @mention parsing, event publishing, user data caching | FastAPI + async SQLAlchemy | `forum_db` |
| **Notification Service** | Event consumption (Redis Streams), notification storage, WebSocket push, REST API, auto-cleanup | FastAPI + async SQLAlchemy | `notification_db` |
| **Frontend** | SPA with routing, state management, real-time WebSocket, dark mode, role-based UI | React 19 + Zustand + Tailwind | — |

---

## 1.4 Communication Patterns

### 1.4.1 Synchronous (Request-Response)

```
Frontend ──HTTP/REST──► Auth Service     (login, register, profile)
Frontend ──HTTP/REST──► Forum Service    (threads, comments, likes)
Frontend ──HTTP/REST──► Notification Svc (fetch/mark notifications)
Forum Svc ─HTTP/httpx─► Auth Service     (bulk user lookup, cached in Redis)
```

### 1.4.2 Asynchronous (Event-Driven)

```
Forum Service ──XADD──► Redis Stream ──XREADGROUP──► Notification Service
                          "forum_events_stream"        (consumer group)
```

### 1.4.3 Real-Time (Bidirectional)

```
Frontend ◄──WebSocket──► Notification Service
              /ws?token=JWT
              JSON messages: subscribe_thread / unsubscribe_thread
```

---

## 1.5 Authentication Flow (HLD)

```
┌──────────┐    POST /login    ┌──────────────┐
│  Browser │──────────────────►│ Auth Service  │
│          │◄──────────────────│              │
│          │   {access, refresh}│  (Django)    │
└────┬─────┘                   └──────────────┘
     │
     │  Bearer <access_token>
     │
     ├────────────────────────►┌──────────────┐
     │   GET /threads          │ Forum Service │  ← decodes JWT locally
     │                         │   (FastAPI)   │    using shared secret
     │                         └──────────────┘
     │
     ├────────────────────────►┌──────────────────┐
     │   WS /ws?token=JWT      │ Notification Svc │  ← decodes JWT locally
     │                         │    (FastAPI)      │
     │                         └──────────────────┘
```

No service ever calls auth-service to verify a token. Each service decodes the JWT itself using the shared HS256 secret key.

---

## 1.6 Event Flow (HLD)

```
 User creates comment on Thread #5, @mentions "alice"
                    │
                    ▼
           ┌──────────────┐
           │ Forum Service │
           │               │
           │ 1. Save comment to forum_db
           │ 2. Parse @mentions → ["alice"]
           │ 3. Resolve alice → user_id=7 via auth-service
           │ 4. XADD events to Redis Stream:
           │    • comment.created  (thread_id=5)
           │    • comment.mentioned (target_user_id=7)
           └───────┬──────┘
                   │ Redis Stream
                   ▼
           ┌──────────────────┐
           │ Notification Svc  │
           │                   │
           │ 1. XREADGROUP reads events
           │ 2. comment.created →
           │    • Broadcast to all WebSockets subscribed to thread 5
           │ 3. comment.mentioned →
           │    • Save notification to notification_db
           │    • Push via WebSocket to user 7
           │ 4. XACK acknowledges processed events
           └──────────────────┘
```

---

## 1.7 Resilience Strategy (HLD)

| Failure | Mitigation |
| --- | --- |
| Redis down on startup | `DummyRedis` no-op class — app runs without cache/streaming |
| Redis down mid-request | Events saved to `event_outbox` table (PostgreSQL) |
| Redis recovers | Background flusher pushes outbox → Redis Stream every 10s |
| Notification-service down | Events persist in Redis Stream; consumer group tracks position |
| Consumer crash mid-event | Unacknowledged events redelivered via `_process_pending()` |
| Auth-service down | Forum returns `User#<id>` placeholder — never 500s |
| WebSocket disconnect | Frontend reconnects with exponential backoff (1s → 30s cap) |

---

## 1.8 Scalability Considerations

```
                      ┌──────────────┐
                      │ Load Balancer │
                      └──────┬───────┘
                             │
              ┌──────────────┼──────────────┐
              ▼              ▼              ▼
        ┌──────────┐  ┌──────────┐   ┌──────────────┐
        │ Auth ×2  │  │ Forum ×3 │   │ Notif ×2     │
        │ (stateless│  │(stateless│   │(consumer grp)│
        └──────────┘  └──────────┘   └──────────────┘
```

- **Auth & Forum**: Stateless — scale horizontally behind a load balancer.
- **Notification**: Redis consumer groups allow multiple workers. WebSocket connections require sticky sessions or a shared pub/sub layer.
- **Database**: Single PostgreSQL instance now; can shard per-service later (ADR-7).

---

---

# Part 2 — Low-Level Design (LLD)

## 2.1 Database Schema (Complete)

### 2.1.1 auth_db — `accounts_user` (Django ORM)

```sql
CREATE TABLE accounts_user (
    id              SERIAL PRIMARY KEY,
    username        VARCHAR(150) NOT NULL UNIQUE,
    email           VARCHAR(254) NOT NULL,
    password        VARCHAR(128) NOT NULL,       -- bcrypt/PBKDF2 hash
    role            VARCHAR(10)  NOT NULL DEFAULT 'member',
                                                  -- 'admin' | 'moderator' | 'member'
    bio             TEXT,
    avatar          TEXT,                          -- URL string
    first_name      VARCHAR(150) NOT NULL DEFAULT '',
    last_name       VARCHAR(150) NOT NULL DEFAULT '',
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    is_staff        BOOLEAN NOT NULL DEFAULT FALSE,
    is_superuser    BOOLEAN NOT NULL DEFAULT FALSE,
    date_joined     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_login      TIMESTAMPTZ
);

-- Django also creates:
--   token_blacklist_outstandingtoken
--   token_blacklist_blacklistedtoken   (for JWT refresh token rotation)
```

### 2.1.2 forum_db — Threads, Comments, Likes, Outbox (SQLAlchemy)

```sql
-- Threads
CREATE TABLE threads (
    id              SERIAL PRIMARY KEY,
    title           VARCHAR NOT NULL,
    description     TEXT NOT NULL,
    user_id         INTEGER NOT NULL,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX ix_threads_user_id    ON threads (user_id);
CREATE INDEX ix_threads_created_at ON threads (created_at);

-- Comments (nested via parent_id)
CREATE TABLE comments (
    id              SERIAL PRIMARY KEY,
    content         TEXT NOT NULL,
    user_id         INTEGER NOT NULL,
    thread_id       INTEGER NOT NULL,
    parent_id       INTEGER,                       -- NULL = top-level comment
    created_at      TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX ix_comments_thread_id ON comments (thread_id);
CREATE INDEX ix_comments_parent_id ON comments (parent_id);
CREATE INDEX ix_comments_user_id   ON comments (user_id);

-- Thread Likes
CREATE TABLE thread_likes (
    id              SERIAL PRIMARY KEY,
    user_id         INTEGER NOT NULL,
    thread_id       INTEGER NOT NULL REFERENCES threads(id) ON DELETE CASCADE,
    CONSTRAINT unique_thread_like UNIQUE (user_id, thread_id)
);
CREATE INDEX ix_thread_likes_thread_id ON thread_likes (thread_id);
CREATE INDEX ix_thread_likes_user_id   ON thread_likes (user_id);

-- Comment Likes
CREATE TABLE comment_likes (
    id              SERIAL PRIMARY KEY,
    user_id         INTEGER NOT NULL,
    comment_id      INTEGER NOT NULL REFERENCES comments(id) ON DELETE CASCADE,
    CONSTRAINT unique_comment_like UNIQUE (user_id, comment_id)
);
CREATE INDEX ix_comment_likes_comment_id ON comment_likes (comment_id);
CREATE INDEX ix_comment_likes_user_id    ON comment_likes (user_id);

-- Event Outbox (fallback when Redis is down)
CREATE TABLE event_outbox (
    id              SERIAL PRIMARY KEY,
    channel         VARCHAR NOT NULL DEFAULT 'forum_events',
    payload         TEXT NOT NULL,                 -- JSON string
    created_at      TIMESTAMPTZ DEFAULT NOW()
);
```

### 2.1.3 notification_db — Notifications (SQLAlchemy)

```sql
CREATE TABLE notifications (
    id              SERIAL PRIMARY KEY,
    user_id         INTEGER,                       -- recipient
    type            VARCHAR(50) NOT NULL,           -- e.g. 'comment.created'
    title           VARCHAR(255) NOT NULL,
    message         TEXT NOT NULL,
    thread_id       INTEGER,
    comment_id      INTEGER,
    action_user_id  INTEGER,                       -- who triggered the notification
    is_read         BOOLEAN DEFAULT FALSE,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX ix_notifications_user_id ON notifications (user_id);
```

---

## 2.2 API Contracts (Request / Response)

### 2.2.1 Auth Service — Base: `/api/auth/`

#### POST `/register/`
```json
// Request
{ "username": "alice", "email": "alice@example.com", "password": "SecurePass123!" }

// Response 201
{ "id": 1, "username": "alice", "email": "alice@example.com", "role": "member" }

// Response 400
{ "username": ["A user with that username already exists."] }
```

#### POST `/login/`
```json
// Request
{ "username": "alice", "password": "SecurePass123!" }

// Response 200
{ "access": "eyJhbG...", "refresh": "eyJhbG..." }

// Response 401
{ "error": "Invalid credentials" }
```

#### GET/PUT `/profile/` (Auth required)
```json
// GET Response 200
{
  "id": 1, "username": "alice", "email": "alice@example.com",
  "role": "member", "bio": "Hello!", "avatar": "https://...",
  "date_joined": "2025-01-15T10:30:00Z"
}

// PUT Request (partial update)
{ "bio": "Updated bio", "avatar": "https://new-avatar.png" }
```

#### POST `/forgot-password/`
```json
// Request
{ "email": "alice@example.com" }

// Response 200
{ "message": "Password reset link sent", "reset_link": "/reset-password?token=abc123" }
```

#### GET `/users/all/?page=1&limit=10` (Admin only)
```json
// Response 200
{
  "users": [
    { "id": 1, "username": "alice", "email": "alice@example.com", "role": "member", "date_joined": "..." }
  ],
  "page": 1, "limit": 10, "total": 42, "total_pages": 5
}
```

#### GET `/users/basic/?ids=1,2,3` (Internal — used by forum-service)
```json
// Response 200
[
  { "id": 1, "username": "alice", "avatar": "https://..." },
  { "id": 2, "username": "bob",   "avatar": null }
]
```

### 2.2.2 Forum Service

#### GET `/threads/?page=1&limit=10`
```json
// Response 200
{
  "threads": [
    {
      "id": 1, "title": "First Thread", "description": "...",
      "username": "alice", "avatar": "https://...",
      "created_at": "2025-01-15T10:30:00Z"
    }
  ],
  "total": 100, "page": 1, "limit": 10, "total_pages": 10
}
```

#### POST `/threads/` (Auth required)
```json
// Request
{ "title": "New Thread", "description": "Thread body text" }

// Response 201
{
  "id": 5, "title": "New Thread", "description": "Thread body text",
  "username": "alice", "avatar": "https://...",
  "created_at": "2025-01-15T10:30:00Z"
}
```

#### POST `/comments/` (Auth required)
```json
// Request
{ "content": "Nice post! @bob what do you think?", "thread_id": 5, "parent_id": null }

// Response 201
{
  "id": 12, "content": "Nice post! @bob what do you think?",
  "username": "alice", "avatar": "https://...",
  "thread_id": 5, "parent_id": null,
  "created_at": "2025-01-15T10:35:00Z"
}
```

#### POST `/likes/thread/5` (Auth required)
```json
// Response 201
{ "message": "Thread liked", "thread_id": 5, "user_id": 1 }

// Response 400 (already liked)
{ "detail": "Already liked" }
```

### 2.2.3 Notification Service

#### GET `/notifications/` (Auth required)
```json
// Response 200
[
  {
    "id": 1, "type": "comment.mentioned", "title": "@alice mentioned you",
    "message": "in thread 'First Thread'",
    "thread_id": 5, "comment_id": 12, "action_user_id": 1,
    "is_read": false, "created_at": "2025-01-15T10:35:00Z"
  }
]
```

#### PATCH `/notifications/read-all` (Auth required)
```json
// Response 200
{ "message": "All notifications marked as read" }
```

---

## 2.3 Redis Data Structures

### 2.3.1 User Cache (String keys)

```
Key:     user:{user_id}
Value:   JSON string — {"id": 1, "username": "alice", "avatar": "https://..."}
TTL:     86400 seconds (24 hours)
Used by: forum-service (auth_client.py)
```

**Example:**
```
SET user:1 '{"id":1,"username":"alice","avatar":"https://img.png"}' EX 86400
GET user:1  →  '{"id":1,"username":"alice","avatar":"https://img.png"}'
```

### 2.3.2 Event Stream

```
Stream:          forum_events_stream
Consumer Group:  notif_service_group
Consumer:        notif_worker_{pid}
```

**Publish (forum-service):**
```
XADD forum_events_stream * data '{"event_type":"comment.created","thread_id":5,...}'
```

**Consume (notification-service):**
```
XREADGROUP GROUP notif_service_group notif_worker_1234
    COUNT 10 BLOCK 5000
    STREAMS forum_events_stream >
```

**Acknowledge:**
```
XACK forum_events_stream notif_service_group <message_id>
```

---

## 2.4 Event Payload Formats

All events are JSON strings stored in the `data` field of the Redis Stream entry.

### 2.4.1 comment.created
```json
{
  "event_type": "comment.created",
  "thread_id": 5,
  "comment_id": 12,
  "action_user_id": 1,
  "title": "New comment",
  "message": "alice commented on 'First Thread'"
}
```
→ Broadcast to all WebSockets subscribed to thread 5.

### 2.4.2 comment.mentioned
```json
{
  "event_type": "comment.mentioned",
  "target_user_id": 7,
  "thread_id": 5,
  "comment_id": 12,
  "action_user_id": 1,
  "title": "@alice mentioned you",
  "message": "in thread 'First Thread'"
}
```
→ Saved to `notifications` table + pushed via WebSocket to user 7.

### 2.4.3 thread.liked
```json
{
  "event_type": "thread.liked",
  "thread_id": 5,
  "action_user_id": 1,
  "target_user_id": 3,
  "title": "Thread liked",
  "message": "alice liked your thread 'First Thread'"
}
```
→ Broadcast to thread 5 subscribers + personal notification to thread owner (user 3).

### 2.4.4 thread.unliked
```json
{
  "event_type": "thread.unliked",
  "thread_id": 5,
  "action_user_id": 1
}
```
→ Broadcast to thread 5 subscribers only (no personal notification).

### 2.4.5 comment.liked
```json
{
  "event_type": "comment.liked",
  "thread_id": 5,
  "comment_id": 12,
  "action_user_id": 1,
  "target_user_id": 7,
  "title": "Comment liked",
  "message": "alice liked your comment"
}
```
→ Broadcast to thread 5 subscribers + personal notification to comment author.

---

## 2.5 WebSocket Protocol

### 2.5.1 Connection

```
ws://localhost:8003/ws?token=<JWT_ACCESS_TOKEN>
```

Server validates JWT → extracts `user_id` → registers socket in `ConnectionManager`.

### 2.5.2 Client → Server Messages

**Subscribe to thread updates:**
```json
{ "action": "subscribe_thread", "thread_id": 5 }
```

**Unsubscribe from thread:**
```json
{ "action": "unsubscribe_thread", "thread_id": 5 }
```

### 2.5.3 Server → Client Messages

**Subscription confirmation:**
```json
{ "action": "subscribed", "thread_id": 5 }
```

**Personal notification:**
```json
{
  "event_type": "comment.mentioned",
  "notification_id": 42,
  "title": "@alice mentioned you",
  "message": "in thread 'First Thread'",
  "thread_id": 5,
  "comment_id": 12,
  "action_user_id": 1,
  "created_at": "2025-01-15T10:35:00.000Z",
  "is_read": false
}
```

**Thread broadcast (live update):**
```json
{
  "event_type": "comment.created",
  "thread_id": 5,
  "comment_id": 12,
  "action_user_id": 1,
  "title": "New comment",
  "message": "alice commented on 'First Thread'"
}
```

### 2.5.4 Connection Lifecycle

```
Client                              Server
  │                                    │
  ├── WS connect /ws?token=JWT ───────►│
  │                                    ├── Decode JWT → user_id
  │◄── accept ────────────────────────┤   manager.connect(user_id, ws)
  │                                    │
  │── {"action":"subscribe_thread",    │
  │    "thread_id": 5} ──────────────►│   manager.subscribe_thread(ws, 5)
  │◄── {"action":"subscribed",         │
  │     "thread_id": 5} ──────────────┤
  │                                    │
  │◄── {event_type: "comment.created"} │   ← someone commented on thread 5
  │◄── {event_type: "comment.mentioned"│   ← you were @mentioned
  │     notification_id: 42, ...}      │
  │                                    │
  │── {"action":"unsubscribe_thread",  │
  │    "thread_id": 5} ──────────────►│   manager.unsubscribe_thread(ws, 5)
  │                                    │
  ├── disconnect ─────────────────────►│   manager.disconnect(user_id, ws)
  │                                    │
```

---

## 2.6 Module Structure (Per Service)

### 2.6.1 Auth Service (Django)

```
auth-service/
├── manage.py                    # Django CLI entry point
├── auth_service/
│   ├── settings.py              # DB config, JWT config, CORS, email
│   ├── urls.py                  # Root URL dispatcher
│   └── wsgi.py                  # WSGI entry point
└── accounts/
    ├── models.py                # User model (AbstractUser + role/bio/avatar)
    ├── serializers.py           # DRF serializers (register, login, profile)
    ├── views.py                 # API views (register, login, profile, password, admin)
    ├── urls.py                  # Route mappings (/register, /login, etc.)
    └── migrations/              # Django auto-generated schema migrations
```

### 2.6.2 Forum Service (FastAPI)

```
forum-service/
├── app/
│   ├── main.py                  # FastAPI app + lifespan (outbox flusher)
│   ├── create_tables.py         # One-off script to create tables
│   ├── create_indexes.py        # One-off script to create indexes
│   ├── core/
│   │   └── auth.py              # JWT decode dependency (get_current_user)
│   ├── db/
│   │   └── database.py          # Async SQLAlchemy engine + session factory
│   ├── models/
│   │   ├── thread.py            # Thread SQLAlchemy model
│   │   ├── comment.py           # Comment SQLAlchemy model (nested via parent_id)
│   │   ├── like.py              # ThreadLike + CommentLike models
│   │   └── event_outbox.py      # EventOutbox model (fallback storage)
│   ├── routers/
│   │   ├── thread.py            # /threads/ endpoints
│   │   ├── comment.py           # /comments/ endpoints
│   │   └── like.py              # /likes/ endpoints
│   ├── schemas/
│   │   ├── thread.py            # Pydantic models (ThreadCreate, ThreadResponse, etc.)
│   │   ├── comment.py           # Pydantic models (CommentCreate, CommentResponse)
│   │   └── like.py              # Pydantic models (LikeResponse)
│   └── services/
│       ├── auth_client.py       # HTTP client for auth-service + Redis cache
│       ├── event_publisher.py   # Redis XADD + outbox fallback
│       ├── mention_parser.py    # @mention regex parser
│       ├── redis_pool.py        # Shared Redis connection pool + DummyRedis
│       └── response_builder.py  # Attaches username/avatar to responses
```

### 2.6.3 Notification Service (FastAPI)

```
notification-service/
├── app/
│   ├── main.py                  # FastAPI app + lifespan (consumer + cleanup tasks)
│   ├── create_tables.py         # One-off script to create tables
│   ├── core/
│   │   ├── auth.py              # JWT decode dependency (HTTP routes)
│   │   └── ws_auth.py           # JWT decode for WebSocket query param
│   ├── db/
│   │   └── database.py          # Async SQLAlchemy engine + session factory
│   ├── models/
│   │   └── notification.py      # Notification SQLAlchemy model
│   ├── routers/
│   │   ├── notification.py      # /notifications/ REST endpoints
│   │   └── ws.py                # /ws WebSocket endpoint
│   ├── schemas/
│   │   └── notification.py      # Pydantic models (NotificationResponse)
│   └── services/
│       ├── connection_manager.py # Unified WebSocket manager
│       └── event_consumer.py    # Redis Streams XREADGROUP consumer
```

---

## 2.7 JWT Token Structure

### 2.7.1 Access Token Payload (decoded)

```json
{
  "token_type": "access",
  "exp": 1737000000,
  "iat": 1736996400,
  "jti": "unique-token-id",
  "user_id": 1,
  "role": "member"
}
```

| Field | Description |
| --- | --- |
| `token_type` | Always `"access"` |
| `exp` | Expiry — 60 minutes from issuance |
| `iat` | Issued at timestamp |
| `jti` | Unique token identifier (for blacklisting) |
| `user_id` | Integer user ID from `accounts_user` |
| `role` | `"admin"` \| `"moderator"` \| `"member"` |

### 2.7.2 Token Lifecycle

```
Login → access (60min) + refresh (7 days)
         │
         ├── Access expired? → POST /api/auth/token/refresh/
         │                     → New access + new refresh
         │                     → Old refresh blacklisted
         │
         └── Refresh expired? → User must log in again
```

---

## 2.8 Background Tasks

| Service | Task | Interval | Purpose |
| --- | --- | --- | --- |
| Forum | `_outbox_flusher()` | 10 seconds | Push pending outbox events to Redis Stream |
| Notification | `start_redis_subscriber()` | Continuous | XREADGROUP loop — consume events from stream |
| Notification | `_cleanup_old_notifications()` | 24 hours | DELETE notifications older than 30 days |

---

## 2.9 Error Handling Strategy

### 2.9.1 Forum Service — Event Publishing

```
publish_event(event)
    ├── Try: redis.xadd(stream, event)  → Success
    │
    └── Catch: Redis error
            └── _save_to_outbox(event)
                    ├── Try: INSERT into event_outbox → Saved
                    └── Catch: DB error → CRITICAL log (event lost)
```

### 2.9.2 Notification Service — Event Consumption

```
XREADGROUP loop
    ├── Read batch of messages
    │
    ├── For each message:
    │   ├── handle_event(event)
    │   │   ├── Broadcast to thread subscribers
    │   │   └── Save notification + push to user
    │   │
    │   └── XACK (acknowledge processed)
    │
    └── On error:
        ├── Exponential backoff reconnect (1s → 30s)
        └── _process_pending() on reconnect (reprocess unACKed)
```

### 2.9.3 Frontend — WebSocket Reconnection

```
WebSocket disconnects
    │
    ├── Wait 1 second → reconnect attempt
    ├── Fail → wait 2 seconds → retry
    ├── Fail → wait 4 seconds → retry
    ├── ...exponential backoff...
    └── Cap at 30 seconds between retries
    
On reconnect:
    ├── Re-authenticate with current JWT
    └── Re-subscribe to any active thread rooms
```

---

## 2.10 Sequence Diagrams

### 2.10.1 User Posts a Comment with @mention

```
Browser          Forum Service        Redis         Notif Service      DB (forum)    DB (notif)
   │                   │                │                │                │              │
   ├─POST /comments/──►│                │                │                │              │
   │ {content, tid}    │                │                │                │              │
   │                   ├─INSERT comment─┼────────────────┼───────────────►│              │
   │                   │                │                │                │              │
   │                   ├─Parse @mentions│                │                │              │
   │                   │ → ["alice"]    │                │                │              │
   │                   │                │                │                │              │
   │                   ├─GET /users/by-usernames?usernames=alice ──► Auth Service       │
   │                   │◄── {id:7, username:"alice"} ◄──────────── Auth Service         │
   │                   │                │                │                │              │
   │                   ├─XADD ─────────►│                │                │              │
   │                   │ comment.created│                │                │              │
   │                   ├─XADD ─────────►│                │                │              │
   │                   │ comment.mentioned               │                │              │
   │                   │ target_user_id=7│               │                │              │
   │◄──201 Created─────┤                │                │                │              │
   │                   │                │                │                │              │
   │                   │                ├─XREADGROUP────►│                │              │
   │                   │                │                ├─INSERT notif───┼─────────────►│
   │                   │                │                ├─WS push to user 7             │
   │                   │                │                ├─WS broadcast to thread 5      │
   │                   │                │◄──XACK─────────┤                │              │
```

### 2.10.2 User Opens Thread Detail Page

```
Browser              Forum Service       Auth Service       Redis (cache)
   │                      │                   │                  │
   ├─GET /threads/5 ─────►│                   │                  │
   │                      ├─SELECT thread─────┼──────────────────┤
   │                      │ user_id=3         │                  │
   │                      │                   │                  │
   │                      ├─GET user:3 ───────┼─────────────────►│
   │                      │◄─ cache HIT ──────┼──────────────────┤
   │                      │  {username:"bob"} │                  │
   │◄─200 {thread + user}─┤                   │                  │
   │                      │                   │                  │
   │                      │  (cache MISS flow)│                  │
   │                      ├─GET /users/basic/?ids=3 ────────────►│
   │                      │◄─ [{id:3, username:"bob", avatar:..}]│
   │                      ├─SET user:3 EX 86400 ────────────────►│
```

---

## 2.11 Configuration Reference

### 2.11.1 Environment Variables

| Variable | Service | Example | Description |
| --- | --- | --- | --- |
| `DATABASE_URL` | Forum, Notification | `postgresql://postgres:postgres@localhost:5433/forum_db` | PostgreSQL connection string |
| `JWT_SECRET_KEY` | All 3 | `my_very_long_super_secure_secret_key_2026_abc123` | Shared JWT signing key |
| `JWT_ALGORITHM` | Forum, Notification | `HS256` | JWT algorithm |
| `REDIS_URL` | Forum, Notification | `redis://localhost:6379/0` | Redis connection string |
| `AUTH_SERVICE_URL` | Forum | `http://127.0.0.1:8001` | Auth service base URL |

### 2.11.2 Ports

| Service | Port | Protocol |
| --- | --- | --- |
| Auth Service | 8001 | HTTP |
| Forum Service | 8000 | HTTP |
| Notification Service | 8003 | HTTP + WS |
| Frontend (Vite dev) | 5173 | HTTP |
| PostgreSQL | 5433 (host) → 5432 (container) | TCP |
| Redis | 6379 | TCP |

### 2.11.3 Key Constants

| Constant | Value | Location |
| --- | --- | --- |
| Access token TTL | 60 minutes | `auth-service/settings.py` |
| Refresh token TTL | 7 days | `auth-service/settings.py` |
| User cache TTL | 86400s (24h) | `forum-service/auth_client.py` |
| Outbox flush interval | 10 seconds | `forum-service/main.py` |
| Notification cleanup | 24 hours | `notification-service/main.py` |
| Notification max age | 30 days | `notification-service/main.py` |
| WS reconnect backoff | 1s → 30s cap | `frontend/notificationStore.js` |
| Redis max connections | 20 | `forum-service/redis_pool.py` |
