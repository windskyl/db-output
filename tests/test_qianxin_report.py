from __future__ import annotations

import unittest

from app.connectors.qianxin_report import QianxinReportConnector


SAMPLE_HTML = """
<div class="report-list">
  <div class="content">
    <ul>
      <li class="report-list-item">
        <div class="report-list-item-box">
          <div class="report-list-item-content">
            <a href="/report/detail/rid/102">
              <div class="report-list-item-title">
                <span class="report-list-item-time">2025&#24180;12&#26376;11&#26085;</span>
                <span class="report-list-item-tag">赛迪顾问</span>
                <span class="report-list-item-hd">中国威胁情报市场研究报告（2025）</span>
              </div>
              <p class="report-list-item-info">奇安信集团在威胁情报领域持续领跑。</p>
            </a>
          </div>
        </div>
      </li>
    </ul>
  </div>
</div>
"""


class QianxinReportConnectorTests(unittest.TestCase):
    def test_parse_list_page(self) -> None:
        connector = QianxinReportConnector()
        items = connector._parse_list_page(SAMPLE_HTML)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].source_item_id, "102")
        self.assertEqual(items[0].published_at, "2025-12-11")
        self.assertEqual(items[0].tag, "赛迪顾问")
        self.assertIn("威胁情报", items[0].title)


if __name__ == "__main__":
    unittest.main()
