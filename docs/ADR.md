# Architecture Decision Records (ADR)

This document captures the key architectural decisions made during the design and development of the Real-Time Discussion Forum. Each ADR explains the decision, the reasoning behind it, the trade-offs considered, and the alternatives that were evaluated.

---

## ADR-1: Microservices vs Monolith

**Decision:** Split the application into 3 backend services (auth, forum, notification) instead of one monolith.

**Why:**
- Each service can be developed, deployed, and scaled independently.
- Auth is a distinct bounded context that rarely changes; forum and notification have very different workloads (read-heavy vs event-heavy).
- Allows mixing frameworks — Django (auth) and FastAPI (forum/notification) — using the best tool for each job.

**Pros:**
- Independent scaling — can scale the forum service without scaling auth.
- Technology freedom — Django's built-in auth system is excellent; FastAPI's async is better for real-time.
- Fault isolation — auth-service crashing doesn't stop forum reads.

**Cons:**
- Increased operational complexity — three services to deploy, monitor, and debug.
- Network calls between services add latency (e.g., forum → auth for user data).
- Data consistency is harder — no cross-service transactions.

**Alternatives considered:**

| Alternative | Pros | Cons |
| --- | --- | --- |
| **Django monolith** | Simpler deployment, shared DB, built-in admin | Can't use async for WebSockets efficiently, harder to scale forum independently |
| **FastAPI monolith** | Single codebase, single DB, simpler | Would need to build auth from scratch (no Django auth), single point of failure |
| **4+ services (separate likes, search)** | Even finer granularity | Way too complex for this scale, network overhead for every like |

---

## ADR-2: JWT with Shared Secret (HS256) for Inter-Service Auth

**Decision:** All services share the same JWT secret key. Forum-service and notification-service verify tokens locally without calling auth-service.

**Why:**
- Zero-latency auth — no HTTP round-trip to verify every request.
- The JWT contains `user_id` and `role`, so services have everything they need.
- Simple to implement and reason about.

**Pros:**
- Every request is verified in microseconds (just a local decode).
- Auth-service being down doesn't block forum/notification reads.
- No single point of failure for authentication.

**Cons:**
- Shared secret — if one service is compromised, all tokens are compromised.
- Can't revoke individual tokens without a blacklist (refresh token rotation helps).
- Role changes don't take effect until the current access token expires (60 min).

**Alternatives considered:**

| Alternative | Pros | Cons |
| --- | --- | --- |
| **RS256 (asymmetric keys)** | Auth-service holds private key; others only have public key. Compromise of forum-service doesn't leak the signing key. | More complex key management, key rotation needs coordination |
| **Auth-service verification on every request** | Centralized control, instant revocation | Single point of failure, added latency on every request, auth-service becomes bottleneck |
| **API Gateway (e.g., Kong, Nginx)** | Centralized auth, rate limiting, logging | Another infrastructure piece to manage, adds latency, potential SPOF |
| **OAuth2 / OpenID Connect** | Industry standard, supports third-party login | Overkill for an internal system with no third-party clients |

---

## ADR-3: Redis Streams over Pub/Sub for Event Delivery

**Decision:** Use Redis Streams (XADD / XREADGROUP) instead of Redis Pub/Sub for event delivery from forum-service to notification-service.

**Why:**
- Pub/Sub is fire-and-forget — if notification-service is offline, events are lost forever.
- Streams persist events in Redis and track consumer position with consumer groups.
- Unacknowledged events are automatically redelivered after a consumer restart.

**Pros:**
- **Durable** — events survive consumer downtime.
- **At-least-once delivery** — unacknowledged events are reprocessed.
- **Consumer groups** — can scale to multiple notification workers.
- **Replay** — can re-read old events if needed.

**Cons:**
- Slightly more complex API than simple Pub/Sub.
- Events are still lost if Redis itself goes down (mitigated by outbox pattern).
- Need to manage consumer group and acknowledgements.

**Alternatives considered:**

| Alternative | Pros | Cons |
| --- | --- | --- |
| **Redis Pub/Sub** | Simpler API, lower latency | Fire-and-forget — any consumer downtime = lost events |
| **RabbitMQ** | Mature, durable, routing patterns, dead-letter queues | Extra infrastructure, more complex setup, overkill for this scale |
| **Apache Kafka** | Extremely durable, ordered, replayable, handles massive throughput | Very heavy infrastructure, complex ops, way too much for this project size |
| **Direct HTTP (forum → notification)** | Simple, no broker needed | Tight coupling, forum-service blocks waiting for notification-service, no retry |
| **PostgreSQL LISTEN/NOTIFY** | No extra infrastructure needed | Limited payload size (8000 bytes), no persistence, no consumer groups |

