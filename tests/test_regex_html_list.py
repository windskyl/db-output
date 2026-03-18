from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from app.connectors.regex_html_list import RegexHtmlListConnector
from app.models.source_profile import SourceProfile
from app.models.task_spec import TaskSpec


class RegexHtmlListConnectorTests(unittest.TestCase):
    def test_parse_qianxin_update_profile(self) -> None:
        html = """
        <div class="product-announcement__bd">
          <ul class="product-announcement__items">
            <li class="product-announcement__item">
              <span class="product-announcement__col order">418</span>
              <span class="product-announcement__col title">
                <a href="https://static01-www.qianxin.com/demo.pdf" target="_blank">奇安信网神网络空间安全态势感知与协调指挥系统V3.0产品版本升级公告</a>
              </span>
              <span class="product-announcement__col tag">
                <a href="/support/update?sid=203" target="_blank">升级公告</a>
              </span>
              <span class="product-announcement__col date">2026-03-03</span>
            </li>
          </ul>
        </div>
        """
        profile = SourceProfile(
            source_id='qianxin_update',
            domain='company_intel',
            connector_kind='regex_html_list',
            source_type='official_company_update',
            source_label='Qianxin Product Updates',
            base_url='https://www.qianxin.com',
            first_page_url='https://www.qianxin.com/support/update',
            paged_url_template='https://www.qianxin.com/support/update?page={page}',
            max_pages=1,
            item_pattern=r'<li class="product-announcement__item">.*?<span class="product-announcement__col order">(?P<source_item_id>\d+)</span>.*?<span class="product-announcement__col title">\s*<a href="(?P<url>[^"]+)"[^>]*>(?P<title>.*?)</a>\s*</span>.*?<span class="product-announcement__col tag">\s*<a [^>]*>(?P<tag>.*?)</a>\s*</span>.*?<span class="product-announcement__col date">(?P<published_at>\d{4}-\d{2}-\d{2})</span>',
            item_pattern_flags=['DOTALL'],
            field_patterns={},
            field_pattern_flags=['DOTALL'],
            clean_fields=['title', 'tag'],
            entity_scope=['奇安信'],
            text_match_fields=['title', 'tag'],
            pagination_pattern='/support/update\\?page=(\\d+)',
            stop_on_older_items=True,
            decode_html_entities=True,
        )
        connector = RegexHtmlListConnector()
        items = connector._parse_items(profile, html, __import__('re').compile(profile.item_pattern, __import__('re').DOTALL), {})
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]['source_item_id'], '418')
        self.assertEqual(items[0]['tag'], '升级公告')
        self.assertEqual(items[0]['published_at'], '2026-03-03')

    def test_parse_python_jobs_profile(self) -> None:
        html = """
        <ol class="list-recent-jobs list-row-container menu">
          <li>
            <h2 class="listing-company">
              <span class="listing-company-name">
                <a href="/jobs/8052/">Python Developer - Remote</a><br/>
                DivIHN Integration Inc
              </span>
              <span class="listing-location"><a href="/jobs/location/atlanta-us/">Atlanta, US</a></span>
            </h2>
            <span class="listing-job-type">Cloud, Web, Support</span>
            <span class="listing-posted">Posted: <time datetime="2026-03-06T14:32:16.395175+00:00">06 March 2026</time></span>
            <span class="listing-company-category"><a href="/jobs/category/developer-engineer/">Developer / Engineer</a></span>
          </li>
        </ol>
        """
        profile = SourceProfile(
            source_id='python_org_jobs',
            domain='jobs',
            connector_kind='regex_html_list',
            source_type='public_jobs_board',
            source_label='Python.org Jobs',
            base_url='https://www.python.org',
            first_page_url='https://www.python.org/jobs/',
            paged_url_template='https://www.python.org/jobs/?page={page}',
            max_pages=1,
            item_pattern=r'<li>\s*<h2 class="listing-company">(?P<body>.*?)</li>',
            item_pattern_flags=['DOTALL'],
            field_patterns={
                'url': r'<a href="(?P<value>/jobs/\d+/)">',
                'title': r'<a href="/jobs/\d+/">(?P<value>.*?)</a>',
                'company': r'<a href="/jobs/\d+/">.*?</a><br/>\s*(?P<value>.*?)\s*</span>',
                'location': r'<span class="listing-location"><a [^>]*>(?P<value>.*?)</a></span>',
                'summary': r'<span class="listing-job-type">(?P<value>.*?)</span>',
                'category': r'<span class="listing-company-category"><a [^>]*>(?P<value>.*?)</a></span>',
                'published_at': r'<time datetime="(?P<value>[^"]+)">',
            },
            field_pattern_flags=['DOTALL'],
            clean_fields=['title', 'company', 'location', 'summary', 'category'],
            entity_scope=[],
            text_match_fields=['title', 'company', 'location', 'summary', 'category'],
            pagination_pattern=None,
            stop_on_older_items=False,
            decode_html_entities=True,
        )
        connector = RegexHtmlListConnector()
        items = connector._parse_items(profile, html, __import__('re').compile(profile.item_pattern, __import__('re').DOTALL), {k: __import__('re').compile(v, __import__('re').DOTALL) for k, v in profile.field_patterns.items()})
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]['company'], 'DivIHN Integration Inc')
        self.assertIn('Python Developer', items[0]['title'])
        self.assertEqual(items[0]['location'], 'Atlanta, US')


if __name__ == '__main__':
    unittest.main()
