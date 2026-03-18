from __future__ import annotations

import unittest

from app.connectors.qianxin_update import QianxinUpdateConnector


SAMPLE_HTML = """
<div class="product-announcement__bd">
  <ul class="product-announcement__items">
    <li class="product-announcement__item">
      <span class="product-announcement__col order">418</span>
      <span class="product-announcement__col title">
        <a href="https://static01-www.qianxin.com/qaxweb/d5ecc5b77f1092ef4a2aff4c813acb33.pdf" target="_blank">奇安信网神网络空间安全态势感知与协调指挥系统V3.0产品版本升级公告</a>
      </span>
      <span class="product-announcement__col tag">
        <a href="/support/update?sid=203" target="_blank">升级公告</a>
      </span>
      <span class="product-announcement__col date">2026-03-03</span>
    </li>
  </ul>
</div>
"""


class QianxinUpdateConnectorTests(unittest.TestCase):
    def test_parse_list_page(self) -> None:
        connector = QianxinUpdateConnector()
        items = connector._parse_list_page(SAMPLE_HTML)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].source_item_id, "418")
        self.assertEqual(items[0].published_at, "2026-03-03")
        self.assertEqual(items[0].tag, "升级公告")
        self.assertIn("版本升级公告", items[0].title)


if __name__ == "__main__":
    unittest.main()
