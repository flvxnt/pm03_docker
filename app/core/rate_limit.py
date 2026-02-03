import time
from collections import defaultdict, deque
from typing import Deque, Dict, Tuple


class RateLimiter:
    def __init__(self, max_requests: int, window_seconds: int):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.storage: Dict[str, Deque[float]] = defaultdict(deque)

    def check(self, key: str) -> bool:
        """
        True = можно
        False = лимит превышен
        """
        now = time.time()
        q = self.storage[key]

        # очищаем старые запросы
        while q and q[0] < now - self.window_seconds:
            q.popleft()

        if len(q) >= self.max_requests:
            return False

        q.append(now)
        return True


rate_limiter = RateLimiter(max_requests=20, window_seconds=10)
