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
        self.base_url = f"http://127.0.0.1:{self.server.server_address[1]}"

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)
        self.temp_dir.cleanup()

    def test_meta_and_home_routes_work(self) -> None:
        meta_text = request.urlopen(f"{self.base_url}/api/meta", timeout=10).read().decode('utf-8')
        html_text = request.urlopen(f"{self.base_url}/", timeout=10).read().decode('utf-8')

        meta_payload = json.loads(meta_text)
        self.assertTrue(meta_payload['ok'])
        self.assertIn('domains', meta_payload['meta'])
        self.assertIn('examples', meta_payload['meta'])
        self.assertIn('db-output Web', html_text)
        self.assertIn('Task Input', html_text)
        self.assertIn('Recent runs', html_text)

    def test_tasks_route_returns_empty_list_for_fresh_base_dir(self) -> None:
        body = json.dumps({'limit': 5}, ensure_ascii=False).encode('utf-8')
        response = request.urlopen(
            request.Request(
                f"{self.base_url}/api/tasks",
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
                f"{self.base_url}/api/draft/form",
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