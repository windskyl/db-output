from __future__ import annotations

import gzip
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from app.models.records import RawRecord
from app.models.task_spec import TaskSpec
from app.services.task_service import TaskService


class TaskServiceQualityTests(unittest.TestCase):
    def build_task(
        self,
        *,
        required_fields: list[str],
        max_missing_ratio: float,
        dedupe_mode: str = "strict",
        max_output_records: int = 100,
        topic_scope: list[str] | None = None,
    ) -> TaskSpec:
        return TaskSpec.from_dict(
            {
                "task_id": "job-quality-001",
                "domain": "jobs",
                "targets": [{"type": "keyword", "value": "python backend"}],
                "topic_scope": topic_scope or ["backend"],
                "time_range": {"start": "2026-03-01T00:00:00", "end": "2026-03-20T00:00:00", "timezone": "UTC"},
                "quality_policy": {
                    "required_fields": required_fields,
                    "dedupe_mode": dedupe_mode,
                    "max_missing_ratio": max_missing_ratio,
                },
                "output_policy": {
                    "writer": "sqlite",
                    "keep_raw": True,
                    "keep_normalized": True,
                    "max_output_records": max_output_records,
                    "update_mode": "replace",
                },
                "run_policy": {
                    "enable_cache": False,
                },
            }
        )

    def build_raw_record(self, *, index: int, title: str, published_at: str, company: str | None = None) -> RawRecord:
        payload: dict[str, str] = {
            "title": title,
            "published_at": published_at,
            "url": f"https://example.com/jobs/{index}",
            "summary": "Backend",
            "location": "Shanghai",
            "category": "Engineering",
        }
        if company is not None:
            payload["company"] = company
        return RawRecord(
            task_id="job-quality-001",
            domain="jobs",
            source_id="test_jobs_source",
            source_type="public_jobs_board",
            source_label="Test Jobs",
            fetched_at=f"2026-03-20T10:00:0{index}+00:00",
            request_url=f"https://example.com/jobs?page={index}",
            http_status=200,
            content_hash=f"hash-{index}",
            raw_payload=payload,
        )

    def test_run_task_applies_dedupe_and_quality_filtering(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            service = TaskService(base_dir=Path(temp_dir))
            service.source_registry.list_for_task = lambda task: []
            service._collect_raw_records = lambda task, selected_sources: [
                self.build_raw_record(index=1, title="Python Engineer", published_at="2026-03-18", company="Acme"),
                self.build_raw_record(index=2, title="Python Engineer", published_at="2026-03-18", company="Acme"),
                self.build_raw_record(index=3, title="Data Engineer", published_at="2026-03-17", company=None),
            ]
            result = service.run_task(self.build_task(required_fields=["title", "company", "published_at"], max_missing_ratio=0.0))

            quality_report = result["quality_report"]
            self.assertEqual(quality_report["normalized_count"], 3)
            self.assertEqual(quality_report["deduped_count"], 2)
            self.assertEqual(quality_report["output_count"], 1)
            self.assertEqual(quality_report["dropped_by_quality"], 1)
            self.assertEqual(quality_report["missing_field_stats"], {"company": 1})
            self.assertIn("去重阶段移除了 1 条重复记录。", quality_report["warnings"])
            self.assertIn("质量规则剔除了 1 条记录。", quality_report["warnings"])

            with gzip.open(result["artifacts"]["normalized_file"], "rt", encoding="utf-8") as handle:
                normalized_rows = [json.loads(line) for line in handle]
            self.assertEqual(len(normalized_rows), 3)
            flagged_row = next(row for row in normalized_rows if row["title"] == "Data Engineer")
            self.assertIn("missing_required:company", flagged_row["quality_flags"])

            connection = sqlite3.connect(result["artifacts"]["sqlite_file"])
            try:
                output_count = connection.execute("SELECT COUNT(*) FROM core_jobs_postings").fetchone()[0]
            finally:
                connection.close()
            self.assertEqual(output_count, 1)

    def test_normalization_uses_record_level_matched_topics_when_present(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            service = TaskService(base_dir=Path(temp_dir))
            service.source_registry.list_for_task = lambda task: []
            service._collect_raw_records = lambda task, selected_sources: [
                RawRecord(
                    task_id="job-quality-001",
                    domain="jobs",
                    source_id="test_jobs_source",
                    source_type="public_jobs_board",
                    source_label="Test Jobs",
                    fetched_at="2026-03-20T10:00:00+00:00",
                    request_url="https://example.com/jobs?page=1",
                    http_status=200,
                    content_hash="hash-matched-topics",
                    raw_payload={
                        "title": "Python Engineer",
                        "published_at": "2026-03-18",
                        "url": "https://example.com/jobs/1",
                        "summary": "Backend platform work",
                        "company": "Acme",
                        "matched_topics": ["backend"],
                    },
                ),
            ]
            result = service.run_task(
                self.build_task(
                    required_fields=["title", "company"],
                    max_missing_ratio=0.0,
                    topic_scope=["backend", "devops"],
                )
            )

            with gzip.open(result["artifacts"]["normalized_file"], "rt", encoding="utf-8") as handle:
                normalized_row = json.loads(next(handle))

            self.assertEqual(normalized_row["topic_tags"], ["backend"])
            self.assertEqual(normalized_row["extra"]["matched_topics"], ["backend"])

    def test_quality_flags_are_retained_when_missing_ratio_is_allowed(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            service = TaskService(base_dir=Path(temp_dir))
            service.source_registry.list_for_task = lambda task: []
            service._collect_raw_records = lambda task, selected_sources: [
                self.build_raw_record(index=1, title="Python Engineer", published_at="2026-03-18", company=None),
            ]
            result = service.run_task(self.build_task(required_fields=["title", "company"], max_missing_ratio=0.5, dedupe_mode="none"))

            quality_report = result["quality_report"]
            self.assertEqual(quality_report["normalized_count"], 1)
            self.assertEqual(quality_report["deduped_count"], 1)
            self.assertEqual(quality_report["output_count"], 1)
            self.assertEqual(quality_report["dropped_by_quality"], 0)
            self.assertEqual(quality_report["missing_field_stats"], {"company": 1})

            with gzip.open(result["artifacts"]["normalized_file"], "rt", encoding="utf-8") as handle:
                normalized_row = json.loads(next(handle))
            self.assertIn("missing_required:company", normalized_row["quality_flags"])

            connection = sqlite3.connect(result["artifacts"]["sqlite_file"])
            try:
                output_count = connection.execute("SELECT COUNT(*) FROM core_jobs_postings").fetchone()[0]
            finally:
                connection.close()
            self.assertEqual(output_count, 1)


if __name__ == "__main__":
    unittest.main()
