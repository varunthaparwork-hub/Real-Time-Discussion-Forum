"""
Auth client with Redis caching, persistent httpx pool, and auth-service-down
fallback.

Resilience features:
  1. Redis TTL cache — user data cached for 120s, avoids repeated HTTP calls
  2. Persistent httpx.AsyncClient — connection pooling, no handshake per request
  3. Per-user granular caching — only uncached users are fetched from auth-service
  4. Auth-service down → returns placeholder User#<id> so APIs never 500
"""

import json
import logging
import os
import httpx
from dotenv import load_dotenv
from app.services.redis_pool import get_redis

load_dotenv()

logger = logging.getLogger("auth_client")

AUTH_SERVICE_URL = os.getenv("AUTH_SERVICE_URL")
USER_CACHE_TTL = 86400  # 24 hours — usernames rarely change, long cache is safe

# ── Persistent HTTP client (connection pooling) ──────────────────────
_http_client: httpx.AsyncClient | None = None


def _get_http_client() -> httpx.AsyncClient:
    global _http_client
    if _http_client is None or _http_client.is_closed:
        _http_client = httpx.AsyncClient(
            timeout=10.0,
            limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
        )
    return _http_client


# ── Placeholder when auth-service is unreachable ─────────────────────
def _placeholder_user(user_id: int) -> dict:
    """Return a safe placeholder so thread/comment APIs never crash."""
    return {
        "id": user_id,
        "username": f"User#{user_id}",
        "avatar": None,
        "role": "member",
    }


# ── Redis cache keys ─────────────────────────────────────────────────
def _user_cache_key(user_id: int) -> str:
    return f"user:id:{user_id}"


def _username_cache_key(username: str) -> str:
    return f"user:name:{username}"


# ── Core: get_user_map with Redis cache ──────────────────────────────
async def get_user_map(user_ids: list[int]) -> dict[int, dict]:
    """
    Maps user_ids → user dicts {id, username, avatar, role}.
    Checks Redis first; only fetches uncached IDs from auth-service.
    If auth-service is down, returns placeholder User#<id> for uncached users.
    """
    unique_ids = sorted(set(user_ids))
    if not unique_ids:
        return {}

    result: dict[int, dict] = {}
    uncached_ids: list[int] = []

    # 1️⃣  Check Redis cache for each user
    redis = get_redis()
    try:
        cache_keys = [_user_cache_key(uid) for uid in unique_ids]
        cached_values = await redis.mget(*cache_keys)

        for uid, cached in zip(unique_ids, cached_values):
            if cached is not None:
                result[uid] = json.loads(cached)
            else:
                uncached_ids.append(uid)
    except Exception:
        # Redis down — fall back to fetching all
        uncached_ids = unique_ids

    # 2️⃣  Fetch only the uncached users from auth-service
    if uncached_ids:
        ids_param = ",".join(str(uid) for uid in uncached_ids)
        url = f"{AUTH_SERVICE_URL}/api/auth/users/basic/?ids={ids_param}"

        try:
            client = _get_http_client()
            response = await client.get(url)
            response.raise_for_status()
            users = response.json()

            # 3️⃣  Store freshly fetched users in Redis
            pipe = redis.pipeline()
            for user in users:
                uid = user["id"]
                result[uid] = user
                pipe.setex(_user_cache_key(uid), USER_CACHE_TTL, json.dumps(user))
            try:
                await pipe.execute()
            except Exception:
                pass  # Redis write failure is non-fatal

            # Any IDs returned by auth that aren't in the response → placeholder
            fetched_ids = {u["id"] for u in users}
            for uid in uncached_ids:
                if uid not in fetched_ids and uid not in result:
                    result[uid] = _placeholder_user(uid)

        except (httpx.ConnectError, httpx.TimeoutException, httpx.HTTPStatusError) as exc:
            # ── Auth-service unreachable — fill with placeholders ──
            logger.warning("Auth-service unreachable (%s), using placeholders for %d users", exc, len(uncached_ids))
            for uid in uncached_ids:
                result[uid] = _placeholder_user(uid)
        except Exception as exc:
            logger.error("Unexpected auth-client error: %s", exc)
            for uid in uncached_ids:
                result[uid] = _placeholder_user(uid)

    return result


async def get_user_role(user_id: int) -> str:
    """Fetch a single user's role (cache-backed)."""
    user_map = await get_user_map([user_id])
    user_data = user_map.get(user_id, {})
    if isinstance(user_data, dict):
        return user_data.get("role", "member")
    return "member"


async def get_users_by_usernames(usernames: list[str]) -> list[dict]:
    """Resolve usernames → user dicts, with Redis caching."""
    unique_usernames = sorted(set(usernames))
    if not unique_usernames:
        return []

    result: list[dict] = []
    uncached: list[str] = []

    redis = get_redis()
    try:
        cache_keys = [_username_cache_key(u) for u in unique_usernames]
        cached_values = await redis.mget(*cache_keys)

        for uname, cached in zip(unique_usernames, cached_values):
            if cached is not None:
                result.append(json.loads(cached))
            else:
                uncached.append(uname)
    except Exception:
        uncached = unique_usernames

    if uncached:
        username_param = ",".join(uncached)
        url = f"{AUTH_SERVICE_URL}/api/auth/users/by-usernames/?usernames={username_param}"

        try:
            client = _get_http_client()
            response = await client.get(url)
            response.raise_for_status()
            fetched = response.json()

            pipe = redis.pipeline()
            for user in fetched:
                result.append(user)
                pipe.setex(_username_cache_key(user["username"]), USER_CACHE_TTL, json.dumps(user))
                pipe.setex(_user_cache_key(user["id"]), USER_CACHE_TTL, json.dumps(user))
            try:
                await pipe.execute()
            except Exception:
                pass
        except (httpx.ConnectError, httpx.TimeoutException, httpx.HTTPStatusError) as exc:
            logger.warning("Auth-service unreachable (%s), skipping username resolution", exc)
        except Exception as exc:
            logger.error("Unexpected auth-client error: %s", exc)

    return result
    