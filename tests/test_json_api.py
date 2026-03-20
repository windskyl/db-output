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

    def test_parse_json_item_supports_root_and_literal_fields(self) -> None:
        profile = SourceProfile(
            source_id='alpha_vantage_demo_earnings',
            domain='finance',
            connector_kind='json_api',
            source_type='public_finance_api',
            source_label='Alpha Vantage Demo Earnings',
            base_url='https://www.alphavantage.co',
            first_page_url='https://www.alphavantage.co/query',
            source_channel='api',
            max_items_per_fetch=12,
            json_items_path='quarterlyEarnings',
            json_field_paths={
                'title': 'literal:Quarterly Earnings',
                'symbol': '$root.symbol',
                'published_at': 'reportedDate|fiscalDateEnding',
                'metric_value': 'reportedEPS',
            },
        )
        payload = {
            'symbol': 'IBM',
            'quarterlyEarnings': [
                {
                    'reportedDate': '2026-01-29',
                    'reportedEPS': '3.92',
                }
            ],
        }
        parsed = JsonApiConnector()._parse_item(profile, payload['quarterlyEarnings'][0], root_payload=payload)
        self.assertEqual(parsed['title'], 'Quarterly Earnings')
        self.assertEqual(parsed['symbol'], 'IBM')
        self.assertEqual(parsed['published_at'], '2026-01-29')
        self.assertEqual(parsed['metric_value'], '3.92')

    def test_dict_items_can_be_coerced_with_key_field(self) -> None:
        items = {
            '2026-03-18': {'4. close': '251.6000', '5. volume': '5177047'},
            '2026-03-17': {'4. close': '253.3500', '5. volume': '3774387'},
        }
        coerced = JsonApiConnector()._coerce_items(items, key_field='trading_date')
        self.assertEqual(len(coerced), 2)
        self.assertEqual(coerced[0]['trading_date'], '2026-03-18')
        self.assertEqual(coerced[0]['4. close'], '251.6000')

    def test_parse_json_item_supports_context_fields(self) -> None:
        profile = SourceProfile(
            source_id='alpha_vantage_demo_daily_quotes',
            domain='finance',
            connector_kind='json_api',
            source_type='public_finance_api',
            source_label='Alpha Vantage Demo Daily Quotes',
            base_url='https://www.alphavantage.co',
            first_page_url='https://www.alphavantage.co/query',
            source_channel='api',
            max_items_per_fetch=10,
            json_items_path='Time Series (Daily)',
            json_item_key_field='trading_date',
            json_field_paths={
                'symbol': '$context.target',
                'published_at': 'trading_date',
                'metric_value': '4. close',
            },
        )
        item = {
            'trading_date': '2026-03-18',
            '4. close': '251.6000',
        }
        parsed = JsonApiConnector()._parse_item(profile, item, context={'target': 'IBM'})
        self.assertEqual(parsed['symbol'], 'IBM')
        self.assertEqual(parsed['published_at'], '2026-03-18')
        self.assertEqual(parsed['metric_value'], '251.6000')

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
