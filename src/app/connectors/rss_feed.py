from __future__ import annotations

import hashlib
import html
import re
import xml.etree.ElementTree as ET
from datetime import UTC, date, datetime
from email.utils import parsedate_to_datetime

from app.connectors.common import matched_topics, matches_relevance
from app.fetching.client import FetchClient
from app.fetching.limiter import RateLimiter
from app.fetching.models import FetchRequest
from app.fetching.scheduler import Scheduler
from app.models.records import RawRecord
from app.models.source_profile import SourceProfile
from app.models.task_spec import TaskSpec


class RssFeedConnector:
    connector_kind = "rss_feed"

    def __init__(self, scheduler: Scheduler | None = None) -> None:
        self.scheduler = scheduler or Scheduler(FetchClient(rate_limiter=RateLimiter()))

    def collect(self, profile: SourceProfile, task: TaskSpec) -> list[RawRecord]:
        start_date = date.fromisoformat(task.time_range.start[:10])
        end_date = date.fromisoformat(task.time_range.end[:10])
        scoped_entity = self._is_scoped_entity(profile, task)
        response = self.scheduler.fetch(
            request=FetchRequest(url=profile.first_page_url, headers={"Accept": "application/rss+xml,application/xml,text/xml"}),
            profile=profile,
            task=task,
        )
        root = ET.fromstring(response.text())
        channel = root.find(".//channel")
        fallback_date = self._parse_date(self._find_text(channel, "lastBuildDate")) if channel is not None else None
        items = root.findall(".//item")[: profile.max_items_per_fetch]

        records: list[RawRecord] = []
        for item in items:
            parsed = self._parse_item(profile, item, fallback_date)
            if not parsed:
                continue
            published_at = parsed.get("published_at", "")
            if not published_at:
                continue
            published_date = date.fromisoformat(published_at[:10])
            if published_date < start_date or published_date > end_date:
                continue
            parsed["matched_topics"] = matched_topics(profile, parsed, task)
            if not matches_relevance(profile, parsed, task, scoped_entity=scoped_entity):
                continue
            source_item_id = parsed.get("source_item_id") or parsed.get("guid") or hashlib.sha256((parsed.get("url", "") + parsed.get("title", "")).encode("utf-8")).hexdigest()
            records.append(
                RawRecord(
                    task_id=task.task_id,
                    domain=task.domain,
                    source_id=profile.source_id,
                    source_type=profile.source_type,
                    source_label=profile.source_label,
                    fetched_at=datetime.now(UTC).isoformat(),
                    request_url=profile.first_page_url,
                    http_status=response.status_code,
                    content_hash=f"{profile.source_id}:{source_item_id}:{published_at}",
                    raw_payload=parsed,
                )
            )
        return records

    def _parse_item(self, profile: SourceProfile, item: ET.Element, fallback_date: str | None) -> dict[str, str]:
        field_map = profile.rss_item_fields or {
            "title": "title",
            "url": "link",
            "summary": "description",
            "guid": "guid",
            "published_at": "pubDate",
        }
        parsed: dict[str, str] = {}
        raw_description = ""
        for target_field, source_field in field_map.items():
            text = self._find_text(item, source_field)
            if text:
                parsed[target_field] = text
                if target_field == "summary":
                    raw_description = text
        if "published_at" in parsed:
            parsed["published_at"] = self._parse_date(parsed["published_at"]) or fallback_date or ""
        elif fallback_date:
            parsed["published_at"] = fallback_date
        if profile.decode_html_entities:
            parsed = {key: html.unescape(value) for key, value in parsed.items()}
            raw_description = html.unescape(raw_description)
        if raw_description:
            parsed.update(self._extract_job_metadata(raw_description))
        for field in profile.clean_fields:
            if field in parsed:
                parsed[field] = self._clean_text(parsed[field])
        return parsed

    def _extract_job_metadata(self, raw_description: str) -> dict[str, str]:
        metadata: dict[str, str] = {}
        first_line = raw_description.splitlines()[0].strip() if raw_description else ""
        if first_line:
            metadata["location"] = first_line
        return metadata

    def _parse_date(self, value: str) -> str | None:
        if not value:
            return None
        try:
            return parsedate_to_datetime(value).date().isoformat()
        except Exception:
            try:
                return datetime.fromisoformat(value.replace("Z", "+00:00")).date().isoformat()
            except ValueError:
                match = re.search(r"\d{4}-\d{2}-\d{2}", value)
                return match.group(0) if match else None

    def _find_text(self, item: ET.Element | None, tag_name: str) -> str:
        if item is None:
            return ""
        child = item.find(tag_name)
        if child is not None and child.text:
            return child.text
        return ""

    def _is_scoped_entity(self, profile: SourceProfile, task: TaskSpec) -> bool:
        if not profile.entity_scope:
            return False
        targets = [str(target.get("value", "")).strip() for target in task.targets]
        return any(target in profile.entity_scope for target in targets)

    def _clean_text(self, text: str) -> str:
        return " ".join(re.sub(r"<[^>]+>", " ", text).split())