"""HTTP session with per-endpoint-group rate limiting and retries with backoff."""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from typing import Any

import requests

log = logging.getLogger(__name__)

RETRY_STATUS = {429, 500, 502, 503, 504}
USER_AGENT = "krakow-air-quality-pipeline/0.1 (+https://github.com/)"


class ApiError(requests.HTTPError):
    """A 4xx answer with a GIOŚ error body, e.g. API-ERR-100003 for a manual sensor."""

    def __init__(self, code: str | None, reason: str | None, response: requests.Response):
        super().__init__(f"{response.status_code} {code}: {reason}", response=response)
        self.code = code


class RateLimiter:
    """Simple spacing limiter: at most ``per_minute`` calls per rolling minute."""

    def __init__(self, per_minute: float, clock: Callable[[], float] = time.monotonic,
                 sleep: Callable[[float], None] = time.sleep):
        self.interval = 60.0 / per_minute if per_minute > 0 else 0.0
        self._clock = clock
        self._sleep = sleep
        self._last: float | None = None

    def wait(self) -> None:
        if self._last is not None and self.interval:
            remaining = self.interval - (self._clock() - self._last)
            if remaining > 0:
                log.debug("rate limit: sleeping %.1fs", remaining)
                self._sleep(remaining)
        self._last = self._clock()


class HttpClient:
    def __init__(
        self,
        rate_limits_per_min: dict[str, float],
        timeout_s: float = 60,
        max_attempts: int = 6,
        backoff_base_s: float = 5.0,
        session: requests.Session | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ):
        self.session = session or requests.Session()
        self.session.headers.setdefault("User-Agent", USER_AGENT)
        self.session.headers.setdefault("Accept", "application/json")
        self.timeout_s = timeout_s
        self.max_attempts = max_attempts
        self.backoff_base_s = backoff_base_s
        self._sleep = sleep
        self.limiters = {g: RateLimiter(r, sleep=sleep) for g, r in rate_limits_per_min.items()}
        self.calls = 0

    def get_json(self, url: str, params: dict[str, Any] | None = None, group: str = "default") -> Any:
        limiter = self.limiters.get(group)
        last_error: Exception | None = None
        for attempt in range(1, self.max_attempts + 1):
            if limiter:
                limiter.wait()
            try:
                self.calls += 1
                resp = self.session.get(url, params=params, timeout=self.timeout_s)
            except (requests.ConnectionError, requests.Timeout) as exc:
                last_error = exc
                delay = self.backoff_base_s * 2 ** (attempt - 1)
                log.warning("GET %s failed (%s), retry %d/%d in %.0fs", url, exc, attempt,
                            self.max_attempts, delay)
                self._sleep(delay)
                continue

            if resp.status_code in RETRY_STATUS:
                retry_after = resp.headers.get("Retry-After")
                delay = float(retry_after) if retry_after and retry_after.isdigit() \
                    else self.backoff_base_s * 2 ** (attempt - 1)
                last_error = requests.HTTPError(f"{resp.status_code} for {resp.url}", response=resp)
                log.warning("GET %s -> %s, retry %d/%d in %.0fs", url, resp.status_code, attempt,
                            self.max_attempts, delay)
                self._sleep(delay)
                continue

            if 400 <= resp.status_code < 500:
                try:
                    body = resp.json()
                except ValueError:
                    body = None
                if isinstance(body, dict) and "error_code" in body:
                    raise ApiError(body.get("error_code"), body.get("error_reason"), resp)
            resp.raise_for_status()
            return resp.json()

        raise RuntimeError(f"GET {url} failed after {self.max_attempts} attempts") from last_error
