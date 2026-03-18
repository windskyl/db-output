from __future__ import annotations

import gzip
import hashlib
import html
import re
import urllib.parse
import urllib.request
from datetime import UTC, date, datetime

from app.models.records import RawRecord
from app.models.source_profile import SourceProfile
from app.models.task_spec import TaskSpec


class RegexHtmlListConnector:
    connector_kind = 'regex_html_list'

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
            page_url = profile.first_page_url if page == 1 or not profile.paged_url_template else profile.paged_url_template.format(page=page)
            html_text = self._fetch_text(page_url)
            items = self._parse_items(profile, html_text, item_regex, field_regexes)
            if not items:
                break

            reached_older_items = False
            for item in items:
                published_at = item.get('published_at', '')
                if not published_at:
                    continue
                published_date = date.fromisoformat(published_at[:10])
                if published_date < start_date:
                    reached_older_items = True
                    continue
                if published_date > end_date:
                    continue
                if task.relevance_policy.require_target_match and not scoped_entity and not self._matches_targets(profile, item, task):
                    continue
                item_source_id = str(item.get('source_item_id') or hashlib.sha256((item.get('url', '') + item.get('title', '')).encode('utf-8')).hexdigest())
                records.append(
                    RawRecord(
                        task_id=task.task_id,
                        domain=task.domain,
                        source_id=profile.source_id,
                        source_type=profile.source_type,
                        source_label=profile.source_label,
                        fetched_at=datetime.now(UTC).isoformat(),
                        request_url=page_url,
                        http_status=200,
                        content_hash=f'{profile.source_id}:{item_source_id}:{published_at}',
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

    def _parse_items(self, profile: SourceProfile, html_text: str, item_regex: re.Pattern[str], field_regexes: dict[str, re.Pattern[str]]) -> list[dict[str, str]]:
        text = html.unescape(html_text) if profile.decode_html_entities else html_text
        items: list[dict[str, str]] = []
        for match in item_regex.finditer(text):
            body = match.groupdict().get('body', match.group(0))
            item: dict[str, str] = {key: value for key, value in match.groupdict().items() if value and key != 'body'}
            for field_name, regex in field_regexes.items():
                field_match = regex.search(body)
                if field_match:
                    value = field_match.groupdict().get('value')
                    if value is not None:
                        item[field_name] = value
            if 'published_at' not in item and {'published_year', 'published_month', 'published_day'}.issubset(item):
                item['published_at'] = f"{int(item['published_year']):04d}-{int(item['published_month']):02d}-{int(item['published_day']):02d}"
            if 'summary' not in item and 'tag' in item:
                item['summary'] = item['tag']
            if 'url' in item:
                item['url'] = urllib.parse.urljoin(profile.base_url, item['url'])
            for field in profile.clean_fields:
                if field in item:
                    item[field] = self._clean_text(item[field])
            items.append(item)
        return items

    def _fetch_text(self, url: str) -> str:
        request = urllib.request.Request(
            url,
            headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                              '(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
                'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
                'Accept-Encoding': 'gzip',
            },
        )
        with urllib.request.urlopen(request, timeout=20) as response:
            data = response.read()
            if response.headers.get('Content-Encoding') == 'gzip' or data[:2] == b'\x1f\x8b':
                data = gzip.decompress(data)
            return data.decode('utf-8', errors='ignore')

    def _matches_targets(self, profile: SourceProfile, item: dict[str, str], task: TaskSpec) -> bool:
        haystack = ' '.join(str(item.get(field, '')) for field in profile.text_match_fields)
        targets = [str(target.get('value', '')).strip() for target in task.targets]
        return any(target and target.lower() in haystack.lower() for target in targets)

    def _is_scoped_entity(self, profile: SourceProfile, task: TaskSpec) -> bool:
        if not profile.entity_scope:
            return False
        targets = [str(target.get('value', '')).strip() for target in task.targets]
        return any(target in profile.entity_scope for target in targets)

    def _clean_text(self, text: str) -> str:
        return ' '.join(re.sub(r'<[^>]+>', ' ', text).split())

    def _flags(self, names: list[str]) -> int:
        value = 0
        for name in names:
            value |= getattr(re, name)
        return value
