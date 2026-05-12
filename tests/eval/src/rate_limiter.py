import threading
import time


class RateLimiter:
    """Token-bucket rate limiter for GitHub Models free-tier (15 RPM)."""

    def __init__(self, calls_per_minute: int = 12) -> None:
        self._min_interval = 60.0 / calls_per_minute
        self._last_call: float = 0.0
        self._lock = threading.Lock()

    def wait(self) -> None:
        with self._lock:
            now = time.monotonic()
            gap = self._min_interval - (now - self._last_call)
            if gap > 0:
                time.sleep(gap)
            self._last_call = time.monotonic()


# Shared singleton used by agent.py and judge_model.py
github_models_limiter = RateLimiter(calls_per_minute=12)
