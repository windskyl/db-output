from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

from app.connectors.qianxin_news import QianxinNewsConnector
from app.domain_plugins.registry import DomainRegistry
from app.models.records import NormalizedRecord, RawRecord, RunArtifacts
from app.models.task_spec import TaskSpec
from app.storage.normalized_store import NormalizedStore
from app.storage.paths import TaskPaths
from app.storage.raw_store import RawStore
from app.writers.sqlite_writer import SQLiteWriter


class TaskService:
    def __init__(self, base_dir: Path) -> None:
        self.base_dir = base_dir
        self.registry = DomainRegistry()
        self.raw_store = RawStore()
        self.normalized_store = NormalizedStore()
        self.writer = SQLiteWriter()
        self.qianxin_news_connector = QianxinNewsConnector()

    def validate_task(self, task: TaskSpec) -> dict:
        plugin = self.registry.get(task.domain)
        plugin.validate_task(task)
        return {
            "ok": True,
            "task": task.to_summary(),
            "supported_domains": self.registry.names(),
        }

    def run_task(self, task: TaskSpec) -> dict:
        plugin = self.registry.get(task.domain)
        plugin.validate_task(task)

        paths = TaskPaths(base_dir=self.base_dir, domain=task.domain, task_id=task.task_id)
        paths.ensure()

        raw_records = self._collect_raw_records(task)
        normalized_records = self._normalize_records(task, raw_records)

        if task.output_policy.keep_raw:
            self.raw_store.write(paths.raw_file, raw_records)
        if task.output_policy.keep_normalized:
            self.normalized_store.write(paths.normalized_file, normalized_records)

        quality_report = {
            "task_id": task.task_id,
            "domain": task.domain,
            "raw_count": len(raw_records),
            "normalized_count": len(normalized_records),
            "deduped_count": len(normalized_records),
            "output_count": len(normalized_records),
            "dropped_by_relevance": 0,
            "dropped_by_quality": 0,
            "missing_field_stats": {},
            "source_stats": self._build_source_stats(raw_records),
            "error_stats": {},
            "warnings": self._build_warnings(task, raw_records),
        }
        run_summary = {
            "task_id": task.task_id,
            "domain": task.domain,
            "scenario_template": task.scenario_template,
            "status": "success",
            "raw_count": len(raw_records),
            "normalized_count": len(normalized_records),
            "output_count": len(normalized_records),
            "quality_report": quality_report,
        }
        artifacts = RunArtifacts(
            task_id=task.task_id,
            domain=task.domain,
            raw_file=str(paths.raw_file),
            normalized_file=str(paths.normalized_file),
            sqlite_file=str(paths.sqlite_file),
            quality_report_file=str(paths.quality_report_file),
            run_report_file=str(paths.run_report_file),
        )
        self.writer.write(run_summary, normalized_records, artifacts)
        paths.quality_report_file.write_text(json.dumps(quality_report, ensure_ascii=False, indent=2), encoding="utf-8")
        paths.run_report_file.write_text(
            json.dumps(
                {
                    "task": task.to_summary(),
                    "artifacts": {
                        "raw_file": artifacts.raw_file,
                        "normalized_file": artifacts.normalized_file,
                        "sqlite_file": artifacts.sqlite_file,
                        "quality_report_file": artifacts.quality_report_file,
                        "run_report_file": artifacts.run_report_file,
                    },
                    "status": "success",
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        return {
            "status": "success",
            "artifacts": {
                "raw_file": artifacts.raw_file,
                "normalized_file": artifacts.normalized_file,
                "sqlite_file": artifacts.sqlite_file,
                "quality_report_file": artifacts.quality_report_file,
                "run_report_file": artifacts.run_report_file,
            },
            "quality_report": quality_report,
        }

    def _collect_raw_records(self, task: TaskSpec) -> list[RawRecord]:
        if task.domain == "company_intel" and self._is_qianxin_task(task):
            records = self.qianxin_news_connector.collect(task)
            if records:
                return records
        return [self._build_seed_raw_record(task)]

    def _normalize_records(self, task: TaskSpec, raw_records: list[RawRecord]) -> list[NormalizedRecord]:
        normalized: list[NormalizedRecord] = []
        for index, raw in enumerate(raw_records, start=1):
            payload = raw.raw_payload
            title = str(payload.get("title", "") or f"Seed record for {task.domain}")
            summary = str(payload.get("summary", ""))
            source_url = str(payload.get("url", raw.request_url))
            published_at = str(payload.get("published_at", task.time_range.end))
            primary_entity = self._primary_entity(task)
            record_id = f"{task.task_id}-{index}"
            normalized.append(
                NormalizedRecord(
                    task_id=task.task_id,
                    domain=task.domain,
                    record_id=record_id,
                    dedupe_key=f"{raw.source_id}:{published_at}:{title}",
                    source_id=raw.source_id,
                    source_url=source_url,
                    published_at=published_at,
                    collected_at=raw.fetched_at,
                    primary_entity=primary_entity,
                    entity_tags=[primary_entity],
                    topic_tags=list(task.topic_scope),
                    title=title,
                    content_text=summary or "Generated from the validated task spec so the pipeline can be tested locally.",
                    relevance_score=max(task.relevance_policy.min_relevance_score, 0.7),
                    extra={
                        "scenario_template": task.scenario_template,
                        "request_url": raw.request_url,
                    },
                )
            )
        return normalized

    def _build_source_stats(self, raw_records: list[RawRecord]) -> dict[str, int]:
        stats: dict[str, int] = {}
        for record in raw_records:
            stats[record.source_id] = stats.get(record.source_id, 0) + 1
        return stats

    def _build_warnings(self, task: TaskSpec, raw_records: list[RawRecord]) -> list[str]:
        if task.domain == "company_intel" and self._is_qianxin_task(task) and raw_records and raw_records[0].source_id != "seed":
            return []
        return ["This run used the local seed fallback because no live connector matched the task."]

    def _is_qianxin_task(self, task: TaskSpec) -> bool:
        return any("奇安信" in str(target.get("value", "")) for target in task.targets)

    def _primary_entity(self, task: TaskSpec) -> str:
        primary_target = task.targets[0].get("value") or task.targets[0].get("type") or "unknown"
        return str(primary_target)

    def _build_seed_raw_record(self, task: TaskSpec) -> RawRecord:
        seed_payload = {
            "task": task.to_summary(),
            "targets": task.targets,
            "topic_scope": task.topic_scope,
        }
        seed_json = json.dumps(seed_payload, ensure_ascii=False, sort_keys=True)
        return RawRecord(
            task_id=task.task_id,
            domain=task.domain,
            source_id="seed",
            fetched_at=datetime.now(UTC).isoformat(),
            request_url="local://task-seed",
            http_status=200,
            content_hash=hashlib.sha256(seed_json.encode("utf-8")).hexdigest(),
            raw_payload=seed_payload,
        )
