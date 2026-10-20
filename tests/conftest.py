from __future__ import annotations

from typing import Any

import pytest


class FakeResponse:
    def __init__(self, payload: Any, status: int = 200, headers: dict | None = None, url: str = ""):
        self._payload = payload
        self.status_code = status
        self.headers = headers or {}
        self.url = url

    def json(self) -> Any:
        return self._payload

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


class FakeSession:
    """Returns queued responses and records every request."""

    def __init__(self, responses: list[FakeResponse]):
        self.responses = list(responses)
        self.requests: list[tuple[str, dict]] = []
        self.headers: dict[str, str] = {}

    def get(self, url: str, params: dict | None = None, timeout: float | None = None) -> FakeResponse:
        self.requests.append((url, dict(params or {})))
        if not self.responses:
            raise AssertionError(f"Unexpected request {url} {params}")
        return self.responses.pop(0)


@pytest.fixture
def no_sleep():
    calls: list[float] = []
    return calls.append, calls
