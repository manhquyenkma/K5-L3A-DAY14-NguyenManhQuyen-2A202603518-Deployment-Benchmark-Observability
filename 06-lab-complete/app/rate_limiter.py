"""
Rate limiting (tiêu chí 7) — Sliding window lưu trong Redis.
"""
import math
import threading
import time
import uuid
from collections import defaultdict, deque

from fastapi import HTTPException

from app.config import settings
from app.redis_client import r

WINDOW_SECONDS = 60

# Atomic sliding window bằng Redis sorted set:
# ZREMRANGEBYSCORE → ZCARD → (ZRANGE nếu vượt) → ZADD → EXPIRE
_SLIDING_WINDOW_LUA = """
redis.call('ZREMRANGEBYSCORE', KEYS[1], 0, ARGV[1])
local count = redis.call('ZCARD', KEYS[1])
if count >= tonumber(ARGV[3]) then
    local oldest = redis.call('ZRANGE', KEYS[1], 0, 0, 'WITHSCORES')
    return {0, oldest[2] or ARGV[2]}
end
redis.call('ZADD', KEYS[1], ARGV[2], ARGV[4])
redis.call('EXPIRE', KEYS[1], tonumber(ARGV[5]))
return {1, count + 1}
"""

_mem_lock = threading.Lock()
_mem_windows: dict[str, deque[float]] = defaultdict(deque)


def _check_memory(key: str, limit: int, now: float) -> None:
    cutoff = now - WINDOW_SECONDS
    with _mem_lock:
        dq = _mem_windows[key]
        while dq and dq[0] <= cutoff:
            dq.popleft()
        if len(dq) >= limit:
            retry_after = max(1, math.ceil(dq[0] + WINDOW_SECONDS - now))
            raise HTTPException(
                status_code=429,
                detail="Rate limit exceeded",
                headers={"Retry-After": str(retry_after)},
            )
        dq.append(now)


def check_rate_limit(key: str) -> None:
    """Giới hạn RATE_LIMIT_PER_MINUTE request / 60s cho mỗi API key."""
    limit = max(1, settings.rate_limit_per_minute)
    now = time.time()
    cutoff = now - WINDOW_SECONDS

    if r is not None:
        redis_key = f"ratelimit:{key}"
        member = f"{now:.6f}:{uuid.uuid4().hex}"
        try:
            allowed, value = r.eval(
                _SLIDING_WINDOW_LUA,
                1,
                redis_key,
                cutoff,
                now,
                limit,
                member,
                WINDOW_SECONDS + 5,
            )
            if int(allowed) == 0:
                oldest_ts = float(value)
                retry_after = max(1, math.ceil(oldest_ts + WINDOW_SECONDS - now))
                raise HTTPException(
                    status_code=429,
                    detail="Rate limit exceeded",
                    headers={"Retry-After": str(retry_after)},
                )
            return
        except HTTPException:
            raise
        except Exception:
            pass

    _check_memory(key, limit, now)
