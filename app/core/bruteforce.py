import time
from collections import defaultdict, deque
from fastapi import Request, HTTPException


class BruteForceProtector:
    def __init__(self, limit: int, window_seconds: int):
        self.limit = limit
        self.window = window_seconds
        self.attempts = defaultdict(deque)

    def register_fail(self, key: str):
        now = time.time()
        q = self.attempts[key]

        while q and now - q[0] > self.window:
            q.popleft()

        q.append(now)

    def is_blocked(self, key: str) -> bool:
        now = time.time()
        q = self.attempts[key]

        while q and now - q[0] > self.window:
            q.popleft()

        return len(q) >= self.limit


bruteforce = BruteForceProtector(limit=5, window_seconds=60)
