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
        if task.run_policy.enable_cache:
            paths.cache_dir.mkdir(parents=True, exist_ok=True)

        self.fetch_client.begin_session(task.task_id, cache_dir=paths.cache_dir if task.run_policy.enable_cache else None)
        selected_sources = self.source_registry.list_for_task(task)
        raw_records = self._collect_raw_records(task, selected_sources)
        normalized_records = self._normalize_records(task, raw_records)
        output_records, quality_stats = self._apply_quality_policy(task, normalized_records)
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
            "deduped_count": quality_stats["deduped_count"],
            "output_count": len(output_records),
            "dropped_by_relevance": 0,
            "dropped_by_quality": quality_stats["dropped_by_quality"],
            "missing_field_stats": quality_stats["missing_field_stats"],
            "source_stats": self._build_source_stats(raw_records),
            "fetch_stats": fetch_stats,
            "error_stats": fetch_stats["error_types"],
            "warnings": self._build_warnings(raw_records, fetch_stats, quality_stats),
        }
        run_summary = {
            "task_id": task.task_id,
            "domain": task.domain,
            "scenario_template": task.scenario_template,
            "status": "success",
            "raw_count": len(raw_records),
            "normalized_count": len(normalized_records),
            "output_count": len(output_records),
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
            cache_dir=str(paths.cache_dir) if task.run_policy.enable_cache else None,
        )
        self.writer.write(run_summary, output_records, artifacts)
        report_summary = self._build_domain_report_summary(task.domain, Path(artifacts.sqlite_file))
        if report_summary:
            quality_report["domain_summary"] = report_summary
            run_summary["quality_report"]["domain_summary"] = report_summary
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
                        "cache_dir": artifacts.cache_dir,
                    },
                    "status": "success",
                    "created_at": artifacts.created_at,
                    "quality_summary": {
                        "raw_count": quality_report["raw_count"],
                        "normalized_count": quality_report["normalized_count"],
                        "deduped_count": quality_report["deduped_count"],
                        "output_count": quality_report["output_count"],
                        "warning_count": len(quality_report["warnings"]),
                        "fetch_request_count": fetch_stats["total_requests"],
                        "fetch_network_request_count": fetch_stats["network_requests"],
                        "fetch_cache_hit_count": fetch_stats["cache_hits"],
                        "fetch_cache_miss_count": fetch_stats["cache_misses"],
                        "fetch_retry_count": fetch_stats["total_retries"],
                        "fetch_failure_count": fetch_stats["failed_requests"],
                        "source_stats": quality_report["source_stats"],
                        "domain_summary": quality_report.get("domain_summary"),
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
                "cache_dir": artifacts.cache_dir,
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
            topic_tags = self._resolve_record_topics(task, payload)
            record_id = f"{task.task_id}-{raw.source_id}-{index}"
            extra = {
                "scenario_template": task.scenario_template,
                "request_url": raw.request_url,
            }
            for key in ("source_item_id", "company", "location", "category", "guid", "author"):
                if key in payload:
                    extra[key] = payload[key]
            if "matched_topics" in payload:
                extra["matched_topics"] = topic_tags
            if task.domain == "finance":
                for key, value in payload.items():
                    if key in {"title", "summary", "published_at", "url", "tag", "category", "matched_topics"}:
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
                    topic_tags=topic_tags,
                    title=title,
                    content_text=summary or "Generated from the validated task spec so the pipeline can be tested locally.",
                    relevance_score=max(task.relevance_policy.min_relevance_score, 0.7),
                    extra=extra,
                )
            )
        return normalized

    def _apply_quality_policy(self, task: TaskSpec, records: list[NormalizedRecord]) -> tuple[list[NormalizedRecord], dict[str, Any]]:
        deduped_records, duplicate_count = self._dedupe_records(task, records)
        quality_filtered_records, missing_field_stats, dropped_by_quality = self._filter_quality_records(task, deduped_records)
        output_records = quality_filtered_records[: task.output_policy.max_output_records]
        truncated_count = max(0, len(quality_filtered_records) - len(output_records))
        return output_records, {
            "deduped_count": len(deduped_records),
            "duplicate_count": duplicate_count,
            "dropped_by_quality": dropped_by_quality,
            "missing_field_stats": missing_field_stats,
            "truncated_count": truncated_count,
        }

    def _dedupe_records(self, task: TaskSpec, records: list[NormalizedRecord]) -> tuple[list[NormalizedRecord], int]:
        if task.quality_policy.dedupe_mode == "none":
            return list(records), 0
        seen: set[str] = set()
        deduped: list[NormalizedRecord] = []
        duplicates = 0
        for record in records:
            key = record.dedupe_key or record.record_id
            if key in seen:
                duplicates += 1
                continue
            seen.add(key)
            deduped.append(record)
        return deduped, duplicates

    def _filter_quality_records(self, task: TaskSpec, records: list[NormalizedRecord]) -> tuple[list[NormalizedRecord], dict[str, int], int]:
        required_fields = list(task.quality_policy.required_fields)
        if not required_fields:
            return list(records), {}, 0

        missing_field_stats: dict[str, int] = {field: 0 for field in required_fields}
        kept: list[NormalizedRecord] = []
        dropped = 0

        for record in records:
            missing_fields = [field for field in required_fields if self._is_missing_record_field(record, field)]
            if missing_fields:
                for field in missing_fields:
                    missing_field_stats[field] += 1
                for field in missing_fields:
                    flag = f"missing_required:{field}"
                    if flag not in record.quality_flags:
                        record.quality_flags.append(flag)
            missing_ratio = len(missing_fields) / len(required_fields)
            if missing_ratio > task.quality_policy.max_missing_ratio:
                dropped += 1
                continue
            kept.append(record)

        return kept, {field: count for field, count in missing_field_stats.items() if count > 0}, dropped

    def _is_missing_record_field(self, record: NormalizedRecord, field_name: str) -> bool:
        value = self._record_field_value(record, field_name)
        if value is None:
            return True
        if isinstance(value, str):
            return not value.strip()
        if isinstance(value, (list, dict, tuple, set)):
            return len(value) == 0
        return False

    def _record_field_value(self, record: NormalizedRecord, field_name: str) -> Any:
        if hasattr(record, field_name):
            return getattr(record, field_name)
        return record.extra.get(field_name)

    def _build_source_stats(self, raw_records: list[RawRecord]) -> dict[str, int]:
        stats: dict[str, int] = {}
        for record in raw_records:
            stats[record.source_id] = stats.get(record.source_id, 0) + 1
        return stats

    def _build_domain_report_summary(self, domain: str, sqlite_path: Path) -> dict[str, Any] | None:
        if not sqlite_path.exists():
            return None
        import sqlite3

        connection = sqlite3.connect(sqlite_path)
        try:
            if domain == "public_sentiment":
                return self._build_public_sentiment_domain_summary(connection)
            if domain == "jobs":
                return self._build_jobs_domain_summary(connection)
            if domain == "company_intel":
                return self._build_company_intel_domain_summary(connection)
            if domain == "finance":
                return self._build_finance_domain_summary(connection)
            return None
        finally:
            connection.close()

    def _build_public_sentiment_domain_summary(self, connection: Any) -> dict[str, Any] | None:
        rows = connection.execute(
            """
            SELECT topic_name, post_count, positive_count, neutral_count, negative_count,
                   average_sentiment_score, dominant_sentiment_label,
                   most_positive_title, most_negative_title, most_neutral_title, extra_json
            FROM core_sentiment_topics
            ORDER BY post_count DESC, topic_name ASC
            """
        ).fetchall()
        if not rows:
            return None
        topics = []
        for row in rows:
            extra = json.loads(str(row[10])) if row[10] else {}
            topics.append(
                {
                    "topic_name": row[0],
                    "post_count": row[1],
                    "positive_count": row[2],
                    "neutral_count": row[3],
                    "negative_count": row[4],
                    "average_sentiment_score": row[5],
                    "dominant_sentiment_label": row[6],
                    "most_positive_title": row[7],
                    "most_negative_title": row[8],
                    "most_neutral_title": row[9],
                    "positive_cue_counts": extra.get("positive_cue_counts", []),
                    "negative_cue_counts": extra.get("negative_cue_counts", []),
                }
            )
        total_posts = sum(topic["post_count"] for topic in topics)
        top_topic = topics[0]["topic_name"] if topics else None
        return {
            "kind": "public_sentiment",
            "topic_count": len(topics),
            "topics": topics,
            "cards": [
                {"label": "Topics", "value": len(topics)},
                {"label": "Posts", "value": total_posts},
            ],
            "narrative": f"Captured {total_posts} sentiment posts across {len(topics)} topic buckets. The busiest topic is {top_topic or 'N/A'}.",
        }

    def _build_jobs_domain_summary(self, connection: Any) -> dict[str, Any] | None:
        posting_count = int(connection.execute("SELECT COUNT(*) FROM core_jobs_postings").fetchone()[0])
        if posting_count == 0:
            return None
        company_rows = connection.execute(
            "SELECT primary_entity, COUNT(*) FROM core_jobs_postings GROUP BY primary_entity ORDER BY COUNT(*) DESC, primary_entity ASC LIMIT 5"
        ).fetchall()
        skill_rows = connection.execute(
            "SELECT skill_name, COUNT(*) FROM core_jobs_skills GROUP BY skill_name ORDER BY COUNT(*) DESC, skill_name ASC LIMIT 8"
        ).fetchall()
        company_count = int(connection.execute("SELECT COUNT(DISTINCT primary_entity) FROM core_jobs_postings").fetchone()[0])
        skill_count = int(connection.execute("SELECT COUNT(*) FROM core_jobs_skills").fetchone()[0])
        top_company = company_rows[0][0] if company_rows else None
        top_skill = skill_rows[0][0] if skill_rows else None
        return {
            "kind": "jobs",
            "cards": [
                {"label": "Postings", "value": posting_count},
                {"label": "Companies", "value": company_count},
                {"label": "Skill rows", "value": skill_count},
            ],
            "sections": [
                {
                    "title": "Top companies",
                    "items": [{"label": row[0], "value": row[1]} for row in company_rows],
                },
                {
                    "title": "Top skills",
                    "items": [{"label": row[0], "value": row[1]} for row in skill_rows],
                },
            ],
            "narrative": f"Found {posting_count} job postings from {company_count} companies. The most visible company is {top_company or 'N/A'} and the most frequent skill is {top_skill or 'N/A'}.",
        }

    def _build_company_intel_domain_summary(self, connection: Any) -> dict[str, Any] | None:
        event_count = int(connection.execute("SELECT COUNT(*) FROM core_company_events").fetchone()[0])
        if event_count == 0:
            return None
        profile_rows = connection.execute(
            "SELECT company_name, evidence_count FROM core_company_profiles ORDER BY evidence_count DESC, company_name ASC LIMIT 5"
        ).fetchall()
        project_rows = connection.execute(
            "SELECT project_name, mention_count FROM core_company_projects ORDER BY mention_count DESC, project_name ASC LIMIT 8"
        ).fetchall()
        profile_count = int(connection.execute("SELECT COUNT(*) FROM core_company_profiles").fetchone()[0])
        project_count = int(connection.execute("SELECT COUNT(*) FROM core_company_projects").fetchone()[0])
        top_company = profile_rows[0][0] if profile_rows else None
        top_project = project_rows[0][0] if project_rows else None
        return {
            "kind": "company_intel",
            "cards": [
                {"label": "Events", "value": event_count},
                {"label": "Profiles", "value": profile_count},
                {"label": "Projects", "value": project_count},
            ],
            "sections": [
                {
                    "title": "Tracked companies",
                    "items": [{"label": row[0], "value": row[1]} for row in profile_rows],
                },
                {
                    "title": "Top projects",
                    "items": [{"label": row[0], "value": row[1]} for row in project_rows],
                },
            ],
            "narrative": f"Captured {event_count} company-intel events. The strongest profile is {top_company or 'N/A'} and the leading project label is {top_project or 'N/A'}.",
        }

    def _build_finance_domain_summary(self, connection: Any) -> dict[str, Any] | None:
        event_count = int(connection.execute("SELECT COUNT(*) FROM core_finance_events").fetchone()[0])
        if event_count == 0:
            return None
        instrument_rows = connection.execute(
            "SELECT symbol, instrument_name FROM core_finance_instruments ORDER BY symbol ASC LIMIT 5"
        ).fetchall()
        metric_rows = connection.execute(
            "SELECT metric_name, COUNT(*) FROM core_finance_metrics GROUP BY metric_name ORDER BY COUNT(*) DESC, metric_name ASC LIMIT 8"
        ).fetchall()
        instrument_count = int(connection.execute("SELECT COUNT(*) FROM core_finance_instruments").fetchone()[0])
        metric_count = int(connection.execute("SELECT COUNT(*) FROM core_finance_metrics").fetchone()[0])
        top_instrument = instrument_rows[0][0] if instrument_rows else None
        top_metric = metric_rows[0][0] if metric_rows else None
        return {
            "kind": "finance",
            "cards": [
                {"label": "Events", "value": event_count},
                {"label": "Instruments", "value": instrument_count},
                {"label": "Metrics", "value": metric_count},
            ],
            "sections": [
                {
                    "title": "Tracked instruments",
                    "items": [{"label": row[0], "value": row[1] or row[0]} for row in instrument_rows],
                },
                {
                    "title": "Top metrics",
                    "items": [{"label": row[0], "value": row[1]} for row in metric_rows],
                },
            ],
            "narrative": f"Captured {event_count} finance events across {instrument_count} instruments. The leading instrument is {top_instrument or 'N/A'} and the top metric is {top_metric or 'N/A'}.",
        }
    def _build_warnings(self, raw_records: list[RawRecord], fetch_stats: dict[str, Any], quality_stats: dict[str, Any]) -> list[str]:
        warnings: list[str] = []
        if raw_records and raw_records[0].source_id == "seed":
            warnings.append("This run used the local seed fallback because no live source profile produced records.")
        if fetch_stats.get("cache_hits", 0) > 0:
            warnings.append(f"Fetch cache served {fetch_stats['cache_hits']} request(s).")
        if fetch_stats.get("total_retries", 0) > 0:
            warnings.append(f"Fetch retries were used for {fetch_stats['total_retries']} attempt(s).")
        if quality_stats.get("duplicate_count", 0) > 0:
            warnings.append(f"Deduplication removed {quality_stats['duplicate_count']} duplicate record(s).")
        if quality_stats.get("dropped_by_quality", 0) > 0:
            warnings.append(f"Quality rules dropped {quality_stats['dropped_by_quality']} record(s).")
        if quality_stats.get("truncated_count", 0) > 0:
            warnings.append(f"Output was truncated by max_output_records and removed {quality_stats['truncated_count']} record(s).")
        return warnings

    def _primary_entity(self, task: TaskSpec, payload: dict) -> str:
        if task.domain == "jobs" and payload.get("company"):
            return str(payload["company"])
        if task.domain == "finance" and payload.get("symbol"):
            return str(payload["symbol"])
        primary_target = task.targets[0].get("value") or task.targets[0].get("type") or "unknown"
        return str(primary_target)

    def _resolve_record_topics(self, task: TaskSpec, payload: dict[str, Any]) -> list[str]:
        raw_topics = payload.get("matched_topics")
        if raw_topics is None:
            return [str(topic).strip() for topic in task.topic_scope if str(topic).strip()]

        if isinstance(raw_topics, str):
            candidates = [raw_topics]
        elif isinstance(raw_topics, (list, tuple, set)):
            candidates = [str(topic) for topic in raw_topics]
        else:
            return []

        allowed = {str(topic).strip() for topic in task.topic_scope if str(topic).strip()}
        seen: set[str] = set()
        resolved: list[str] = []
        for candidate in candidates:
            topic = candidate.strip()
            if not topic or topic in seen:
                continue
            if allowed and topic not in allowed:
                continue
            seen.add(topic)
            resolved.append(topic)
        return resolved

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