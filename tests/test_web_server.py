from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from threading import Thread
from urllib import request

from http.server import ThreadingHTTPServer

from app.interfaces.web.server import WebApplication, make_handler


class WebServerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base_dir = Path(self.temp_dir.name)
        self.app = WebApplication(base_dir=self.base_dir)
        self.server = ThreadingHTTPServer(('127.0.0.1', 0), make_handler(self.app))
        self.thread = Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base_url = f'http://127.0.0.1:{self.server.server_address[1]}'

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)
        self.temp_dir.cleanup()

    def test_meta_and_home_routes_work(self) -> None:
        meta_text = request.urlopen(f'{self.base_url}/api/meta', timeout=10).read().decode('utf-8')
        html_text = request.urlopen(f'{self.base_url}/', timeout=10).read().decode('utf-8')

        meta_payload = json.loads(meta_text)
        self.assertTrue(meta_payload['ok'])
        self.assertIn('domains', meta_payload['meta'])
        self.assertIn('examples', meta_payload['meta'])
        self.assertIn('db-output 本地工作台', html_text)
        self.assertIn('任务输入', html_text)
        self.assertIn('最近运行', html_text)
        self.assertIn('结果预览', html_text)
        self.assertIn('id="sourceWhitelist"', html_text)
        self.assertIn('id="resultPreview"', html_text)

    def test_tasks_route_returns_empty_list_for_fresh_base_dir(self) -> None:
        body = json.dumps({'limit': 5}, ensure_ascii=False).encode('utf-8')
        response = request.urlopen(
            request.Request(
                f'{self.base_url}/api/tasks',
                method='POST',
                data=body,
                headers={'Content-Type': 'application/json'},
            ),
            timeout=10,
        )
        payload = json.loads(response.read().decode('utf-8'))

        self.assertTrue(payload['ok'])
        self.assertEqual(payload['result']['total'], 0)
        self.assertEqual(payload['result']['tasks'], [])

    def test_report_route_exposes_full_task_payload_for_recent_run_reuse(self) -> None:
        task = {
            'task_id': 'web-public-sentiment-001',
            'domain': 'public_sentiment',
            'scenario_template': 'company_sentiment_tracking_basic',
            'targets': [{'type': 'company', 'value': 'OpenAI'}],
            'topic_scope': ['tech_stack_engineering'],
            'time_range': {'start': '2026-03-01T00:00:00', 'end': '2026-12-31T23:59:59', 'timezone': 'UTC'},
            'source_policy': {'selection_mode': 'explicit', 'whitelist': ['hn_algolia_company_story_search'], 'allow_html': False, 'allow_rss': False, 'allow_api': True},
            'relevance_policy': {'require_target_match': True, 'require_topic_match': True, 'require_cooccurrence': False, 'min_relevance_score': 0.6},
            'output_policy': {'writer': 'sqlite', 'keep_raw': True, 'keep_normalized': True, 'max_output_records': 10, 'update_mode': 'replace'},
            'run_policy': {'enable_cache': False},
        }
        run_response = request.urlopen(
            request.Request(
                f'{self.base_url}/api/run',
                method='POST',
                data=json.dumps({'task': task}, ensure_ascii=False).encode('utf-8'),
                headers={'Content-Type': 'application/json'},
            ),
            timeout=20,
        )
        self.assertEqual(json.loads(run_response.read().decode('utf-8'))['ok'], True)

        report_response = request.urlopen(
            request.Request(
                f'{self.base_url}/api/report',
                method='POST',
                data=json.dumps({'task_id': 'web-public-sentiment-001', 'domain': 'public_sentiment', 'kind': 'run'}, ensure_ascii=False).encode('utf-8'),
                headers={'Content-Type': 'application/json'},
            ),
            timeout=20,
        )
        payload = json.loads(report_response.read().decode('utf-8'))

        self.assertTrue(payload['ok'])
        self.assertEqual(payload['result']['task_payload']['task_id'], 'web-public-sentiment-001')
        self.assertEqual(payload['result']['run_report']['task_payload']['task_id'], 'web-public-sentiment-001')
        self.assertEqual(payload['result']['result_preview']['kind'], 'public_sentiment')
        self.assertGreaterEqual(len(payload['result']['result_preview']['tables']), 1)

    def test_task_route_exposes_full_task_payload_for_reuse(self) -> None:
        task = {
            'task_id': 'web-jobs-001',
            'domain': 'jobs',
            'targets': [{'type': 'keyword', 'value': 'Python'}],
            'topic_scope': ['backend'],
            'time_range': {'start': '2026-03-01T00:00:00', 'end': '2026-03-20T00:00:00', 'timezone': 'UTC'},
            'source_policy': {'selection_mode': 'explicit', 'whitelist': ['python_org_jobs_rss']},
        }
        run_response = request.urlopen(
            request.Request(
                f'{self.base_url}/api/run',
                method='POST',
                data=json.dumps({'task': task}, ensure_ascii=False).encode('utf-8'),
                headers={'Content-Type': 'application/json'},
            ),
            timeout=20,
        )
        self.assertEqual(json.loads(run_response.read().decode('utf-8'))['ok'], True)

        task_response = request.urlopen(
            request.Request(
                f'{self.base_url}/api/task',
                method='POST',
                data=json.dumps({'task_id': 'web-jobs-001', 'domain': 'jobs'}, ensure_ascii=False).encode('utf-8'),
                headers={'Content-Type': 'application/json'},
            ),
            timeout=20,
        )
        payload = json.loads(task_response.read().decode('utf-8'))

        self.assertTrue(payload['ok'])
        self.assertEqual(payload['result']['task_payload']['task_id'], 'web-jobs-001')
        self.assertEqual(payload['result']['task_payload']['targets'][0]['value'], 'Python')
        self.assertEqual(payload['result']['result_preview']['kind'], 'jobs')
        self.assertEqual(payload['result']['result_preview']['tables'][0]['title'], '最新岗位样本')

    def test_form_draft_route_returns_task_payload(self) -> None:
        body = json.dumps(
            {
                'domain': 'jobs',
                'target_type': 'keyword',
                'target_value': 'Python',
                'topic_scope': ['backend'],
                'selection_mode': 'explicit',
                'whitelist': ['python_org_jobs_rss'],
            },
            ensure_ascii=False,
        ).encode('utf-8')
        response = request.urlopen(
            request.Request(
                f'{self.base_url}/api/draft/form',
                method='POST',
                data=body,
                headers={'Content-Type': 'application/json'},
            ),
            timeout=10,
        )
        payload = json.loads(response.read().decode('utf-8'))

        self.assertTrue(payload['ok'])
        self.assertEqual(payload['task']['domain'], 'jobs')
        self.assertEqual(payload['task']['targets'][0]['value'], 'Python')
        self.assertEqual(payload['task']['source_policy']['whitelist'], ['python_org_jobs_rss'])


if __name__ == '__main__':
    unittest.main()
