"""熔断器：防止对持续失败的 Provider 进行无效重试，避免雪崩。

状态机：
- closed：正常放行；连续失败达到阈值后切到 open。
- open：在 reset_timeout 内拒绝调用；超时后进入半开（这里简化为直接 closed 重试一次）。
"""

import time
from threading import Lock


class CircuitBreaker:
    def __init__(self, failure_threshold: int = 5, reset_timeout: float = 30.0) -> None:
        self.failure_threshold = failure_threshold
        self.reset_timeout = reset_timeout
        self._failures = 0
        self._opened_at = 0.0
        self._state = "closed"
        self._lock = Lock()

    def allow(self) -> bool:
        with self._lock:
            if self._state == "open":
                if time.time() - self._opened_at >= self.reset_timeout:
                    self._state = "closed"
                    self._failures = 0
                    return True
                return False
            return True

    def record_success(self) -> None:
        with self._lock:
            self._failures = 0
            self._state = "closed"

    def record_failure(self) -> None:
        with self._lock:
            self._failures += 1
            if self._failures >= self.failure_threshold:
                self._state = "open"
                self._opened_at = time.time()
