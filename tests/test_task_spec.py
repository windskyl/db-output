from __future__ import annotations

import unittest

from app.models.task_spec import TaskSpec, TaskValidationError


class TaskSpecTests(unittest.TestCase):
    def test_quality_policy_rejects_unknown_dedupe_mode(self) -> None:
        with self.assertRaises(TaskValidationError):
            TaskSpec.from_dict(
                {
                    "task_id": "task-001",
                    "domain": "jobs",
                    "targets": [{"type": "keyword", "value": "python"}],
                    "topic_scope": ["backend"],
                    "time_range": {"start": "2026-03-01T00:00:00", "end": "2026-03-20T00:00:00", "timezone": "UTC"},
                    "quality_policy": {
                        "dedupe_mode": "loose",
                    },
                }
            )

    def test_task_spec_can_round_trip_via_to_dict(self) -> None:
        task = TaskSpec.from_dict(
            {
                "task_id": "task-roundtrip-001",
                "domain": "jobs",
                "targets": [{"type": "keyword", "value": "python"}],
                "topic_scope": ["backend"],
                "time_range": {"start": "2026-03-01T00:00:00", "end": "2026-03-20T00:00:00", "timezone": "UTC"},
                "source_policy": {"selection_mode": "explicit", "whitelist": ["python_org_jobs_rss"]},
            }
        )

        payload = task.to_dict()
        rebuilt = TaskSpec.from_dict(payload)

        self.assertEqual(rebuilt.task_id, task.task_id)
        self.assertEqual(rebuilt.domain, task.domain)
        self.assertEqual(rebuilt.targets, task.targets)
        self.assertEqual(rebuilt.topic_scope, task.topic_scope)
        self.assertEqual(rebuilt.source_policy.whitelist, task.source_policy.whitelist)


if __name__ == "__main__":
    unittest.main()