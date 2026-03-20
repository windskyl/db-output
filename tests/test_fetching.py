from __future__ import annotations

import gzip
import io
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import Mock

from app.fetching.client import FetchClient
from app.fetching.limiter import RateLimiter
from app.fetching.models import FetchRequest
from app.models.source_profile import SourceProfile
from app.models.task_spec import TaskSpec


class FakeResponse:
    def __init__(self, url: str, status: int, body: bytes, headers: dict[str, str] | None = None) -> None:
        self._url = url
        self.status = status
        self._body = body
        self.headers = headers or {}

    def read(self) -> bytes:
        return self._body

    def getcode(self) -> int:
        return self.status

    def geturl(self) -> str:
        return self._url

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        return False


class FetchClientTests(unittest.TestCase):
    def build_profile(self) -> SourceProfile:
        return SourceProfile(
            source_id="example_api",
            domain="public_sentiment",
            connector_kind="json_api",
            source_type="public_api",
            source_label="Example API",
            base_url="https://example.com",
            first_page_url="https://example.com/api/search",
            source_channel="api",
            json_items_path="hits",
            json_field_paths={"title": "title", "published_at": "created_at"},
            rate_limit_qps=10,
            rate_limit_burst=2,
        )

    def build_task(self) -> TaskSpec:
        return TaskSpec.from_dict(
            {
                "task_id": "fetch-test-001",
                "domain": "public_sentiment",
                "targets": [{"type": "company", "value": "OpenAI"}],
                "topic_scope": ["tech_stack_engineering"],
                "time_range": {"start": "2026-03-01T00:00:00", "end": "2026-03-18T00:00:00", "timezone": "UTC"},
                "source_policy": {"selection_mode": "explicit", "whitelist": ["example_api"], "allow_html": False, "allow_rss": False, "allow_api": True},
                "run_policy": {"timeout_seconds": 5, "retry_times": 1},
            }
        )

    def test_fetch_client_retries_http_error_and_records_stats(self) -> None:
        temporary_error = urllib.error.HTTPError(
            url="https://example.com/api/search",
            code=500,
            msg="temporary failure",
            hdrs={"Content-Type": "application/json"},
            fp=io.BytesIO(b'{"error": "temporary"}'),
        )
        opener = Mock(
            side_effect=[
                temporary_error,
                FakeResponse(
                    url="https://example.com/api/search",
                    status=200,
                    body=b'{"hits": []}',
                    headers={"Content-Type": "application/json"},
                ),
            ]
        )
        client = FetchClient(
            rate_limiter=RateLimiter(sleep_func=lambda _: None),
            open_url=opener,
            sleep_func=lambda _: None,
            random_func=lambda: 0.0,
        )
        client.begin_session("fetch-test-001")

        response = client.fetch(
            request=FetchRequest(url="https://example.com/api/search", headers={"Accept": "application/json"}),
            profile=self.build_profile(),
            task=self.build_task(),
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"hits": []})
        stats = client.build_stats()
        self.assertEqual(stats["total_requests"], 1)
        self.assertEqual(stats["successful_requests"], 1)
        self.assertEqual(stats["failed_requests"], 0)
        self.assertEqual(stats["total_retries"], 1)
        self.assertEqual(stats["source_stats"]["example_api"]["retries"], 1)

    def test_fetch_client_decompresses_gzip_body(self) -> None:
        opener = Mock(
            return_value=FakeResponse(
                url="https://example.com/api/search",
                status=200,
                body=gzip.compress(b'{"hits": [1]}'),
                headers={"Content-Type": "application/json", "Content-Encoding": "gzip"},
            )
        )
        client = FetchClient(
            rate_limiter=RateLimiter(sleep_func=lambda _: None),
            open_url=opener,
            sleep_func=lambda _: None,
        )
        client.begin_session("fetch-test-002")

        response = client.fetch(
            request=FetchRequest(url="https://example.com/api/search", headers={"Accept": "application/json"}),
            profile=self.build_profile(),
            task=self.build_task(),
        )

        self.assertEqual(response.json(), {"hits": [1]})

    def test_fetch_client_uses_disk_cache_for_repeated_get(self) -> None:
        opener = Mock(
            return_value=FakeResponse(
                url="https://example.com/api/search",
                status=200,
                body=b'{"hits": [1]}',
                headers={"Content-Type": "application/json"},
            )
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            client = FetchClient(
                rate_limiter=RateLimiter(sleep_func=lambda _: None),
                open_url=opener,
                sleep_func=lambda _: None,
            )
            client.begin_session("fetch-test-003", cache_dir=Path(temp_dir))
            request = FetchRequest(url="https://example.com/api/search", headers={"Accept": "application/json"})

            first_response = client.fetch(
                request=request,
                profile=self.build_profile(),
                task=self.build_task(),
            )
            second_response = client.fetch(
                request=request,
                profile=self.build_profile(),
                task=self.build_task(),
            )

            self.assertFalse(first_response.from_cache)
            self.assertTrue(second_response.from_cache)
            self.assertEqual(opener.call_count, 1)
            stats = client.build_stats()
            self.assertEqual(stats["total_requests"], 2)
            self.assertEqual(stats["network_requests"], 1)
            self.assertTrue(stats["cache_enabled"])
            self.assertEqual(stats["cache_hits"], 1)
            self.assertEqual(stats["cache_misses"], 1)
            self.assertEqual(stats["cache_writes"], 1)
            self.assertEqual(stats["source_stats"]["example_api"]["cache_hits"], 1)
            self.assertEqual(stats["source_stats"]["example_api"]["network_requests"], 1)
            cache_files = list((Path(temp_dir) / "example_api").glob("*.json"))
            self.assertEqual(len(cache_files), 1)


if __name__ == "__main__":
    unittest.main()