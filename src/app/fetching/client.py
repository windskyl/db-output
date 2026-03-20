from __future__ import annotations

import gzip
import random
import socket
import time
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable

from app.fetching.cache import FetchCache
from app.fetching.limiter import RateLimiter
from app.fetching.models import FetchAttempt, FetchEvent, FetchRequest, FetchResponse, RetryPolicy
from app.models.source_profile import SourceProfile
from app.models.task_spec import TaskSpec


class FetchClient:
    def __init__(
        self,
        rate_limiter: RateLimiter | None = None,
        open_url: Callable[..., Any] | None = None,
        sleep_func: Callable[[float], None] | None = None,
        random_func: Callable[[], float] | None = None,
        cache: FetchCache | None = None,
    ) -> None:
        self.rate_limiter = rate_limiter or RateLimiter()
        self._open_url = open_url or urllib.request.urlopen
        self._sleep = sleep_func or time.sleep
        self._random = random_func or random.random
        self.cache = cache or FetchCache()
        self._events: list[FetchEvent] = []
        self._active_task_id: str | None = None
        self._cache_enabled = False
        self._cache_hits = 0
        self._cache_misses = 0
        self._cache_writes = 0

    def begin_session(self, task_id: str, cache_dir: Path | None = None) -> None:
        self._active_task_id = task_id
        self._events = []
        self.cache.set_root_dir(cache_dir)
        self._cache_enabled = cache_dir is not None
        self._cache_hits = 0
        self._cache_misses = 0
        self._cache_writes = 0

    def fetch(self, request: FetchRequest, profile: SourceProfile, task: TaskSpec) -> FetchResponse:
        request_headers = self._build_headers(profile, request)
        cached_response = self._load_cached_response(
            request=request,
            profile=profile,
            task=task,
            headers=request_headers,
        )
        if cached_response is not None:
            cached_at = cached_response.fetched_at or datetime.now(UTC).isoformat()
            attempts = [
                FetchAttempt(
                    index=1,
                    url=cached_response.final_url,
                    started_at=cached_at,
                    completed_at=cached_at,
                    duration_ms=0,
                    status_code=cached_response.status_code,
                )
            ]
            cached_response.attempts = attempts
            self._record_event(
                source_id=profile.source_id,
                request_url=request.url,
                final_url=cached_response.final_url,
                status_code=cached_response.status_code,
                success=True,
                wait_ms=0,
                attempts=attempts,
                from_cache=True,
            )
            return cached_response

        wait_ms = self.rate_limiter.acquire(
            key=profile.source_id,
            qps=profile.rate_limit_qps,
            burst=profile.rate_limit_burst,
            max_concurrency=min(profile.max_concurrency, task.run_policy.max_concurrency),
        )
        retry_policy = self._resolve_retry_policy(profile, task)
        timeout_seconds = profile.timeout_seconds or task.run_policy.timeout_seconds
        attempts: list[FetchAttempt] = []

        for attempt_index in range(1, retry_policy.max_attempts + 1):
            started_at = datetime.now(UTC).isoformat()
            started_perf = time.perf_counter()
            try:
                urllib_request = urllib.request.Request(
                    request.url,
                    data=request.body,
                    method=request.method,
                    headers=request_headers,
                )
                with self._open_url(urllib_request, timeout=timeout_seconds) as response:
                    raw_body = response.read()
                    headers = {key: value for key, value in response.headers.items()}
                    duration_ms = int(round((time.perf_counter() - started_perf) * 1000))
                    attempts.append(
                        FetchAttempt(
                            index=attempt_index,
                            url=getattr(response, "geturl", lambda: request.url)(),
                            started_at=started_at,
                            completed_at=datetime.now(UTC).isoformat(),
                            duration_ms=duration_ms,
                            status_code=int(getattr(response, "status", response.getcode())),
                        )
                    )
                    fetch_response = FetchResponse(
                        request=request,
                        url=request.url,
                        final_url=getattr(response, "geturl", lambda: request.url)(),
                        status_code=int(getattr(response, "status", response.getcode())),
                        headers=headers,
                        body=self._decode_body(raw_body, headers),
                        attempts=list(attempts),
                    )
                    if self._should_use_cache(request, task):
                        self.cache.save(
                            source_id=profile.source_id,
                            request=request,
                            headers=request_headers,
                            response=fetch_response,
                        )
                        self._cache_writes += 1
                    self._record_event(
                        source_id=profile.source_id,
                        request_url=request.url,
                        final_url=fetch_response.final_url,
                        status_code=fetch_response.status_code,
                        success=True,
                        wait_ms=wait_ms,
                        attempts=attempts,
                    )
                    return fetch_response
            except urllib.error.HTTPError as exc:
                duration_ms = int(round((time.perf_counter() - started_perf) * 1000))
                attempts.append(
                    FetchAttempt(
                        index=attempt_index,
                        url=exc.geturl(),
                        started_at=started_at,
                        completed_at=datetime.now(UTC).isoformat(),
                        duration_ms=duration_ms,
                        status_code=int(exc.code),
                        error_type="HTTPError",
                        error_message=str(exc),
                    )
                )
                if attempt_index < retry_policy.max_attempts and self._should_retry_status(int(exc.code), retry_policy):
                    delay_seconds = self._compute_delay(retry_policy, attempt_index)
                    attempts[-1].retry_delay_ms = int(round(delay_seconds * 1000))
                    self._sleep(delay_seconds)
                    continue
                self._record_event(
                    source_id=profile.source_id,
                    request_url=request.url,
                    final_url=exc.geturl(),
                    status_code=int(exc.code),
                    success=False,
                    wait_ms=wait_ms,
                    attempts=attempts,
                    error_type="HTTPError",
                    error_message=str(exc),
                )
                raise
            except (urllib.error.URLError, TimeoutError, OSError, socket.timeout) as exc:
                duration_ms = int(round((time.perf_counter() - started_perf) * 1000))
                attempts.append(
                    FetchAttempt(
                        index=attempt_index,
                        url=request.url,
                        started_at=started_at,
                        completed_at=datetime.now(UTC).isoformat(),
                        duration_ms=duration_ms,
                        error_type=type(exc).__name__,
                        error_message=str(exc),
                    )
                )
                if attempt_index < retry_policy.max_attempts:
                    delay_seconds = self._compute_delay(retry_policy, attempt_index)
                    attempts[-1].retry_delay_ms = int(round(delay_seconds * 1000))
                    self._sleep(delay_seconds)
                    continue
                self._record_event(
                    source_id=profile.source_id,
                    request_url=request.url,
                    final_url=request.url,
                    status_code=None,
                    success=False,
                    wait_ms=wait_ms,
                    attempts=attempts,
                    error_type=type(exc).__name__,
                    error_message=str(exc),
                )
                raise

        raise RuntimeError("fetch exhausted without returning or raising")

    def build_stats(self) -> dict[str, Any]:
        stats: dict[str, Any] = {
            "task_id": self._active_task_id,
            "total_requests": len(self._events),
            "network_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "total_retries": 0,
            "total_wait_ms": 0,
            "cache_enabled": self._cache_enabled,
            "cache_hits": self._cache_hits,
            "cache_misses": self._cache_misses,
            "cache_writes": self._cache_writes,
            "status_codes": {},
            "error_types": {},
            "source_stats": {},
            "recent_errors": [],
        }
        for event in self._events:
            if not event.from_cache:
                stats["network_requests"] += 1
            if event.success:
                stats["successful_requests"] += 1
            else:
                stats["failed_requests"] += 1
            stats["total_retries"] += event.retry_count
            stats["total_wait_ms"] += event.wait_ms
            if event.status_code is not None:
                code = str(event.status_code)
                stats["status_codes"][code] = stats["status_codes"].get(code, 0) + 1
            if event.error_type:
                stats["error_types"][event.error_type] = stats["error_types"].get(event.error_type, 0) + 1
                stats["recent_errors"].append(
                    {
                        "source_id": event.source_id,
                        "url": event.url,
                        "status_code": event.status_code,
                        "error_type": event.error_type,
                        "error_message": event.error_message,
                    }
                )

            source_stats = stats["source_stats"].setdefault(
                event.source_id,
                {
                    "requests": 0,
                    "network_requests": 0,
                    "cache_hits": 0,
                    "successful_requests": 0,
                    "failed_requests": 0,
                    "retries": 0,
                    "wait_ms": 0,
                    "status_codes": {},
                },
            )
            source_stats["requests"] += 1
            if event.from_cache:
                source_stats["cache_hits"] += 1
            else:
                source_stats["network_requests"] += 1
            if event.success:
                source_stats["successful_requests"] += 1
            else:
                source_stats["failed_requests"] += 1
            source_stats["retries"] += event.retry_count
            source_stats["wait_ms"] += event.wait_ms
            if event.status_code is not None:
                code = str(event.status_code)
                source_stats["status_codes"][code] = source_stats["status_codes"].get(code, 0) + 1

        stats["recent_errors"] = stats["recent_errors"][-5:]
        return stats

    def _build_headers(self, profile: SourceProfile, request: FetchRequest) -> dict[str, str]:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip",
            "Accept": "*/*",
        }
        headers.update(profile.request_headers)
        headers.update(request.headers)
        return headers

    def _load_cached_response(
        self,
        request: FetchRequest,
        profile: SourceProfile,
        task: TaskSpec,
        headers: dict[str, str],
    ) -> FetchResponse | None:
        if not self._should_use_cache(request, task):
            return None
        response = self.cache.load(source_id=profile.source_id, request=request, headers=headers)
        if response is None:
            self._cache_misses += 1
            return None
        self._cache_hits += 1
        return response

    def _should_use_cache(self, request: FetchRequest, task: TaskSpec) -> bool:
        return self._cache_enabled and task.run_policy.enable_cache and request.method.upper() == "GET"

    def _resolve_retry_policy(self, profile: SourceProfile, task: TaskSpec) -> RetryPolicy:
        payload = dict(profile.retry_policy)
        status_codes = payload.get("retry_on_status_codes", [429, 500, 502, 503, 504])
        return RetryPolicy(
            max_attempts=max(1, int(payload.get("max_attempts", task.run_policy.retry_times + 1))),
            base_delay_seconds=float(payload.get("base_delay_seconds", 0.5)),
            backoff_multiplier=float(payload.get("backoff_multiplier", 2.0)),
            max_delay_seconds=float(payload.get("max_delay_seconds", 8.0)),
            jitter_ratio=float(payload.get("jitter_ratio", 0.2)),
            retry_on_status_codes=tuple(int(code) for code in status_codes),
        )

    def _should_retry_status(self, status_code: int, retry_policy: RetryPolicy) -> bool:
        return status_code in retry_policy.retry_on_status_codes

    def _compute_delay(self, retry_policy: RetryPolicy, attempt_index: int) -> float:
        base_delay = retry_policy.base_delay_seconds * (retry_policy.backoff_multiplier ** max(0, attempt_index - 1))
        jitter = base_delay * retry_policy.jitter_ratio * self._random()
        return min(retry_policy.max_delay_seconds, base_delay + jitter)

    def _decode_body(self, payload: bytes, headers: dict[str, str]) -> bytes:
        encoding = headers.get("Content-Encoding", "").lower()
        if encoding == "gzip" or payload[:2] == b"\x1f\x8b":
            return gzip.decompress(payload)
        return payload

    def _record_event(
        self,
        source_id: str,
        request_url: str,
        final_url: str,
        status_code: int | None,
        success: bool,
        wait_ms: int,
        attempts: list[FetchAttempt],
        error_type: str | None = None,
        error_message: str | None = None,
        from_cache: bool = False,
    ) -> None:
        self._events.append(
            FetchEvent(
                source_id=source_id,
                url=request_url,
                final_url=final_url,
                status_code=status_code,
                success=success,
                attempt_count=len(attempts),
                retry_count=max(0, len(attempts) - 1),
                wait_ms=wait_ms,
                duration_ms=sum(attempt.duration_ms for attempt in attempts),
                error_type=error_type,
                error_message=error_message,
                from_cache=from_cache,
            )
        )