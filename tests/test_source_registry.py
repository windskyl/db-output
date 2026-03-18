from __future__ import annotations

import unittest
from pathlib import Path

from app.models.source_profile import SourceProfileValidationError
from app.sources.registry import SourceRegistry
from app.models.task_spec import TaskSpec


ROOT = Path(__file__).resolve().parents[1]


class SourceRegistryTests(unittest.TestCase):
    def test_load_profiles(self) -> None:
        registry = SourceRegistry(ROOT / 'configs' / 'sources')
        sources = registry._profiles
        self.assertIn('qianxin_news', sources)
        self.assertIn('python_org_jobs', sources)
        self.assertIn('python_org_jobs_rss', sources)
        self.assertEqual(sources['python_org_jobs'].domain, 'jobs')

    def test_auto_selection_filters_by_channel(self) -> None:
        registry = SourceRegistry(ROOT / 'configs' / 'sources')
        task = TaskSpec.from_dict({
            'task_id': 'jobs-auto-001',
            'domain': 'jobs',
            'targets': [{'type': 'keyword', 'value': 'Python'}],
            'topic_scope': ['backend'],
            'time_range': {'start': '2026-02-01T00:00:00', 'end': '2026-03-18T00:00:00', 'timezone': 'UTC'},
            'source_policy': {'selection_mode': 'auto', 'allow_html': False, 'allow_rss': True, 'allow_api': False, 'max_sources': 5},
        })
        selected = [profile.source_id for profile in registry.list_for_task(task)]
        self.assertEqual(selected, ['python_org_jobs_rss'])

    def test_explicit_selection_requires_available_source(self) -> None:
        registry = SourceRegistry(ROOT / 'configs' / 'sources')
        task = TaskSpec.from_dict({
            'task_id': 'jobs-explicit-001',
            'domain': 'jobs',
            'targets': [{'type': 'keyword', 'value': 'Python'}],
            'topic_scope': ['backend'],
            'time_range': {'start': '2026-02-01T00:00:00', 'end': '2026-03-18T00:00:00', 'timezone': 'UTC'},
            'source_policy': {'selection_mode': 'explicit', 'whitelist': ['python_org_jobs'], 'allow_html': True, 'allow_rss': True, 'allow_api': False, 'max_sources': 5},
        })
        selected = [profile.source_id for profile in registry.list_for_task(task)]
        self.assertEqual(selected, ['python_org_jobs'])

    def test_profile_validation_rejects_bad_connector_kind(self) -> None:
        with self.assertRaises(SourceProfileValidationError):
            from app.models.source_profile import SourceProfile
            SourceProfile(
                source_id='bad',
                domain='jobs',
                connector_kind='bad_kind',
                source_type='x',
                source_label='x',
                base_url='https://example.com',
                first_page_url='https://example.com'
            ).validate()


if __name__ == '__main__':
    unittest.main()
