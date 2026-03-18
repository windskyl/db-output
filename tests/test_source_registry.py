from __future__ import annotations

import unittest
from pathlib import Path

from app.sources.registry import SourceRegistry


ROOT = Path(__file__).resolve().parents[1]


class SourceRegistryTests(unittest.TestCase):
    def test_load_profiles(self) -> None:
        registry = SourceRegistry(ROOT / 'configs' / 'sources')
        sources = registry._profiles
        self.assertIn('qianxin_news', sources)
        self.assertIn('python_org_jobs', sources)
        self.assertEqual(sources['python_org_jobs'].domain, 'jobs')


if __name__ == '__main__':
    unittest.main()
