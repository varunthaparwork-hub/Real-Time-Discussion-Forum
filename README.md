# Real-Time Discussion Forum

A full-stack, microservices-based discussion forum with real-time notifications, @mentions, nested comments, likes, and role-based access control.

---

## Table of Contents

- [Tech Stack](#tech-stack)
- [Architecture Overview](#architecture-overview)
- [Service Breakdown](#service-breakdown)
  - [Auth Service](#1-auth-service-port-8001)
  - [Forum Service](#2-forum-service-port-8000)
  - [Notification Service](#3-notification-service-port-8003)
  - [Frontend](#4-frontend-port-5173)
- [How Services Communicate](#how-services-communicate)
- [Database Schema](#database-schema)
- [API Endpoints](#api-endpoints)
- [Real-Time Flow](#real-time-event-flow)
- [Resilience & Fallbacks](#resilience--fallbacks)
- [Testing](#testing)
- [Setup & Installation](#setup--installation)
- [Architecture Decision Records (ADR)](#architecture-decision-records-adr)
- [HLD & LLD](docs/HLD_LLD.md)

---

## Tech Stack

| Layer            | Technology                                |
| ---------------- | ----------------------------------------- |
| Frontend         | React 19, Zustand, Tailwind CSS 4, Vite 8 |
| Auth Service     | Django 6.0, Django REST Framework, SimpleJWT |
| Forum Service    | FastAPI, SQLAlchemy (async), asyncpg       |
| Notification Service | FastAPI, SQLAlchemy (async), asyncpg   |
| Databases        | PostgreSQL 15 (3 separate databases)      |
| Cache / Broker   | Redis 7 (caching + Streams)               |
| Real-Time        | WebSocket (native, via FastAPI)            |
| Containerisation | Docker Compose (PostgreSQL + Redis)        |

---

## Architecture Overview

```
┌────────────────────────────────────────────────────────────┐
│                     Frontend (React)                       │
│               http://localhost:5173                        │
│  Zustand stores │ Axios HTTP clients │ WebSocket client    │
└───────┬─────────┼────────────────────┼─────────────────────┘
        │ REST    │ REST               │ WS
        ▼         ▼                    ▼
 ┌──────────┐  ┌──────────┐    ┌──────────────────┐
 │  Auth    │  │  Forum   │    │  Notification    │
 │  Service │  │  Service │    │  Service         │
 │  :8001   │  │  :8000   │    │  :8003           │
 │  Django  │  │  FastAPI │    │  FastAPI         │
 └──────────┘  └────┬─────┘    └───────┬──────────┘
       │             │                  │
       │        ┌────┴────┐        ┌────┴────┐
       │        │  Redis  │◄───────│ Streams │
       │        │  :6379  │  consume│ Consumer│
       │        └─────────┘        └─────────┘
       │             │
  ┌────┴────┐   ┌────┴────┐    ┌──────────────┐
  │auth_db  │   │forum_db │    │notification_db│
  │(Postgres)│  │(Postgres)│   │  (Postgres)   │
  └─────────┘   └─────────┘    └──────────────┘
```

Each service has its **own database** — they never share tables. Cross-service data is fetched via HTTP or resolved from JWT tokens.

---

## Service Breakdown

### 1. Auth Service (port 8001)

**Framework:** Django + Django REST Framework + SimpleJWT

Handles everything user-related:
- **Registration** — validates input, hashes password, creates user
- **Login** — verifies credentials, returns JWT access + refresh tokens
- **Profile management** — view/edit bio, avatar
- **Password reset** — generates reset links (email or response)
- **Role-based access** — admin, moderator, member
- **User lookup APIs** — bulk endpoints used internally by forum-service

**Key design:** The JWT token contains the user's `role` claim, so other services can check permissions without calling auth-service.

### 2. Forum Service (port 8000)

**Framework:** FastAPI + async SQLAlchemy + asyncpg

The core discussion engine:
- **Threads** — CRUD with pagination and full-text search
- **Comments** — nested replies (parent_id), @mention parsing
- **Likes** — like/unlike threads and comments (unique constraint per user)
- **Event publishing** — pushes events to Redis Streams on every comment, like, or mention

**Key design:** Verifies JWT tokens **locally** using the shared secret key — no HTTP call to auth-service on every request. User display data (username, avatar) is fetched from auth-service and cached in Redis for 24 hours.

### 3. Notification Service (port 8003)

**Framework:** FastAPI + async SQLAlchemy + asyncpg

Handles real-time delivery and persistence of notifications:
- **Redis Streams consumer** — listens for events from forum-service
- **Notification storage** — saves to PostgreSQL for history
- **WebSocket server** — pushes live updates to connected users
- **REST API** — fetch notifications, mark as read, mark all read
- **Auto-cleanup** — deletes notifications older than 30 days

**Key design:** One unified WebSocket per user handles both personal notifications (mentions, likes) and thread-level live updates (new comments appearing in real time).

### 4. Frontend (port 5173)

**Framework:** React 19 + Zustand + Tailwind CSS + Vite

- **Pages:** Home, Thread Detail, Create Thread, Login, Register, Profile, Dashboard, Forgot/Reset Password
- **State management:** Zustand stores for auth, notifications, and theme
- **Real-time:** Single WebSocket connection with JSON-based subscribe/unsubscribe for thread rooms
- **Dark mode:** Toggle with localStorage persistence
- **Role-based UI:** Admin dashboard with user management and thread moderation

---

## How Services Communicate

| From → To | Method | Purpose |
| --- | --- | --- |
| Frontend → Auth Service | REST (Axios) | Login, register, profile, password reset |
| Frontend → Forum Service | REST (Axios) | Threads, comments, likes |
| Frontend → Notification Service | REST (Axios) | Fetch/mark notifications |
| Frontend → Notification Service | WebSocket | Live notifications + thread updates |
| Forum Service → Auth Service | HTTP (httpx) | Fetch username/avatar for posts (cached in Redis) |
| Forum Service → Auth Service | Shared JWT secret | Verify tokens locally without HTTP call |
| Forum Service → Notification Service | Redis Streams | Publish events (comment created, liked, mentioned) |

---

## Database Schema

### auth_db (PostgreSQL — managed by Django)

| Table | Key Columns |
| --- | --- |
| `accounts_user` | id, username, email, password (hashed), role, bio, avatar, date_joined |

### forum_db (PostgreSQL — managed by SQLAlchemy)

| Table | Key Columns |
| --- | --- |
| `threads` | id, title, description, user_id, created_at |
| `comments` | id, content, user_id, thread_id, parent_id (nullable), created_at |
| `thread_likes` | id, user_id, thread_id (unique constraint) |
| `comment_likes` | id, user_id, comment_id (unique constraint) |
| `event_outbox` | id, channel, payload (JSON), created_at |

### notification_db (PostgreSQL — managed by SQLAlchemy)

| Table | Key Columns |
| --- | --- |
| `notifications` | id, user_id, type, title, message, thread_id, comment_id, action_user_id, is_read, created_at |

---

## API Endpoints

### Auth Service — `/api/auth/`

| Method | Endpoint | Auth | Description |
| --- | --- | --- | --- |
| POST | `/register/` | No | Create account |
| POST | `/login/` | No | Get JWT tokens |
| POST | `/forgot-password/` | No | Request password reset link |
| POST | `/reset-password/` | No | Set new password with token |
| GET/PUT | `/profile/` | Yes | Own profile |
| GET | `/profile/:username/` | No | Public profile |
| GET | `/users/all/?page=1&limit=10` | Admin | Paginated user list |
| PUT | `/users/:id/role/` | Admin | Change user role |
| GET | `/users/basic/?ids=1,2,3` | Internal | Bulk user lookup by IDs |
| GET | `/users/by-usernames/?usernames=a,b` | Internal | Bulk user lookup by usernames |

### Forum Service

| Method | Endpoint | Auth | Description |
| --- | --- | --- | --- |
| GET | `/threads/?page=1&limit=10` | No | List threads (paginated) |
| GET | `/threads/search?q=keyword` | No | Search threads |
| POST | `/threads/` | Yes | Create thread |
| GET | `/threads/:id` | No | Get thread |
| PUT | `/threads/:id` | Owner/Admin | Update thread |
| DELETE | `/threads/:id` | Owner/Admin | Delete thread |
| GET | `/comments/thread/:threadId` | No | Get comments for thread |
| POST | `/comments/` | Yes | Create comment |
| PUT | `/comments/:id` | Owner/Admin | Update comment |
| DELETE | `/comments/:id` | Owner/Admin | Delete comment |
| POST | `/likes/thread/:id` | Yes | Like thread |
| DELETE | `/likes/thread/:id` | Yes | Unlike thread |
| GET | `/likes/thread/:id/count` | No | Get thread like count |
| GET | `/likes/thread/:id/status` | Yes | Check if user liked thread |
| POST | `/likes/comment/:id` | Yes | Like comment |
| DELETE | `/likes/comment/:id` | Yes | Unlike comment |

### Notification Service

| Method | Endpoint | Auth | Description |
| --- | --- | --- | --- |
| GET | `/notifications/` | Yes | Get my notifications |
| PATCH | `/notifications/:id/read` | Yes | Mark one as read |
| PATCH | `/notifications/read-all` | Yes | Mark all as read |
| WS | `/ws?token=JWT` | Token | Unified WebSocket |

---

## Real-Time Event Flow

```
User comments on Thread #5
         │
         ▼
  ┌──────────────┐
  │ Forum Service │──► Redis Stream (XADD)
  └──────────────┘    "forum_events_stream"
                           │
                           ▼
                  ┌──────────────────┐
                  │ Notification Svc │  (XREADGROUP consumer)
                  │                  │
                  │ 1. Save to DB    │
                  │ 2. Push via WS   │
                  └──────┬───────────┘
                         │
            ┌────────────┼────────────┐
            ▼            ▼            ▼
     Thread #5       Thread owner   @mentioned
     subscribers     notification   users get
     see new         bell rings     notification
     comment live
```

**Event types published:**
- `comment.created` — new comment on a thread
- `comment.mentioned` — user was @mentioned in a comment
- `thread.liked` / `thread.unliked` — thread like changes
- `comment.liked` — comment was liked

---

## Resilience & Fallbacks

| Scenario | What Happens |
| --- | --- |
| **Redis down on startup** | Forum-service uses `DummyRedis` — app runs without caching. Events go to outbox table. |
| **Redis down mid-operation** | `publish_event()` catches the error, saves event to `event_outbox` table in PostgreSQL. |
| **Redis recovers** | Background task (`_outbox_flusher`) runs every 10s, pushes pending outbox events to Redis Streams. |
| **Notification-service down** | Events stay in Redis Stream. Consumer group tracks position — events are redelivered on restart. |
| **Consumer crashes mid-event** | Unacknowledged events are reprocessed via `_process_pending()` on reconnection (XREADGROUP with id "0"). |
| **Auth-service down** | Forum-service returns placeholder `User#<id>` instead of crashing. API never 500s. |
| **WebSocket disconnects** | Frontend reconnects with exponential backoff (1s → 2s → 4s → ... → 30s cap). |
| **Old notifications** | Background task deletes notifications older than 30 days every 24 hours. |

---

## Testing

All three backend services have comprehensive test suites — **83 tests total**, covering unit tests, API integration tests, input sanitization, auth flows, and edge cases.

### Test Summary

| Service | Framework | Tests | Command |
| --- | --- | --- | --- |
| Forum Service | pytest + pytest-asyncio + httpx | 52 | `cd forum-service && pytest tests/ -v` |
| Auth Service | Django TestCase + DRF APIClient | 22 | `cd auth-service && python manage.py test accounts -v 2` |
| Notification Service | pytest + pytest-asyncio + httpx | 9 | `cd notification-service && pytest tests/ -v` |

### Forum Service Tests (52)

**Unit Tests** (`tests/test_unit.py` — 25 tests):
- `TestSanitizer` (10) — XSS prevention, HTML stripping, rich text allowlists, attribute removal
- `TestMentionParser` (9) — @mention extraction, deduplication, email exclusion, edge cases
- `TestResponseBuilder` (6) — thread/comment serialization with user maps, unknown user fallback

**API Integration Tests** (`tests/test_api.py` — 27 tests):
- `TestThreadEndpoints` (12) — CRUD, auth enforcement, XSS sanitization, pagination, search, ownership checks
- `TestCommentEndpoints` (7) — CRUD, nested replies, nonexistent thread, XSS in comments
- `TestLikeEndpoints` (8) — like/unlike, duplicate rejection, like counts, like status, batch counts

**Test infrastructure** (`tests/conftest.py`):
- SQLite test database (no PostgreSQL needed)
- Mocked `auth_client` (no HTTP calls) and `event_publisher` (no Redis needed)
- JWT token generator for authenticated requests
- Rate limiter disabled during tests

### Auth Service Tests (22)

**Django TestCase tests** (`accounts/tests.py`):
- `TestRegistration` (5) — success, duplicate username, password mismatch, weak password, missing fields
- `TestLogin` (4) — success, wrong password, nonexistent user, empty body
- `TestProfile` (5) — authenticated get, unauthenticated 401, bio/avatar update, XSS sanitization
- `TestUserLookup` (4) — bulk ID/username lookup, empty/nonexistent results
- `TestRoleManagement` (2) — admin can change role, non-admin gets 403
- `TestSerializerSanitization` (2) — bleach strips HTML from bio, empty bio allowed

### Notification Service Tests (9)

**API tests** (`tests/test_notifications.py`):
- `TestGetNotifications` (4) — empty list, seeded data, unauthenticated 401, user isolation
- `TestMarkRead` (3) — mark as read, nonexistent 404, other user's notification 404
- `TestMarkAllRead` (2) — mark all read, no-op when no notifications

### Running All Tests

```bash
# Forum service (52 tests)
cd forum-service
pip install pytest pytest-asyncio httpx aiosqlite   # one-time
pytest tests/ -v

# Auth service (22 tests)
cd auth-service
python manage.py test accounts -v 2

# Notification service (9 tests)
cd notification-service
pip install pytest pytest-asyncio httpx aiosqlite   # one-time
pytest tests/ -v
```

> **Note:** Tests use SQLite — no PostgreSQL or Redis needed. All external dependencies are mocked.

---

## Setup & Installation

### Prerequisites

- Python 3.12+
- Node.js 18+
- Docker & Docker Compose

### Option A: One-Command Docker Setup (Recommended)

Run **everything** (PostgreSQL, Redis, all 3 backend services, and the frontend) with a single command:

```bash
cd docker
docker-compose up --build
```

This will start:
- **PostgreSQL** on port 5433 (creates `auth_db`, `forum_db`, `notification_db`)
- **Redis** on port 6379
- **Auth Service** on port 8001
- **Forum Service** on port 8000
- **Notification Service** on port 8003
- **Frontend** on port 5173

Open **http://localhost:5173** in your browser.

To stop everything:
```bash
docker-compose down
```

To stop and also delete the database data:
```bash
docker-compose down -v
```

### Option B: Manual Setup (for development)

#### 1. Start Infrastructure

```bash
cd docker
docker-compose up -d postgres redis
```

This starts PostgreSQL (port 5433) and Redis (port 6379), and creates the three databases (`auth_db`, `forum_db`, `notification_db`).

### 2. Auth Service

```bash
cd auth-service
python -m venv .venv
.venv\Scripts\activate        # Windows
pip install -r requirements.txt

# Create .env file
echo JWT_SECRET_KEY=my_very_long_super_secure_secret_key_2026_abc123 > .env

python manage.py migrate
python manage.py runserver 8001
```

### 3. Forum Service

```bash
cd forum-service
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt

# Create .env file with:
# DATABASE_URL=postgresql://postgres:postgres@localhost:5433/forum_db
# JWT_SECRET_KEY=my_very_long_super_secure_secret_key_2026_abc123
# REDIS_URL=redis://localhost:6379/0
# AUTH_SERVICE_URL=http://127.0.0.1:8001

python -m app.create_tables
python -m app.create_indexes
uvicorn app.main:app --reload --port 8000
```

### 4. Notification Service

```bash
cd notification-service
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt

# Create .env file with:
# DATABASE_URL=postgresql://postgres:postgres@localhost:5433/notification_db
# JWT_SECRET_KEY=my_very_long_super_secure_secret_key_2026_abc123
# REDIS_URL=redis://localhost:6379/0

python -m app.create_tables
uvicorn app.main:app --reload --port 8003
```

### 5. Frontend

```bash
cd frontend
npm install
npm run dev
```

Open **http://localhost:5173** in your browser.

---

## Architecture Decision Records (ADR)

9 ADRs covering every major design decision — from microservices vs monolith, to JWT strategy, Redis Streams, outbox pattern, WebSocket unification, caching, database-per-service, framework choices, and state management.

👉 **[Read the full ADRs →](docs/ADR.md)**

