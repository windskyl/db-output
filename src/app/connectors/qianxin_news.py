from __future__ import annotations

import html
import re
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Iterable

from app.models.records import RawRecord
from app.models.task_spec import TaskSpec


LIST_ITEM_RE = re.compile(r'<li class="lists statistics-js" data-id="(?P<id>\d+)">(?P<body>.*?)</li>', re.S)
TITLE_RE = re.compile(r'<h3 class="subtitle">.*?<a href="(?P<href>[^"]+)">\s*(?P<title>.*?)\s*</a>', re.S)
SUMMARY_RE = re.compile(r'<p class="news-content">.*?<a [^>]*>\s*(?P<summary>.*?)\s*</a>', re.S)
DATE_RE = re.compile(
    r'<div class="news-date">.*?<span class="year">(?P<year>\d{4})</span>.*?'
    r'<span class="month">(?P<month>\d{2})</span>.*?<span class="day">(?P<day>\d{2})</span>',
    re.S,
)
NEXT_PAGE_RE = re.compile(r'/news/list\?page=(\d+)')
TAG_RE = re.compile(r'<[^>]+>')


@dataclass(slots=True)
class QianxinNewsItem:
    source_id: str
    title: str
    summary: str
    url: str
    published_at: str


class QianxinNewsConnector:
    source_id = 'qianxin_news'
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
            url = f'{self.base_url}/news/list' if page == 1 else f'{self.base_url}/news/list?page={page}'
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
                        content_hash=f'{item.source_id}:{item.published_at}',
                        raw_payload={
                            'source_id': item.source_id,
                            'title': item.title,
                            'summary': item.summary,
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

    def _parse_list_page(self, html_text: str) -> list[QianxinNewsItem]:
        items: list[QianxinNewsItem] = []
        for match in LIST_ITEM_RE.finditer(html_text):
            body = match.group('body')
            title_match = TITLE_RE.search(body)
            date_match = DATE_RE.search(body)
            if not title_match or not date_match:
                continue
            summary_match = SUMMARY_RE.search(body)
            href = urllib.parse.urljoin(self.base_url, html.unescape(title_match.group('href').strip()))
            title = self._clean_text(title_match.group('title'))
            summary = self._clean_text(summary_match.group('summary')) if summary_match else ''
            published_at = f"{date_match.group('year')}-{date_match.group('month')}-{date_match.group('day')}"
            items.append(
                QianxinNewsItem(
                    source_id=match.group('id'),
                    title=title,
                    summary=summary,
                    url=href,
                    published_at=published_at,
                )
            )
        return items

    def _clean_text(self, text: str) -> str:
        return ' '.join(html.unescape(TAG_RE.sub(' ', text)).split())

    def _matches_targets(self, item: QianxinNewsItem, targets: Iterable[str]) -> bool:
        haystack = f'{item.title} {item.summary}'
        return any(target and target in haystack for target in targets)

    def _max_known_page(self, html_text: str) -> int:
        pages = [int(page) for page in NEXT_PAGE_RE.findall(html_text)]
        return max(pages, default=1)
