"""
Rate limiter — throttles API requests per IP using slowapi.

Limits:
  • Write operations (POST/PUT/DELETE) — stricter (e.g. 10/min)
  • Read operations (GET)              — relaxed  (e.g. 60/min)

Uses the client's IP address as the rate-limit key.
Returns HTTP 429 (Too Many Requests) when the limit is exceeded.
"""
from slowapi import Limiter
from slowapi.util import get_remote_address

# Key function: extract the client's real IP from the request
limiter = Limiter(key_func=get_remote_address)
