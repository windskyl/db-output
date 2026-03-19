from __future__ import annotations

import hashlib
import json
import re
import urllib.parse
from datetime import UTC, date, datetime
from typing import Any

from app.connectors.common import build_request_context, format_template, matches_relevance
from app.fetching.client import FetchClient
from app.fetching.limiter import RateLimiter
from app.fetching.models import FetchRequest
from app.fetching.scheduler import Scheduler
from app.models.records import RawRecord
from app.models.source_profile import SourceProfile
from app.models.task_spec import TaskSpec


class JsonApiConnector:
    connector_kind = "json_api"

    def __init__(self, scheduler: Scheduler | None = None) -> None:
        self.scheduler = scheduler or Scheduler(FetchClient(rate_limiter=RateLimiter()))

    def collect(self, profile: SourceProfile, task: TaskSpec) -> list[RawRecord]:
        start_date = date.fromisoformat(task.time_range.start[:10])
        end_date = date.fromisoformat(task.time_range.end[:10])
        scoped_entity = self._is_scoped_entity(profile, task)
        request_url = self._build_request_url(profile, task)
        response = self.scheduler.fetch(
            request=FetchRequest(url=request_url, headers={"Accept": "application/json"}),
            profile=profile,
            task=task,
        )
        payload = response.json()
        items = self._extract_items(payload, profile.json_items_path or "")
        if not isinstance(items, list):
            return []

        records: list[RawRecord] = []
        for item in items[: profile.max_items_per_fetch]:
            if not isinstance(item, dict):
                continue
            parsed = self._parse_item(profile, item, root_payload=payload)
            if not parsed:
                continue
            published_at = parsed.get("published_at", "")
            if not published_at:
                continue
            published_date = date.fromisoformat(published_at[:10])
            if published_date < start_date or published_date > end_date:
                continue
            if not matches_relevance(profile, parsed, task, scoped_entity=scoped_entity):
                continue
            source_item_id = parsed.get("source_item_id") or hashlib.sha256((parsed.get("url", "") + parsed.get("title", "")).encode("utf-8")).hexdigest()
            records.append(
                RawRecord(
                    task_id=task.task_id,
                    domain=task.domain,
                    source_id=profile.source_id,
                    source_type=profile.source_type,
                    source_label=profile.source_label,
                    fetched_at=datetime.now(UTC).isoformat(),
                    request_url=request_url,
                    http_status=response.status_code,
                    content_hash=f"{profile.source_id}:{source_item_id}:{published_at}",
                    raw_payload=parsed,
                )
            )
        return records

    def _build_request_url(self, profile: SourceProfile, task: TaskSpec) -> str:
        context = build_request_context(profile, task)
        base_url = format_template(profile.first_page_url, context)
        if not profile.request_query_params:
            return base_url
        rendered_params = {
            key: format_template(value, context)
            for key, value in profile.request_query_params.items()
            if format_template(value, context)
        }
        if not rendered_params:
            return base_url
        parsed = urllib.parse.urlsplit(base_url)
        existing_params = urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
        merged_params = existing_params + list(rendered_params.items())
        query = urllib.parse.urlencode(merged_params)
        return urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, parsed.path, query, parsed.fragment))

    def _extract_items(self, payload: Any, path: str) -> Any:
        value: Any = payload
        for part in path.split("."):
            if not part:
                continue
            if isinstance(value, dict):
                value = value.get(part)
            elif isinstance(value, list) and part.isdigit() and int(part) < len(value):
                value = value[int(part)]
            else:
                return None
        return value

    def _parse_item(self, profile: SourceProfile, item: dict[str, Any], root_payload: Any | None = None) -> dict[str, str]:
        parsed: dict[str, str] = {}
        for target_field, source_path in profile.json_field_paths.items():
            value = self._extract_field_value(item, source_path, root_payload=root_payload)
            if value in (None, "", [], {}):
                continue
            if isinstance(value, list):
                value = " ".join(str(part) for part in value if part not in (None, ""))
            elif isinstance(value, dict):
                value = json.dumps(value, ensure_ascii=False, sort_keys=True)
            else:
                value = str(value)
            if target_field == "published_at":
                normalized_date = self._normalize_date(value)
                if normalized_date:
                    parsed[target_field] = normalized_date
                continue
            if target_field == "url":
                value = urllib.parse.urljoin(profile.base_url, value)
            parsed[target_field] = value
        for field in profile.clean_fields:
            if field in parsed:
                parsed[field] = self._clean_text(parsed[field])
        return parsed

    def _extract_field_value(self, item: dict[str, Any], path_expression: str, root_payload: Any | None = None) -> Any:
        for candidate in path_expression.split("|"):
            candidate = candidate.strip()
            if not candidate:
                continue
            if candidate.startswith("literal:"):
                return candidate.removeprefix("literal:")
            if candidate.startswith("$root.") and root_payload is not None:
                value = self._extract_items(root_payload, candidate.removeprefix("$root."))
            else:
                value = self._extract_items(item, candidate)
            if value not in (None, "", [], {}):
                return value
        return None

    def _normalize_date(self, value: str) -> str | None:
        try:
            normalized = value.replace("Z", "+00:00")
            return datetime.fromisoformat(normalized).date().isoformat()
        except ValueError:
            match = re.search(r"\d{4}-\d{2}-\d{2}", value)
            if match:
                return match.group(0)
            return None

    def _is_scoped_entity(self, profile: SourceProfile, task: TaskSpec) -> bool:
        if not profile.entity_scope:
            return False
        targets = [str(target.get("value", "")).strip() for target in task.targets]
        return any(target in profile.entity_scope for target in targets)

    def _clean_text(self, text: str) -> str:
        return " ".join(str(text).split())
