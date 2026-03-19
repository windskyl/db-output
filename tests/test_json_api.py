from __future__ import annotations

import unittest

from app.connectors.json_api import JsonApiConnector
from app.connectors.common import resolve_topic_terms
from app.models.source_profile import SourceProfile, SourceProfileValidationError
from app.models.task_spec import TaskSpec


class JsonApiConnectorTests(unittest.TestCase):
    def test_parse_json_item_with_fallback_paths(self) -> None:
        profile = SourceProfile(
            source_id='hn_algolia_company_story_search',
            domain='public_sentiment',
            connector_kind='json_api',
            source_type='public_forum_api',
            source_label='HN Algolia',
            base_url='https://hn.algolia.com',
            first_page_url='https://hn.algolia.com/api/v1/search_by_date',
            source_channel='api',
            max_items_per_fetch=50,
            clean_fields=['title', 'summary'],
            text_match_fields=['title', 'summary', 'url', 'author'],
            request_query_params={'query': '{target}', 'tags': 'story'},
            json_items_path='hits',
            json_field_paths={
                'source_item_id': 'objectID',
                'title': 'title|story_title',
                'summary': 'story_text|comment_text',
                'url': 'url|story_url',
                'published_at': 'created_at',
                'author': 'author',
            },
            topic_terms={'tech_stack_engineering': ['api', 'model', 'sdk']},
        )
        item = {
            'objectID': '123',
            'title': '',
            'story_title': 'OpenAI releases new API model',
            'comment_text': 'Developers discuss the SDK rollout.',
            'url': 'https://example.com/openai-api',
            'created_at': '2026-03-18T12:02:31Z',
            'author': 'pg',
        }
        parsed = JsonApiConnector()._parse_item(profile, item)
        self.assertEqual(parsed['source_item_id'], '123')
        self.assertEqual(parsed['published_at'], '2026-03-18')
        self.assertIn('OpenAI releases new API model', parsed['title'])
        self.assertIn('SDK rollout', parsed['summary'])

    def test_request_context_uses_topic_terms(self) -> None:
        profile = SourceProfile(
            source_id='hn_algolia_company_story_search',
            domain='public_sentiment',
            connector_kind='json_api',
            source_type='public_forum_api',
            source_label='HN Algolia',
            base_url='https://hn.algolia.com',
            first_page_url='https://hn.algolia.com/api/v1/search_by_date',
            source_channel='api',
            max_items_per_fetch=50,
            json_items_path='hits',
            json_field_paths={'title': 'title', 'published_at': 'created_at'},
            topic_terms={'tech_stack_engineering': ['api', 'model', 'sdk']},
        )
        task = TaskSpec.from_dict({
            'task_id': 'sentiment-api-001',
            'domain': 'public_sentiment',
            'targets': [{'type': 'company', 'value': 'OpenAI'}],
            'topic_scope': ['tech_stack_engineering'],
            'time_range': {'start': '2025-09-01T00:00:00', 'end': '2026-03-18T00:00:00', 'timezone': 'UTC'},
            'source_policy': {'selection_mode': 'explicit', 'whitelist': ['hn_algolia_company_story_search'], 'allow_html': False, 'allow_rss': False, 'allow_api': True},
        })
        self.assertEqual(resolve_topic_terms(profile, task), ['api', 'model', 'sdk'])

    def test_profile_validation_rejects_incomplete_json_api_profile(self) -> None:
        with self.assertRaises(SourceProfileValidationError):
            SourceProfile(
                source_id='bad-json',
                domain='public_sentiment',
                connector_kind='json_api',
                source_type='public_forum_api',
                source_label='Bad',
                base_url='https://example.com',
                first_page_url='https://example.com/api',
                source_channel='api',
                json_items_path='hits',
            ).validate()


if __name__ == '__main__':
    unittest.main()
