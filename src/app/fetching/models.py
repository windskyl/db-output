from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


@dataclass(slots=True)
class FetchRequest:
    url: str
    method: str = "GET"
    headers: dict[str, str] = field(default_factory=dict)
    body: bytes | None = None


@dataclass(slots=True)
class RetryPolicy:
    max_attempts: int = 1
    base_delay_seconds: float = 0.5
    backoff_multiplier: float = 2.0
    max_delay_seconds: float = 8.0
    jitter_ratio: float = 0.2
    retry_on_status_codes: tuple[int, ...] = (429, 500, 502, 503, 504)


@dataclass(slots=True)
class FetchAttempt:
    index: int
    url: str
    started_at: str
    completed_at: str
    duration_ms: int
    status_code: int | None = None
    error_type: str | None = None
    error_message: str | None = None
    retry_delay_ms: int = 0


@dataclass(slots=True)
class FetchResponse:
    request: FetchRequest
    url: str
    final_url: str
    status_code: int
    headers: dict[str, str] = field(default_factory=dict)
    body: bytes = b""
    attempts: list[FetchAttempt] = field(default_factory=list)
    fetched_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    from_cache: bool = False

    def text(self, encoding: str | None = None) -> str:
        return self.body.decode(encoding or self._detect_encoding(), errors="ignore")

    def json(self) -> Any:
        return json.loads(self.text())

    def _detect_encoding(self) -> str:
        content_type = self.headers.get("Content-Type", "")
        match = re.search(r"charset=([\w-]+)", content_type, flags=re.IGNORECASE)
        return match.group(1) if match else "utf-8"


@dataclass(slots=True)
class FetchEvent:
    source_id: str
    url: str
    final_url: str
    status_code: int | None
    success: bool
    attempt_count: int
    retry_count: int
    wait_ms: int
    duration_ms: int
    error_type: str | None = None
    error_message: str | None = None
    from_cache: bool = False
    finished_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())