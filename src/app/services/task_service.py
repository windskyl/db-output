from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.connectors.json_api import JsonApiConnector
from app.connectors.regex_html_list import RegexHtmlListConnector
from app.connectors.rss_feed import RssFeedConnector
from app.domain_plugins.registry import DomainRegistry
from app.fetching.client import FetchClient
from app.fetching.limiter import RateLimiter
from app.fetching.scheduler import Scheduler
from app.models.records import NormalizedRecord, RawRecord, RunArtifacts
from app.models.task_spec import TaskSpec, TaskValidationError
from app.sources.registry import SourceRegistry
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
        self.source_registry = SourceRegistry(config_root=Path(__file__).resolve().parents[3] / "configs" / "sources")
        self.rate_limiter = RateLimiter()
        self.fetch_client = FetchClient(rate_limiter=self.rate_limiter)
        self.scheduler = Scheduler(fetch_client=self.fetch_client)
        self.connectors = {
            "regex_html_list": RegexHtmlListConnector(scheduler=self.scheduler),
            "rss_feed": RssFeedConnector(scheduler=self.scheduler),
            "json_api": JsonApiConnector(scheduler=self.scheduler),
        }

    def validate_task(self, task: TaskSpec) -> dict:
        plugin = self.registry.get(task.domain)
        plugin.validate_task(task)
        selected_sources = self.source_registry.list_for_task(task)
        return {
            "ok": True,
            "task": task.to_summary(),
            "selected_sources": [profile.source_id for profile in selected_sources],
            "selected_source_details": [profile.to_summary() for profile in selected_sources],
            "supported_domains": self.registry.names(),
        }

    def list_sources(self, domain: str | None = None, channel: str | None = None, task: TaskSpec | None = None) -> dict:
        profiles = self.source_registry.list_profiles(domain=domain, channel=channel)
        result: dict[str, object] = {
            "total": len(profiles),
            "sources": [profile.to_summary() for profile in profiles],
        }
        if task is not None:
            selected = self.source_registry.list_for_task(task)
            result["task"] = task.to_summary()
            result["selected_sources"] = [profile.to_summary() for profile in selected]
        return result

    def list_task_runs(self, domain: str | None = None, status: str | None = None, limit: int | None = None) -> dict:
        items = self._load_task_runs(domain=domain)
        if status is not None:
            items = [item for item in items if item["status"] == status]

        items.sort(key=lambda item: str(item["updated_at"]), reverse=True)
        total = len(items)
        if limit is not None:
            items = items[:limit]

        return {
            "total": total,
            "returned": len(items),
            "tasks": [
                {
                    "task_id": item["task"]["task_id"],
                    "domain": item["task"]["domain"],
                    "scenario_template": item["task"]["scenario_template"],
                    "status": item["status"],
                    "created_at": item["created_at"],
                    "updated_at": item["updated_at"],
                    "artifacts_dir": item["artifacts_dir"],
                    "output_count": item["quality_report"].get("output_count", 0),
                    "warning_count": len(item["quality_report"].get("warnings", [])),
                }
                for item in items
            ],
        }

    def get_task_status(self, task_id: str, domain: str | None = None) -> dict:
        item = self._resolve_task_run(task_id=task_id, domain=domain)
        return {
            "task": item["task"],
            "status": item["status"],
            "created_at": item["created_at"],
            "updated_at": item["updated_at"],
            "artifacts_dir": item["artifacts_dir"],
            "artifacts": item["artifacts"],
            "selected_sources": item["selected_sources"],
            "quality_report": item["quality_report"],
        }

    def get_task_report(self, task_id: str, domain: str | None = None, kind: str = "all") -> dict:
        item = self._resolve_task_run(task_id=task_id, domain=domain)
        report: dict[str, Any] = {
            "task": item["task"],
            "status": item["status"],
            "created_at": item["created_at"],
            "updated_at": item["updated_at"],
            "files": {
                "run_report_file": item["artifacts"]["run_report_file"],
                "quality_report_file": item["artifacts"]["quality_report_file"],
            },
        }
        if kind in {"run", "all"}:
            report["run_report"] = item["run_report"]
        if kind in {"quality", "all"}:
            report["quality_report"] = item["quality_report"]
        return report

    def run_task(self, task: TaskSpec) -> dict:
        plugin = self.registry.get(task.domain)
        plugin.validate_task(task)

        paths = TaskPaths(base_dir=self.base_dir, domain=task.domain, task_id=task.task_id)
        paths.ensure()

        self.fetch_client.begin_session(task.task_id)
        selected_sources = self.source_registry.list_for_task(task)
        raw_records = self._collect_raw_records(task, selected_sources)
        normalized_records = self._normalize_records(task, raw_records)
        fetch_stats = self.fetch_client.build_stats()

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
            "fetch_stats": fetch_stats,
            "error_stats": fetch_stats["error_types"],
            "warnings": self._build_warnings(raw_records, fetch_stats),
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
                    "selected_sources": [profile.to_summary() for profile in selected_sources],
                    "artifacts": {
                        "raw_file": artifacts.raw_file,
                        "normalized_file": artifacts.normalized_file,
                        "sqlite_file": artifacts.sqlite_file,
                        "quality_report_file": artifacts.quality_report_file,
                        "run_report_file": artifacts.run_report_file,
                    },
                    "status": "success",
                    "created_at": artifacts.created_at,
                    "quality_summary": {
                        "raw_count": quality_report["raw_count"],
                        "normalized_count": quality_report["normalized_count"],
                        "output_count": quality_report["output_count"],
                        "warning_count": len(quality_report["warnings"]),
                        "fetch_request_count": fetch_stats["total_requests"],
                        "fetch_retry_count": fetch_stats["total_retries"],
                        "fetch_failure_count": fetch_stats["failed_requests"],
                        "source_stats": quality_report["source_stats"],
                    },
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        return {
            "status": "success",
            "created_at": artifacts.created_at,
            "selected_sources": [profile.to_summary() for profile in selected_sources],
            "artifacts": {
                "raw_file": artifacts.raw_file,
                "normalized_file": artifacts.normalized_file,
                "sqlite_file": artifacts.sqlite_file,
                "quality_report_file": artifacts.quality_report_file,
                "run_report_file": artifacts.run_report_file,
            },
            "quality_report": quality_report,
        }

    def _collect_raw_records(self, task: TaskSpec, selected_sources: Iterable[Any]) -> list[RawRecord]:
        records: list[RawRecord] = []
        for profile in selected_sources:
            connector = self.connectors[profile.connector_kind]
            records.extend(connector.collect(profile, task))
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
            primary_entity = self._primary_entity(task, payload)
            source_tag = str(payload.get("tag", payload.get("category", "")))
            record_id = f"{task.task_id}-{raw.source_id}-{index}"
            extra = {
                "scenario_template": task.scenario_template,
                "request_url": raw.request_url,
            }
            for key in ("source_item_id", "company", "location", "category", "guid", "author"):
                if key in payload:
                    extra[key] = payload[key]
            if task.domain == "finance":
                for key, value in payload.items():
                    if key in {"title", "summary", "published_at", "url", "tag", "category"}:
                        continue
                    if value is None or isinstance(value, (dict, list)):
                        continue
                    extra[key] = value
            normalized.append(
                NormalizedRecord(
                    task_id=task.task_id,
                    domain=task.domain,
                    record_id=record_id,
                    dedupe_key=f"{raw.source_id}:{published_at}:{title}",
                    source_id=raw.source_id,
                    source_type=raw.source_type,
                    source_label=raw.source_label,
                    source_tag=source_tag,
                    source_url=source_url,
                    published_at=published_at,
                    collected_at=raw.fetched_at,
                    primary_entity=primary_entity,
                    entity_tags=[primary_entity],
                    topic_tags=list(task.topic_scope),
                    title=title,
                    content_text=summary or "Generated from the validated task spec so the pipeline can be tested locally.",
                    relevance_score=max(task.relevance_policy.min_relevance_score, 0.7),
                    extra=extra,
                )
            )
        return normalized

    def _build_source_stats(self, raw_records: list[RawRecord]) -> dict[str, int]:
        stats: dict[str, int] = {}
        for record in raw_records:
            stats[record.source_id] = stats.get(record.source_id, 0) + 1
        return stats

    def _build_warnings(self, raw_records: list[RawRecord], fetch_stats: dict[str, Any]) -> list[str]:
        warnings: list[str] = []
        if raw_records and raw_records[0].source_id == "seed":
            warnings.append("This run used the local seed fallback because no live source profile produced records.")
        if fetch_stats.get("total_retries", 0) > 0:
            warnings.append(f"Fetch retries were used for {fetch_stats['total_retries']} attempt(s).")
        return warnings

    def _primary_entity(self, task: TaskSpec, payload: dict) -> str:
        if task.domain == "jobs" and payload.get("company"):
            return str(payload["company"])
        if task.domain == "finance" and payload.get("symbol"):
            return str(payload["symbol"])
        primary_target = task.targets[0].get("value") or task.targets[0].get("type") or "unknown"
        return str(primary_target)

    def _build_seed_raw_record(self, task: TaskSpec) -> RawRecord:
        seed_payload = {
            "task": task.to_summary(),
            "targets": task.targets,
            "topic_scope": task.topic_scope,
            "published_at": task.time_range.end,
        }
        seed_json = json.dumps(seed_payload, ensure_ascii=False, sort_keys=True)
        return RawRecord(
            task_id=task.task_id,
            domain=task.domain,
            source_id="seed",
            source_type="seed",
            source_label="Local Seed",
            fetched_at=datetime.now(UTC).isoformat(),
            request_url="local://task-seed",
            http_status=200,
            content_hash=hashlib.sha256(seed_json.encode("utf-8")).hexdigest(),
            raw_payload=seed_payload,
        )

    def _load_task_runs(self, domain: str | None = None) -> list[dict[str, Any]]:
        artifact_root = self.base_dir / "artifacts"
        if domain is not None:
            report_paths = sorted((artifact_root / domain).glob("*/run_report.json"))
        else:
            report_paths = sorted(artifact_root.glob("*/*/run_report.json"))
        return [self._load_task_run(path) for path in report_paths]

    def _load_task_run(self, run_report_path: Path) -> dict[str, Any]:
        run_report = self._read_json_file(run_report_path)
        artifacts = dict(run_report.get("artifacts", {}))
        artifacts.setdefault("run_report_file", str(run_report_path))
        quality_report_path = Path(str(artifacts.get("quality_report_file", run_report_path.with_name("quality_report.json"))))
        artifacts.setdefault("quality_report_file", str(quality_report_path))
        quality_report = self._read_json_file(quality_report_path) if quality_report_path.exists() else {}
        run_report_stat = run_report_path.stat()
        quality_report_stat = quality_report_path.stat() if quality_report_path.exists() else run_report_stat
        created_at = str(run_report.get("created_at") or self._timestamp_to_iso(run_report_stat.st_mtime))
        updated_at = self._timestamp_to_iso(max(run_report_stat.st_mtime, quality_report_stat.st_mtime))
        return {
            "task": dict(run_report.get("task", {})),
            "status": str(run_report.get("status", "unknown")),
            "created_at": created_at,
            "updated_at": updated_at,
            "artifacts_dir": str(run_report_path.parent),
            "artifacts": artifacts,
            "selected_sources": list(run_report.get("selected_sources", [])),
            "run_report": run_report,
            "quality_report": quality_report,
        }

    def _resolve_task_run(self, task_id: str, domain: str | None = None) -> dict[str, Any]:
        matches = [item for item in self._load_task_runs(domain=domain) if item["task"].get("task_id") == task_id]
        if not matches:
            raise FileNotFoundError(f"No run report found for task_id={task_id}")
        if len(matches) > 1:
            raise TaskValidationError(f"Ambiguous task_id={task_id}; specify --domain to disambiguate.")
        return matches[0]

    def _read_json_file(self, path: Path) -> dict[str, Any]:
        return json.loads(path.read_text(encoding="utf-8"))

    def _timestamp_to_iso(self, timestamp: float) -> str:
        return datetime.fromtimestamp(timestamp, tz=UTC).isoformat()
