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
            "task_payload": item.get("task_payload"),
            "status": item["status"],
            "created_at": item["created_at"],
            "updated_at": item["updated_at"],
            "artifacts_dir": item["artifacts_dir"],
            "artifacts": item["artifacts"],
            "selected_sources": item["selected_sources"],
            "quality_report": item["quality_report"],
            "result_preview": item["quality_report"].get("result_preview"),
        }

    def get_task_report(self, task_id: str, domain: str | None = None, kind: str = "all") -> dict:
        item = self._resolve_task_run(task_id=task_id, domain=domain)
        report: dict[str, Any] = {
            "task": item["task"],
            "task_payload": item.get("task_payload"),
            "status": item["status"],
            "created_at": item["created_at"],
            "updated_at": item["updated_at"],
            "files": {
                "run_report_file": item["artifacts"]["run_report_file"],
                "quality_report_file": item["artifacts"]["quality_report_file"],
            },
            "result_preview": item["quality_report"].get("result_preview"),
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
        result_preview = self._build_result_preview(task.domain, Path(artifacts.sqlite_file))
        if result_preview:
            quality_report["result_preview"] = result_preview
            run_summary["quality_report"]["result_preview"] = result_preview
        paths.quality_report_file.write_text(json.dumps(quality_report, ensure_ascii=False, indent=2), encoding="utf-8")
        paths.run_report_file.write_text(
            json.dumps(
                {
                    "task": task.to_summary(),
                    "task_payload": task.to_dict(),
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
            "result_preview": quality_report.get("result_preview"),
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

    def _build_result_preview(self, domain: str, sqlite_path: Path) -> dict[str, Any] | None:
        if not sqlite_path.exists():
            return None
        import sqlite3

        connection = sqlite3.connect(sqlite_path)
        try:
            if domain == "jobs":
                return self._build_jobs_result_preview(connection)
            if domain == "company_intel":
                return self._build_company_intel_result_preview(connection)
            if domain == "finance":
                return self._build_finance_result_preview(connection)
            if domain == "public_sentiment":
                return self._build_public_sentiment_result_preview(connection)
            return None
        finally:
            connection.close()

    def _build_jobs_result_preview(self, connection: Any) -> dict[str, Any] | None:
        posting_rows = connection.execute(
            """
            SELECT primary_entity, title, published_at, extra_json
            FROM core_jobs_postings
            ORDER BY published_at DESC, record_id ASC
            LIMIT 5
            """
        ).fetchall()
        skill_rows = connection.execute(
            """
            SELECT skill_name, COUNT(*)
            FROM core_jobs_skills
            GROUP BY skill_name
            ORDER BY COUNT(*) DESC, skill_name ASC
            LIMIT 8
            """
        ).fetchall()
        if not posting_rows and not skill_rows:
            return None
        postings = []
        for company, title, published_at, extra_json in posting_rows:
            extra = json.loads(str(extra_json)) if extra_json else {}
            postings.append(
                {
                    "company": company,
                    "title": title,
                    "published_at": self._preview_date_text(published_at),
                    "location": str(extra.get("location") or "未提供"),
                }
            )
        skills = [{"skill_name": row[0], "count": int(row[1])} for row in skill_rows]
        return {
            "kind": "jobs",
            "tables": [
                self._preview_table(
                    title="最新岗位样本",
                    description="用于快速核对职位标题、公司和发布时间是否符合预期。",
                    columns=[
                        {"key": "company", "label": "公司"},
                        {"key": "title", "label": "职位标题"},
                        {"key": "published_at", "label": "发布时间"},
                        {"key": "location", "label": "地点"},
                    ],
                    rows=postings,
                ),
                self._preview_table(
                    title="热门技能",
                    description="用于快速看出当前任务中频率最高的技能要求。",
                    columns=[
                        {"key": "skill_name", "label": "技能"},
                        {"key": "count", "label": "出现次数"},
                    ],
                    rows=skills,
                ),
            ],
        }

    def _build_company_intel_result_preview(self, connection: Any) -> dict[str, Any] | None:
        event_rows = connection.execute(
            """
            SELECT primary_entity, title, published_at, topic_tags_json
            FROM core_company_events
            ORDER BY published_at DESC, record_id ASC
            LIMIT 5
            """
        ).fetchall()
        project_rows = connection.execute(
            """
            SELECT project_name, mention_count, last_published_at
            FROM core_company_projects
            ORDER BY mention_count DESC, project_name ASC
            LIMIT 8
            """
        ).fetchall()
        if not event_rows and not project_rows:
            return None
        events = []
        for company, title, published_at, topic_tags_json in event_rows:
            topics = self._preview_topic_text("company_intel", self._json_list(topic_tags_json))
            events.append(
                {
                    "company": company,
                    "title": title,
                    "published_at": self._preview_date_text(published_at),
                    "topics": topics or "未提供",
                }
            )
        projects = [
            {
                "project_name": row[0],
                "mention_count": int(row[1]),
                "last_published_at": self._preview_date_text(row[2]),
            }
            for row in project_rows
        ]
        return {
            "kind": "company_intel",
            "tables": [
                self._preview_table(
                    title="事件样本",
                    description="用于快速确认抓取的公司动态标题与主题分类。",
                    columns=[
                        {"key": "company", "label": "公司"},
                        {"key": "title", "label": "事件标题"},
                        {"key": "published_at", "label": "发布时间"},
                        {"key": "topics", "label": "主题"},
                    ],
                    rows=events,
                ),
                self._preview_table(
                    title="高频项目",
                    description="用于快速查看被多次提及的产品或项目名称。",
                    columns=[
                        {"key": "project_name", "label": "项目名称"},
                        {"key": "mention_count", "label": "提及次数"},
                        {"key": "last_published_at", "label": "最后出现"},
                    ],
                    rows=projects,
                ),
            ],
        }

    def _build_finance_result_preview(self, connection: Any) -> dict[str, Any] | None:
        metric_rows = connection.execute(
            """
            SELECT primary_entity, metric_name, metric_value, published_at
            FROM core_finance_metrics
            ORDER BY published_at DESC, primary_entity ASC, metric_name ASC
            LIMIT 8
            """
        ).fetchall()
        instrument_rows = connection.execute(
            """
            SELECT symbol, instrument_name, last_seen_at
            FROM core_finance_instruments
            ORDER BY last_seen_at DESC, symbol ASC
            LIMIT 5
            """
        ).fetchall()
        if not metric_rows and not instrument_rows:
            return None
        metrics = [
            {
                "symbol": row[0],
                "metric_name": row[1],
                "metric_value": str(row[2]),
                "published_at": self._preview_date_text(row[3]),
            }
            for row in metric_rows
        ]
        instruments = [
            {
                "symbol": row[0],
                "instrument_name": row[1] or row[0],
                "last_seen_at": self._preview_date_text(row[2]),
            }
            for row in instrument_rows
        ]
        return {
            "kind": "finance",
            "tables": [
                self._preview_table(
                    title="最新指标",
                    description="用于快速查看结果库中的标的指标值。",
                    columns=[
                        {"key": "symbol", "label": "标的"},
                        {"key": "metric_name", "label": "指标"},
                        {"key": "metric_value", "label": "数值"},
                        {"key": "published_at", "label": "日期"},
                    ],
                    rows=metrics,
                ),
                self._preview_table(
                    title="跟踪标的",
                    description="用于快速确认本次任务涉及的标的范围。",
                    columns=[
                        {"key": "symbol", "label": "代码"},
                        {"key": "instrument_name", "label": "名称"},
                        {"key": "last_seen_at", "label": "最后出现"},
                    ],
                    rows=instruments,
                ),
            ],
        }

    def _build_public_sentiment_result_preview(self, connection: Any) -> dict[str, Any] | None:
        post_rows = connection.execute(
            """
            SELECT title, sentiment_label, sentiment_score, published_at,
                   sentiment_positive_cues_json, sentiment_negative_cues_json
            FROM core_sentiment_posts
            ORDER BY published_at DESC, record_id ASC
            LIMIT 5
            """
        ).fetchall()
        topic_rows = connection.execute(
            """
            SELECT topic_name, post_count, dominant_sentiment_label, average_sentiment_score
            FROM core_sentiment_topics
            ORDER BY post_count DESC, topic_name ASC
            LIMIT 5
            """
        ).fetchall()
        if not post_rows and not topic_rows:
            return None
        posts = []
        for title, sentiment_label, sentiment_score, published_at, positive_json, negative_json in post_rows:
            cues = self._json_list(positive_json)[:2] + self._json_list(negative_json)[:2]
            posts.append(
                {
                    "title": title,
                    "sentiment_label": self._preview_sentiment_label(sentiment_label),
                    "sentiment_score": self._preview_score_text(sentiment_score),
                    "published_at": self._preview_date_text(published_at),
                    "cues": "、".join(str(item) for item in cues) if cues else "未提供",
                }
            )
        topics = [
            {
                "topic_name": self._preview_topic_label("public_sentiment", row[0]),
                "post_count": int(row[1]),
                "dominant_sentiment_label": self._preview_sentiment_label(row[2]),
                "average_sentiment_score": self._preview_score_text(row[3]),
            }
            for row in topic_rows
        ]
        return {
            "kind": "public_sentiment",
            "tables": [
                self._preview_table(
                    title="帖子样本",
                    description="用于快速查看情绪标签、得分和代表性线索。",
                    columns=[
                        {"key": "title", "label": "帖子标题"},
                        {"key": "sentiment_label", "label": "情绪"},
                        {"key": "sentiment_score", "label": "得分"},
                        {"key": "published_at", "label": "日期"},
                        {"key": "cues", "label": "代表线索"},
                    ],
                    rows=posts,
                ),
                self._preview_table(
                    title="主题观察",
                    description="用于快速对比不同主题的讨论量与主导情绪。",
                    columns=[
                        {"key": "topic_name", "label": "主题"},
                        {"key": "post_count", "label": "帖子数"},
                        {"key": "dominant_sentiment_label", "label": "主导情绪"},
                        {"key": "average_sentiment_score", "label": "平均得分"},
                    ],
                    rows=topics,
                ),
            ],
        }

    def _preview_table(self, *, title: str, description: str, columns: list[dict[str, str]], rows: list[dict[str, Any]]) -> dict[str, Any]:
        return {
            "title": title,
            "description": description,
            "columns": columns,
            "rows": rows,
        }

    def _preview_date_text(self, value: Any) -> str:
        if value is None:
            return "未提供"
        text = str(value).strip()
        if not text:
            return "未提供"
        return text[:10]

    def _preview_score_text(self, value: Any) -> str:
        try:
            return f"{float(value):.4f}".rstrip("0").rstrip(".")
        except Exception:
            return str(value)

    def _json_list(self, raw_value: Any) -> list[Any]:
        if not raw_value:
            return []
        if isinstance(raw_value, list):
            return raw_value
        try:
            parsed = json.loads(str(raw_value))
        except Exception:
            return []
        return parsed if isinstance(parsed, list) else []

    def _preview_topic_text(self, domain: str, topics: list[Any]) -> str:
        labels = [self._preview_topic_label(domain, str(topic)) for topic in topics if str(topic).strip()]
        return "、".join(labels)

    def _preview_topic_label(self, domain: str, topic: str) -> str:
        mapping = {
            "jobs": {
                "backend": "后端开发",
                "frontend": "前端开发",
                "algorithm": "算法题与算法岗",
                "testing": "测试与质量保障",
                "devops": "DevOps 与运维",
                "data_engineering": "数据工程",
                "client": "客户端开发",
            },
            "company_intel": {
                "company_profile": "公司画像",
                "product_update": "产品动态",
                "tech_blog": "技术博客",
                "open_source_activity": "开源动态",
                "funding_event": "融资事件",
                "career_page": "招聘页面",
            },
            "finance": {
                "market_quote": "行情报价",
                "company_announcement": "公司公告",
                "financial_report": "财务报告",
                "fund_holding": "基金持仓",
                "investment_news": "投资新闻",
            },
            "public_sentiment": {
                "interview_experience": "面试体验",
                "salary_benefits": "薪酬福利",
                "workload_overtime": "工作强度",
                "management_culture": "管理与文化",
                "tech_stack_engineering": "技术栈与工程",
                "layoff_hiring_freeze": "裁员与冻结招聘",
                "remote_office_policy": "远程与办公政策",
            },
        }
        return mapping.get(domain, {}).get(topic, topic)

    def _preview_sentiment_label(self, label: Any) -> str:
        mapping = {
            "positive": "正向",
            "neutral": "中性",
            "negative": "负向",
        }
        return mapping.get(str(label), str(label))

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
                {"label": "主题数", "value": len(topics)},
                {"label": "帖子数", "value": total_posts},
            ],
            "narrative": f"共采集 {total_posts} 条舆情帖子，覆盖 {len(topics)} 个主题，下方摘要展示了各主题的情绪分布。",
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
                {"label": "岗位数", "value": posting_count},
                {"label": "公司数", "value": company_count},
                {"label": "技能条目", "value": skill_count},
            ],
            "sections": [
                {
                    "title": "高频公司",
                    "items": [{"label": row[0], "value": row[1]} for row in company_rows],
                },
                {
                    "title": "高频技能",
                    "items": [{"label": row[0], "value": row[1]} for row in skill_rows],
                },
            ],
            "narrative": f"共汇总 {posting_count} 条岗位信息，涉及 {company_count} 家公司，并提取 {skill_count} 条技能记录。",
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
                {"label": "事件数", "value": event_count},
                {"label": "画像条数", "value": profile_count},
                {"label": "项目条数", "value": project_count},
            ],
            "sections": [
                {
                    "title": "跟踪公司",
                    "items": [{"label": row[0], "value": row[1]} for row in profile_rows],
                },
                {
                    "title": "高频项目",
                    "items": [{"label": row[0], "value": row[1]} for row in project_rows],
                },
            ],
            "narrative": f"共汇总 {event_count} 条公司情报事件，形成 {profile_count} 条公司画像和 {project_count} 条项目记录。",
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
                {"label": "事件数", "value": event_count},
                {"label": "标的数", "value": instrument_count},
                {"label": "指标条数", "value": metric_count},
            ],
            "sections": [
                {
                    "title": "跟踪标的",
                    "items": [{"label": row[0], "value": row[1] or row[0]} for row in instrument_rows],
                },
                {
                    "title": "高频指标",
                    "items": [{"label": row[0], "value": row[1]} for row in metric_rows],
                },
            ],
            "narrative": f"共汇总 {event_count} 条金融事件，覆盖 {instrument_count} 个标的，并提取 {metric_count} 条指标记录。",
        }
    def _build_warnings(self, raw_records: list[RawRecord], fetch_stats: dict[str, Any], quality_stats: dict[str, Any]) -> list[str]:
        warnings: list[str] = []
        if raw_records and raw_records[0].source_id == "seed":
            warnings.append("本次运行未从在线来源获取记录，已使用本地 seed 回退数据。")
        if fetch_stats.get("cache_hits", 0) > 0:
            warnings.append(f"抓取缓存命中了 {fetch_stats['cache_hits']} 次请求。")
        if fetch_stats.get("total_retries", 0) > 0:
            warnings.append(f"抓取阶段共发生 {fetch_stats['total_retries']} 次重试。")
        if quality_stats.get("duplicate_count", 0) > 0:
            warnings.append(f"去重阶段移除了 {quality_stats['duplicate_count']} 条重复记录。")
        if quality_stats.get("dropped_by_quality", 0) > 0:
            warnings.append(f"质量规则剔除了 {quality_stats['dropped_by_quality']} 条记录。")
        if quality_stats.get("truncated_count", 0) > 0:
            warnings.append(f"由于 max_output_records 限制，额外截断了 {quality_stats['truncated_count']} 条记录。")
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
        sqlite_file = str(artifacts.get("sqlite_file", "") or "")
        domain_name = str(run_report.get("task", {}).get("domain", "") or "")
        if sqlite_file and domain_name and "result_preview" not in quality_report:
            preview = self._build_result_preview(domain_name, Path(sqlite_file))
            if preview is not None:
                quality_report["result_preview"] = preview
        run_report_stat = run_report_path.stat()
        quality_report_stat = quality_report_path.stat() if quality_report_path.exists() else run_report_stat
        created_at = str(run_report.get("created_at") or self._timestamp_to_iso(run_report_stat.st_mtime))
        updated_at = self._timestamp_to_iso(max(run_report_stat.st_mtime, quality_report_stat.st_mtime))
        return {
            "task": dict(run_report.get("task", {})),
            "task_payload": dict(run_report.get("task_payload", {})) if isinstance(run_report.get("task_payload", {}), dict) else None,
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
            raise FileNotFoundError(f"未找到 task_id={task_id} 的运行报告。")
        if len(matches) > 1:
            raise TaskValidationError(f"task_id={task_id} 存在多条记录，请指定 --domain 进行区分。")
        return matches[0]

    def _read_json_file(self, path: Path) -> dict[str, Any]:
        return json.loads(path.read_text(encoding="utf-8"))

    def _timestamp_to_iso(self, timestamp: float) -> str:
        return datetime.fromtimestamp(timestamp, tz=UTC).isoformat()
