from __future__ import annotations

import unittest
from datetime import UTC, datetime

from app.interfaces.web.helpers import (
    WebInputError,
    build_task_payload_from_form,
    extract_task_payload_from_document,
    validate_uploaded_text,
)
from app.models.task_spec import TaskSpec


class WebHelperTests(unittest.TestCase):
    def setUp(self) -> None:
        self.now = datetime(2026, 3, 25, 8, 0, 0, tzinfo=UTC)

    def test_build_task_payload_from_form_produces_valid_task(self) -> None:
        payload = build_task_payload_from_form(
            {
                'domain': 'jobs',
                'target_type': 'keyword',
                'target_value': 'Python',
                'topic_scope': ['backend', 'devops'],
                'start': '2026-03-01',
                'end': '2026-03-25',
                'selection_mode': 'explicit',
                'whitelist': ['python_org_jobs_rss'],
                'allow_html': False,
                'allow_rss': True,
                'allow_api': False,
            },
            now=self.now,
        )
        task = TaskSpec.from_dict(payload)
        self.assertEqual(task.domain, 'jobs')
        self.assertEqual(task.targets[0]['value'], 'Python')
        self.assertEqual(task.topic_scope, ['backend', 'devops'])
        self.assertEqual(task.source_policy.selection_mode, 'explicit')
        self.assertEqual(task.source_policy.whitelist, ['python_org_jobs_rss'])

    def test_extract_task_payload_from_json_document(self) -> None:
        result = extract_task_payload_from_document(
            'task.json',
            '{"task_id":"demo-001","domain":"public_sentiment","targets":[{"type":"company","value":"OpenAI"}],"topic_scope":["tech_stack_engineering"],"time_range":{"start":"2026-03-01T00:00:00","end":"2026-03-25T23:59:59","timezone":"UTC"}}',
            now=self.now,
        )
        task = TaskSpec.from_dict(result['task_payload'])
        self.assertEqual(result['mode'], 'json')
        self.assertEqual(task.domain, 'public_sentiment')
        self.assertEqual(task.targets[0]['value'], 'OpenAI')

    def test_extract_task_payload_from_markdown_fenced_json(self) -> None:
        content = '''
# 需求说明

```json
{
  "task_id": "fenced-001",
  "domain": "company_intel",
  "targets": [{"type": "company", "value": "奇安信"}],
  "topic_scope": ["company_profile"],
  "time_range": {"start": "2026-03-01T00:00:00", "end": "2026-03-25T23:59:59", "timezone": "UTC"}
}
```
'''
        result = extract_task_payload_from_document('requirement.md', content, now=self.now)
        task = TaskSpec.from_dict(result['task_payload'])
        self.assertEqual(result['mode'], 'json_block')
        self.assertEqual(task.domain, 'company_intel')
        self.assertEqual(task.targets[0]['value'], '奇安信')

    def test_extract_task_payload_from_plain_text_uses_heuristics(self) -> None:
        content = '''
领域: public_sentiment
目标: OpenAI
主题: tech_stack_engineering
开始: 2026-03-01
结束: 2026-03-25
备注: 想看 OpenAI API、SDK、agent 工程相关的讨论和舆情。
'''
        result = extract_task_payload_from_document('notes.txt', content, now=self.now)
        task = TaskSpec.from_dict(result['task_payload'])
        self.assertEqual(result['mode'], 'heuristic')
        self.assertEqual(task.domain, 'public_sentiment')
        self.assertEqual(task.targets[0]['value'], 'OpenAI')
        self.assertEqual(task.topic_scope, ['tech_stack_engineering'])
        self.assertTrue(result['warnings'])

    def test_validate_uploaded_text_rejects_binary_or_bad_extension(self) -> None:
        with self.assertRaises(WebInputError):
            validate_uploaded_text('payload.exe', 'test')
        with self.assertRaises(WebInputError):
            validate_uploaded_text('payload.txt', 'bad\x00data')


if __name__ == '__main__':
    unittest.main()