---

## ADR-4: Database Outbox Pattern for Event Reliability

**Decision:** When Redis is unavailable, save events to an `event_outbox` PostgreSQL table. A background task flushes them to Redis every 10 seconds.

**Why:**
- Redis Streams solve consumer downtime, but not Redis downtime.
- The outbox pattern ensures **zero event loss** — if Redis is down, events are persisted in the same PostgreSQL transaction as the data change.

**Pros:**
- **Zero event loss** — events are always saved somewhere (Redis or PostgreSQL).
- **Automatic recovery** — background flusher pushes events when Redis comes back.
- **No manual intervention** — self-healing.

**Cons:**
- Events are delayed when Redis is down (up to 10 seconds per flush cycle).
- Adds complexity — two event paths (Redis direct vs outbox).
- Outbox table can grow if Redis is down for extended periods.

**Alternatives considered:**

| Alternative | Pros | Cons |
| --- | --- | --- |
| **Just drop events when Redis is down** | Simplest possible approach | Notifications are lost, bad UX |
| **Retry in-process with exponential backoff** | No outbox table needed | Blocks the API request while retrying, user waits |
| **Write-ahead log (WAL) tailing** | Can capture every DB change automatically | Very complex, needs CDC tooling (Debezium), heavy infra |
| **Dual-write (write to Redis AND DB always)** | Always consistent | Double write latency on every request, risk of partial failure |

---

## ADR-5: One Unified WebSocket vs Separate Sockets

**Decision:** Use a single WebSocket connection per user that handles both personal notifications and thread-level live updates, with JSON-based subscribe/unsubscribe messages.

**Why:**
- The two use cases (notifications and thread updates) have different lifecycles — notifications are persistent, thread subscriptions are temporary.
- Despite different lifecycles, a single socket reduces connection overhead and simplifies the frontend.

**Pros:**
- **One connection** — less resource usage, simpler reconnection logic.
- **Multiplexed** — notifications and thread events on the same pipe.
- **Dynamic** — subscribe/unsubscribe to threads without reconnecting.

**Cons:**
- Server-side routing logic is more complex (must parse JSON messages).
- If the socket drops, both notifications and thread updates stop (but reconnection handles this).
- Thread messages are sent even if the user only cares about notifications (negligible bandwidth).

**Alternatives considered:**

| Alternative | Pros | Cons |
| --- | --- | --- |
| **Two separate WebSockets** (notification + thread) | Clean separation of concerns, independent lifecycles | Double the connections, double the auth handshakes, more complex frontend |
| **Server-Sent Events (SSE) for notifications** | Simpler than WebSocket (one-way), auto-reconnect built-in | Can't do bidirectional (no subscribe/unsubscribe), separate mechanism needed for thread updates |
| **Long polling** | Works everywhere, no WebSocket support needed | Higher latency, more server load, not truly real-time |
| **Socket.IO** | Auto-reconnection, room management, fallback transports | Extra dependency, heavier, abstracts away control |

---

## ADR-6: Redis Cache for Cross-Service User Data

**Decision:** Cache user data (username, avatar, role) in Redis with a 24-hour TTL instead of calling auth-service on every request.

**Why:**
- Every thread and comment needs the author's username/avatar for display.
- Without caching, displaying a page with 50 comments = 50 HTTP calls to auth-service.
- Usernames and avatars rarely change, making them excellent cache candidates.

**Pros:**
- **~0ms** for cached lookups vs ~10ms+ for HTTP calls.
- Reduces auth-service load dramatically.
- Granular caching — only fetch uncached user IDs from auth-service.

**Cons:**
- Stale data — if a user changes their avatar, it takes up to 24h to reflect everywhere.
- Redis dependency — if Redis is down, falls back to HTTP (slower but works).
- Cache invalidation complexity — no active invalidation on profile changes.

**Alternatives considered:**

