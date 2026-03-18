from __future__ import annotations

import unittest
import xml.etree.ElementTree as ET

from app.connectors.rss_feed import RssFeedConnector
from app.models.source_profile import SourceProfile
from app.models.task_spec import TaskSpec


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


class RssFeedConnectorTests(unittest.TestCase):
    def test_parse_rss_item(self) -> None:
        profile = SourceProfile(
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
        item = ET.fromstring(RSS_SAMPLE).find('.//item')
        parsed = RssFeedConnector()._parse_item(profile, item, None)
        self.assertEqual(parsed['published_at'], '2026-03-06')
        self.assertIn('Python Developer', parsed['title'])
        self.assertEqual(parsed['location'], 'Atlanta, US')


if __name__ == '__main__':
    unittest.main()

