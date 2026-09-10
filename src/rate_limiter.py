import time
import threading

RATE_LIMIT_RPM = 4
RATE_LIMIT_ENABLED = True


class GeminiRateLimiter:
    """
    Thread-safe rate limiter that spaces Gemini API calls evenly.

    At 4 RPM, calls are spaced approximately 15 seconds apart.
    """

    def __init__(
        self,
        max_requests_per_minute: int = RATE_LIMIT_RPM,
        enabled: bool = RATE_LIMIT_ENABLED,
    ):
        self.max_rpm = max_requests_per_minute
        self.enabled = enabled

        # 4 RPM -> 15 seconds between calls
        self.interval = 60.0 / self.max_rpm

        self._lock = threading.Lock()
        self._next_allowed_time = time.monotonic()

    def wait_if_needed(self) -> None:
        if not self.enabled:
            return

        with self._lock:
            now = time.monotonic()

            # How long until this request gets its slot?
            wait_time = self._next_allowed_time - now

            if wait_time > 0:
                print(
                    f"[RateLimiter] Waiting {wait_time:.1f}s "
                    f"for next Gemini API slot..."
                )
                time.sleep(wait_time)

            # Reserve the next slot
            self._next_allowed_time = (
                max(self._next_allowed_time, time.monotonic())
                + self.interval
            )


gemini_rate_limiter = GeminiRateLimiter()