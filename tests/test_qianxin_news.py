from __future__ import annotations

import unittest

from app.connectors.qianxin_news import QianxinNewsConnector


SAMPLE_HTML = """
<ul class="content_list">
  <li class="lists statistics-js" data-id="14626">
    <div class="list_content--container">
      <h3 class="subtitle">
        <a href="/news/detail?news_id=14626">实现“看得清、管得住、用得好”，奇安信安全指南让OpenClaw真正释放生产力</a>
      </h3>
      <p class="news-content">
        <a href="/news/detail?news_id=14626">奇安信发布安全指南，帮助企业管控智能体使用风险。</a>
      </p>
      <div class="news-date">
        <span class="year">2026</span>
        <span class="divider">/</span>
        <span class="month">03</span>
        <span class="divider">/</span>
        <span class="day">16</span>
      </div>
    </div>
  </li>
</ul>
"""


class QianxinNewsConnectorTests(unittest.TestCase):
    def test_parse_list_page(self) -> None:
        connector = QianxinNewsConnector()
        items = connector._parse_list_page(SAMPLE_HTML)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].source_id, "14626")
        self.assertEqual(items[0].published_at, "2026-03-16")
        self.assertIn("奇安信", items[0].title)


if __name__ == "__main__":
    unittest.main()
