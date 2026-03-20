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


if __name__ == "__main__":
    unittest.main()