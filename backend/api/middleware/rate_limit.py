import logging

import redis

from backend.core.config import settings

log = logging.getLogger("verity.rate_limit")

_client = redis.from_url(settings.redis_url, decode_responses=True)

WINDOW_SECONDS = 20 * 60  # 20 minutes
MAX_REQUESTS = 20  # per authenticated user


def check_rate_limit(ip: str) -> tuple[bool, int]:
    """Check if IP is within rate limit.

    Returns (is_allowed, retry_after_seconds).
    Uses a sliding counter in Redis — first request sets a 20-min TTL.
    """
    key = f"rl:{ip}"
    try:
        pipe = _client.pipeline()
        pipe.incr(key)
        pipe.ttl(key)
        count, ttl = pipe.execute()

        if ttl < 0:
            _client.expire(key, WINDOW_SECONDS)
            ttl = WINDOW_SECONDS

        if count > MAX_REQUESTS:
            log.warning("[rate_limit] IP=%s blocked | count=%d | retry_after=%ds", ip, count, ttl)
            return False, max(ttl, 0)

        log.debug("[rate_limit] IP=%s | count=%d/%d", ip, count, MAX_REQUESTS)
        return True, 0

    except Exception as exc:
        # Redis down → allow request rather than block everyone
        log.warning("[rate_limit] Redis unavailable, skipping check: %s", exc)
        return True, 0
