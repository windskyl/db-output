from __future__ import annotations

import unittest
import xml.etree.ElementTree as ET

from app.connectors.rss_feed import RssFeedConnector
from app.models.source_profile import SourceProfile


RSS_SAMPLE = """
<rss version="2.0">
  <channel>
    <item>
      <title>Python Developer - Remote, DivIHN Integration Inc</title>
      <link>https://www.python.org/jobs/8052/</link>
      <description>Atlanta, US\n&lt;p&gt;Responsibilities include Python development.&lt;/p&gt;</description>
      <guid>https://www.python.org/jobs/8052/</guid>
      <pubDate>Fri, 06 Mar 2026 14:32:16 +0000</pubDate>
    </item>
  </channel>
</rss>
"""

RSS_SAMPLE_WITHOUT_PUBDATE = """
<rss version="2.0">
  <channel>
    <lastBuildDate>Mon, 23 Mar 2026 09:25:08 +0000</lastBuildDate>
    <item>
      <title>Python Software Engineer, HypothesisBase</title>
      <link>https://www.python.org/jobs/8054/</link>
      <description>Remote, USA\n&lt;p&gt;Assist in the development of software applications using Python.&lt;/p&gt;</description>
      <guid>https://www.python.org/jobs/8054/</guid>
    </item>
  </channel>
</rss>
"""


class RssFeedConnectorTests(unittest.TestCase):
    def build_profile(self) -> SourceProfile:
        return SourceProfile(
            source_id='python_org_jobs_rss',
            domain='jobs',
            connector_kind='rss_feed',
            source_type='public_jobs_rss',
            source_label='Python.org Jobs RSS',
            base_url='https://www.python.org',
            first_page_url='https://www.python.org/jobs/feed/rss/',
            source_channel='rss',
            max_items_per_fetch=50,
            clean_fields=['title', 'summary'],
            text_match_fields=['title', 'summary', 'location'],
            rss_item_fields={'title': 'title', 'url': 'link', 'summary': 'description', 'guid': 'guid', 'published_at': 'pubDate'},
        )

    def test_parse_rss_item(self) -> None:
        item = ET.fromstring(RSS_SAMPLE).find('.//item')
        parsed = RssFeedConnector()._parse_item(self.build_profile(), item, None)
        self.assertEqual(parsed['published_at'], '2026-03-06')
        self.assertIn('Python Developer', parsed['title'])
        self.assertEqual(parsed['location'], 'Atlanta, US')

    def test_parse_rss_item_falls_back_to_channel_last_build_date_when_pubdate_is_missing(self) -> None:
        root = ET.fromstring(RSS_SAMPLE_WITHOUT_PUBDATE)
        item = root.find('.//item')
        fallback_date = RssFeedConnector()._parse_date(root.findtext('.//channel/lastBuildDate'))
        parsed = RssFeedConnector()._parse_item(self.build_profile(), item, fallback_date)
        self.assertEqual(parsed['published_at'], '2026-03-23')
        self.assertIn('Python Software Engineer', parsed['title'])
        self.assertEqual(parsed['location'], 'Remote, USA')


if __name__ == '__main__':
    unittest.main()