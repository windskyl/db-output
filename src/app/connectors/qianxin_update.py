from __future__ import annotations

import html
import re
import urllib.request
from dataclasses import dataclass
from datetime import UTC, date, datetime

from app.models.records import RawRecord
from app.models.task_spec import TaskSpec


ITEM_RE = re.compile(
    r'<li class="product-announcement__item">.*?'
    r'<span class="product-announcement__col order">(?P<order>\d+)</span>.*?'
    r'<span class="product-announcement__col title">\s*<a href="(?P<href>[^"]+)"[^>]*>(?P<title>.*?)</a>\s*</span>.*?'
    r'<span class="product-announcement__col tag">\s*<a [^>]*>(?P<tag>.*?)</a>\s*</span>.*?'
    r'<span class="product-announcement__col date">(?P<date>\d{4}-\d{2}-\d{2})</span>',
    re.S,
)
NEXT_PAGE_RE = re.compile(r'/support/update\?page=(\d+)')
HTML_TAG_RE = re.compile(r'<[^>]+>')


@dataclass(slots=True)
class QianxinUpdateItem:
    source_item_id: str
    title: str
    tag: str
    url: str
    published_at: str


class QianxinUpdateConnector:
    source_id = 'qianxin_update'

    def collect(self, task: TaskSpec) -> list[RawRecord]:
        start_date = date.fromisoformat(task.time_range.start[:10])
        end_date = date.fromisoformat(task.time_range.end[:10])
        max_pages = max(1, min(task.source_policy.max_sources, 8))

        records: list[RawRecord] = []
        page = 1
        while page <= max_pages:
            url = 'https://www.qianxin.com/support/update' if page == 1 else f'https://www.qianxin.com/support/update?page={page}'
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
                            'summary': item.tag,
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

    def _parse_list_page(self, html_text: str) -> list[QianxinUpdateItem]:
        items: list[QianxinUpdateItem] = []
        for match in ITEM_RE.finditer(html_text):
            items.append(
                QianxinUpdateItem(
                    source_item_id=match.group('order'),
                    title=self._clean_text(html.unescape(match.group('title'))),
                    tag=self._clean_text(html.unescape(match.group('tag'))),
                    url=html.unescape(match.group('href')),
                    published_at=match.group('date'),
                )
            )
        return items

    def _clean_text(self, text: str) -> str:
        return ' '.join(HTML_TAG_RE.sub(' ', text).split())

    def _max_known_page(self, html_text: str) -> int:
        pages = [int(page) for page in NEXT_PAGE_RE.findall(html_text)]
        return max(pages, default=1)
