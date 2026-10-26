"""Per-visitor daily limits for every route that spends Meta API credit.

MetaAPI already refuses calls past the global budget; these limits stop one visitor from
using up a public demo. Counts live in memory, so a restart resets them.
"""
from __future__ import annotations

import os
import threading
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request

DAY_S = 24 * 3600
# Calls per IP per day. Override with TOT_LIMIT_BUILD, TOT_LIMIT_SCENE, TOT_LIMIT_SCORE.
DEFAULT_LIMITS = {"build": 3, "scene": 3, "score": 60}
WHAT = {"build": "picture sets", "scene": "scenes", "score": "scored responses"}
TRUST_PROXY = os.environ.get("TOT_TRUST_PROXY") == "1"


def limit_for(bucket: str) -> int:
    return int(os.environ.get(f"TOT_LIMIT_{bucket.upper()}", DEFAULT_LIMITS[bucket]))


def client_ip(request: Request) -> str:
    """The caller's address. Behind a reverse proxy set TOT_TRUST_PROXY=1 to use X-Forwarded-For."""
    if TRUST_PROXY and (fwd := request.headers.get("x-forwarded-for")):
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


class DailyLimiter:
    def __init__(self, window_s: int = DAY_S):
        self.window_s = window_s
        self.hits: dict[tuple[str, str], deque] = defaultdict(deque)
        self.lock = threading.Lock()

    def _prune(self, key: tuple[str, str], now: float) -> deque:
        q = self.hits[key]
        while q and q[0] <= now - self.window_s:
            q.popleft()
        return q

    def remaining(self, bucket: str, ip: str) -> int:
        with self.lock:
            return max(0, limit_for(bucket) - len(self._prune((bucket, ip), time.time())))

    def take(self, bucket: str, ip: str, n: int = 1) -> None:
        """Count n calls, or raise 429 if they would go over today's limit."""
        now = time.time()
        with self.lock:
            q = self._prune((bucket, ip), now)
            limit = limit_for(bucket)
            if len(q) + n > limit:
                retry = int(q[0] + self.window_s - now) + 1 if q else self.window_s
                raise HTTPException(429, f"Daily limit reached: {limit} {WHAT[bucket]} per visitor per day "
                                         f"on this demo. Try again in about {retry // 3600 + 1} h.",
                                    headers={"Retry-After": str(retry)})
            q.extend([now] * n)


limiter = DailyLimiter()
