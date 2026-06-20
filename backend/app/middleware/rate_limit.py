"""Per-IP rate limiter for /query.

Uses slowapi's in-memory storage. For multi-instance deployments this would
need Redis; v1 runs on a single Railway dyno so in-memory is fine.

Applied as a FastAPI dependency on the routes that need it, plus a global
exception handler for 429 RateLimitExceeded.
"""

from __future__ import annotations

from slowapi import Limiter
from slowapi.util import get_remote_address

QUERY_RATE = "10/hour"  # per-IP cap on /query

limiter = Limiter(key_func=get_remote_address)
