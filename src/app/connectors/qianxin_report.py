from __future__ import annotations

import html
import re
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import UTC, date, datetime

from app.models.records import RawRecord
from app.models.task_spec import TaskSpec


ITEM_RE = re.compile(
    r'<li class="report-list-item">.*?'
    r'<a href="(?P<href>/report/detail/rid/(?P<rid>\d+))">.*?'
    r'<span\s+class="report-list-item-time">(?P<year>\d{4})年(?P<month>\d{1,2})月(?P<day>\d{1,2})日</span>.*?'
    r'<span\s+class="report-list-item-tag">(?P<tag>.*?)</span>.*?'
    r'<span\s+class="report-list-item-hd">(?P<title>.*?)</span>.*?'
    r'<p class="report-list-item-info">\s*(?P<summary>.*?)\s*</p>',
    re.S,
)
NEXT_PAGE_RE = re.compile(r'/report/index\?page=(\d+)')
HTML_TAG_RE = re.compile(r'<[^>]+>')


@dataclass(slots=True)
class QianxinReportItem:
    source_item_id: str
    title: str
    summary: str
    tag: str
    url: str
    published_at: str


class QianxinReportConnector:
    source_id = 'qianxin_report'
    base_url = 'https://www.qianxin.com'

    def collect(self, task: TaskSpec) -> list[RawRecord]:
        start_date = date.fromisoformat(task.time_range.start[:10])
        end_date = date.fromisoformat(task.time_range.end[:10])
        max_pages = max(1, min(task.source_policy.max_sources, 8))
        target_texts = [str(target.get('value', '')).strip() for target in task.targets]
        official_target = any('奇安信' in target for target in target_texts)

        records: list[RawRecord] = []
        page = 1
        while page <= max_pages:
            url = f'{self.base_url}/report/index' if page == 1 else f'{self.base_url}/report/index?page={page}'
            html_text = self._fetch_text(url)
            items = self._parse_list_page(html_text)
            if not items:
                break

            reached_older_items = False
            for item in items:
                published = date.fromisoformat(item.published_at)
                if published < start_date:
                    reached_older_items = True
                    continue
                if published > end_date:
                    continue
                if target_texts and not official_target and not self._matches_targets(item, target_texts):
                    continue
                records.append(
                    RawRecord(
                        task_id=task.task_id,
                        domain=task.domain,
                        source_id=self.source_id,
                        fetched_at=datetime.now(UTC).isoformat(),
                        request_url=url,
                        http_status=200,
                        content_hash=f'{item.source_item_id}:{item.published_at}',
                        raw_payload={
                            'source_item_id': item.source_item_id,
                            'title': item.title,
                            'summary': item.summary,
                            'tag': item.tag,
                            'url': item.url,
                            'published_at': item.published_at,
                        },
                    )
                )
            if reached_older_items:
                break
            if page >= self._max_known_page(html_text):
                break
            page += 1
        return records

    def _fetch_text(self, url: str) -> str:
        request = urllib.request.Request(
            url,
            headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                              '(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
                'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            },
        )
        with urllib.request.urlopen(request, timeout=20) as response:
            return response.read().decode('utf-8', errors='ignore')

    def _parse_list_page(self, html_text: str) -> list[QianxinReportItem]:
        decoded = html.unescape(html_text)
        items: list[QianxinReportItem] = []
        for match in ITEM_RE.finditer(decoded):
            items.append(
                QianxinReportItem(
                    source_item_id=match.group('rid'),
                    title=self._clean_text(match.group('title')),
                    summary=self._clean_text(match.group('summary')),
                    tag=self._clean_text(match.group('tag')),
                    url=urllib.parse.urljoin(self.base_url, match.group('href').strip()),
                    published_at=f"{match.group('year')}-{int(match.group('month')):02d}-{int(match.group('day')):02d}",
                )
            )
        return items

    def _clean_text(self, text: str) -> str:
        return ' '.join(HTML_TAG_RE.sub(' ', text).split())

    def _matches_targets(self, item: QianxinReportItem, targets: list[str]) -> bool:
        haystack = f'{item.title} {item.summary} {item.tag}'
        return any(target and target in haystack for target in targets)

    def _max_known_page(self, html_text: str) -> int:
        pages = [int(page) for page in NEXT_PAGE_RE.findall(html_text)]
        return max(pages, default=1)