| Alternative | Pros | Cons |
| --- | --- | --- |
| **No cache (always call auth-service)** | Always fresh data | Extremely slow under load, auth-service becomes bottleneck |
| **In-memory cache (per-process dict)** | No Redis dependency, zero latency | Not shared across workers, cache cold on restart, memory pressure |
| **Replicate user data to forum_db** | Fastest reads, no network calls at all | Data duplication, sync complexity, eventual consistency issues |
| **GraphQL federation** | Elegant cross-service data fetching | Massive overhaul, complex setup, overkill for this use case |

---

## ADR-7: Separate Databases per Service

**Decision:** Each service has its own PostgreSQL database (auth_db, forum_db, notification_db) running on the same PostgreSQL instance.

**Why:**
- Enforces service boundaries — services can't accidentally query each other's tables.
- Each service owns and migrates its own schema independently.
- Easier to move a service to a different database server later.

**Pros:**
- Strong encapsulation — no accidental cross-service joins.
- Independent migrations — auth can migrate without touching forum.
- Can scale databases independently in production.

**Cons:**
- Can't do cross-service SQL joins (need HTTP calls instead).
- No cross-service foreign keys — referential integrity is application-level.
- More databases to manage (backups, monitoring).

**Alternatives considered:**

| Alternative | Pros | Cons |
| --- | --- | --- |
| **Shared database, separate schemas** | Can still do cross-schema joins if needed, fewer DBs to manage | Weaker isolation, migration conflicts, temptation to couple |
| **Shared database, shared schema** | Simplest, full SQL power | No service boundaries, tight coupling, single migration nightmare |
| **Separate PostgreSQL instances per service** | Maximum isolation | More infrastructure, more ops overhead, unnecessary at this scale |

---

## ADR-8: Django for Auth, FastAPI for Forum/Notification

**Decision:** Use Django + DRF for auth-service and FastAPI for forum-service and notification-service.

**Why:**
- Django has a battle-tested auth system: `AbstractUser`, password hashing, token generation, admin panel.
- FastAPI's native async support is essential for WebSockets and high-concurrency endpoints.
- Each framework is used where it excels.

**Pros:**
- Django's `AbstractUser`, `authenticate()`, password validators, and admin panel saved weeks of development.
- FastAPI's `async/await` handles hundreds of concurrent WebSocket connections without blocking.
- Best of both worlds.

**Cons:**
- Two different Python frameworks to learn and maintain.
- Different ORM patterns (Django ORM vs SQLAlchemy) — mental context switch.
- Can't share model code between services.

**Alternatives considered:**

| Alternative | Pros | Cons |
| --- | --- | --- |
| **All Django** | One framework, shared code, Django admin everywhere | Django's async support is still maturing, WebSocket handling is clunky (needs Channels + Daphne) |
| **All FastAPI** | One framework, fully async, consistent patterns | No built-in auth system, would need to build password hashing, token generation, admin from scratch |
| **Express.js (Node) + React** | Full-stack JavaScript, shared types with frontend | Python's data science / ML ecosystem not available, team expertise is Python |
| **Spring Boot (Java)** | Enterprise-grade, excellent for microservices | Heavy, verbose, slower development iteration |

---

## ADR-9: Zustand over Redux for Frontend State

**Decision:** Use Zustand for all frontend state management (auth, notifications, theme).

**Why:**
- The app has a few distinct global stores (auth, notifications, theme) — doesn't need Redux's complex action/reducer/middleware patterns.
- Zustand is ~1KB, zero boilerplate, and works with React hooks natively.

**Pros:**
- Minimal boilerplate — a store is just a function.
- No providers needed — import and use anywhere.
- Built-in devtools support.
- Tiny bundle size.

**Cons:**
- Less structure for very large teams — no enforced patterns.
- Smaller ecosystem than Redux.
- No built-in middleware for complex async flows (though simple async works fine).

**Alternatives considered:**

| Alternative | Pros | Cons |
| --- | --- | --- |
| **Redux Toolkit** | Industry standard, great devtools, middleware ecosystem | Verbose boilerplate (slices, actions, reducers), overkill for 3 stores |
| **React Context + useReducer** | No extra dependency, built into React | Performance issues with frequent updates, awkward API for async |
| **Jotai / Recoil** | Atomic state, great for derived state | Overkill for this app's state shape, less mature |
| **MobX** | Automatic reactivity, minimal boilerplate | Magic can be hard to debug, larger bundle |
