from __future__ import annotations

import hashlib
import html
import re
import urllib.parse
from datetime import UTC, date, datetime

from app.connectors.common import build_request_context, format_template, matched_topics, matches_relevance
from app.fetching.client import FetchClient
from app.fetching.limiter import RateLimiter
from app.fetching.models import FetchRequest
from app.fetching.scheduler import Scheduler
from app.models.records import RawRecord
from app.models.source_profile import SourceProfile
from app.models.task_spec import TaskSpec


class RegexHtmlListConnector:
    connector_kind = "regex_html_list"

    def __init__(self, scheduler: Scheduler | None = None) -> None:
        self.scheduler = scheduler or Scheduler(FetchClient(rate_limiter=RateLimiter()))

    def collect(self, profile: SourceProfile, task: TaskSpec) -> list[RawRecord]:
        start_date = date.fromisoformat(task.time_range.start[:10])
        end_date = date.fromisoformat(task.time_range.end[:10])
        item_regex = re.compile(profile.item_pattern, self._flags(profile.item_pattern_flags))
        field_regexes = {
            key: re.compile(pattern, self._flags(profile.field_pattern_flags))
            for key, pattern in profile.field_patterns.items()
        }
        pagination_regex = re.compile(profile.pagination_pattern) if profile.pagination_pattern else None
        scoped_entity = self._is_scoped_entity(profile, task)

        records: list[RawRecord] = []
        page = 1
        max_pages = max(1, profile.max_pages)
        while page <= max_pages:
            page_url = self._build_page_url(profile, task, page)
            response = self.scheduler.fetch(
                request=FetchRequest(url=page_url, headers={"Accept": "text/html,application/xhtml+xml"}),
                profile=profile,
                task=task,
            )
            html_text = response.text()
            items = self._parse_items(profile, html_text, item_regex, field_regexes)
            if not items:
                break

            reached_older_items = False
            for item in items:
                published_at = item.get("published_at", "")
                if not published_at:
                    continue
                published_date = date.fromisoformat(published_at[:10])
                if published_date < start_date:
                    reached_older_items = True
                    continue
                if published_date > end_date:
                    continue
                item["matched_topics"] = matched_topics(profile, item, task)
                if not matches_relevance(profile, item, task, scoped_entity=scoped_entity):
                    continue
                item_source_id = str(item.get("source_item_id") or hashlib.sha256((item.get("url", "") + item.get("title", "")).encode("utf-8")).hexdigest())
                records.append(
                    RawRecord(
                        task_id=task.task_id,
                        domain=task.domain,
                        source_id=profile.source_id,
                        source_type=profile.source_type,
                        source_label=profile.source_label,
                        fetched_at=datetime.now(UTC).isoformat(),
                        request_url=page_url,
                        http_status=response.status_code,
                        content_hash=f"{profile.source_id}:{item_source_id}:{published_at}",
                        raw_payload=item,
                    )
                )
            if profile.stop_on_older_items and reached_older_items:
                break
            if not pagination_regex:
                break
            known_pages = [int(num) for num in pagination_regex.findall(html_text)]
            if page >= max(known_pages, default=1):
                break
            page += 1
        return records

    def _build_page_url(self, profile: SourceProfile, task: TaskSpec, page: int) -> str:
        context = build_request_context(profile, task, page=page)
        template = profile.first_page_url if page == 1 or not profile.paged_url_template else profile.paged_url_template
        return format_template(template, context)

    def _parse_items(self, profile: SourceProfile, html_text: str, item_regex: re.Pattern[str], field_regexes: dict[str, re.Pattern[str]]) -> list[dict[str, str]]:
        text = html.unescape(html_text) if profile.decode_html_entities else html_text
        items: list[dict[str, str]] = []
        for match in item_regex.finditer(text):
            body = match.groupdict().get("body", match.group(0))
            item: dict[str, str] = {key: value for key, value in match.groupdict().items() if value and key != "body"}
            for field_name, regex in field_regexes.items():
                field_match = regex.search(body)
                if field_match:
                    value = field_match.groupdict().get("value")
                    if value is not None:
                        item[field_name] = value
            if "published_at" not in item and {"published_year", "published_month", "published_day"}.issubset(item):
                item["published_at"] = f"{int(item['published_year']):04d}-{int(item['published_month']):02d}-{int(item['published_day']):02d}"
            if "summary" not in item and "tag" in item:
                item["summary"] = item["tag"]
            if "url" in item:
                item["url"] = urllib.parse.urljoin(profile.base_url, item["url"])
            for field in profile.clean_fields:
                if field in item:
                    item[field] = self._clean_text(item[field])
            items.append(item)
        return items

    def _is_scoped_entity(self, profile: SourceProfile, task: TaskSpec) -> bool:
        if not profile.entity_scope:
            return False
        targets = [str(target.get("value", "")).strip() for target in task.targets]
        return any(target in profile.entity_scope for target in targets)

    def _clean_text(self, text: str) -> str:
        return " ".join(re.sub(r"<[^>]+>", " ", text).split())

    def _flags(self, names: list[str]) -> int:
        value = 0
        for name in names:
            value |= getattr(re, name)
        return value