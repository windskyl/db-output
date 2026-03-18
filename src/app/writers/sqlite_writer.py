from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from app.models.records import NormalizedRecord, RunArtifacts


class SQLiteWriter:
    def write(self, run_summary: dict, records: list[NormalizedRecord], artifacts: RunArtifacts) -> None:
        sqlite_path = Path(artifacts.sqlite_file)
        sqlite_path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(sqlite_path)
        try:
            self._create_base_tables(connection)
            self._create_domain_tables(connection, run_summary["domain"])
            connection.execute(
                """
                INSERT OR REPLACE INTO task_runs (
                    task_id, domain, scenario_template, status,
                    raw_count, normalized_count, output_count,
                    raw_file, normalized_file, sqlite_file
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_summary["task_id"],
                    run_summary["domain"],
                    run_summary.get("scenario_template"),
                    run_summary["status"],
                    run_summary["raw_count"],
                    run_summary["normalized_count"],
                    run_summary["output_count"],
                    artifacts.raw_file,
                    artifacts.normalized_file,
                    artifacts.sqlite_file,
                ),
            )
            connection.execute(
                "INSERT OR REPLACE INTO quality_reports (task_id, domain, report_json) VALUES (?, ?, ?)",
                (
                    run_summary["task_id"],
                    run_summary["domain"],
                    json.dumps(run_summary["quality_report"], ensure_ascii=False),
                ),
            )
            self._insert_domain_records(connection, run_summary["domain"], records)
            connection.commit()
        finally:
            connection.close()

    def _create_base_tables(self, connection: sqlite3.Connection) -> None:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS task_runs (
                task_id TEXT PRIMARY KEY,
                domain TEXT NOT NULL,
                scenario_template TEXT,
                status TEXT NOT NULL,
                raw_count INTEGER NOT NULL,
                normalized_count INTEGER NOT NULL,
                output_count INTEGER NOT NULL,
                raw_file TEXT NOT NULL,
                normalized_file TEXT NOT NULL,
                sqlite_file TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS task_errors (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id TEXT NOT NULL,
                source_id TEXT,
                stage TEXT NOT NULL,
                error_type TEXT NOT NULL,
                message TEXT NOT NULL,
                detail_json TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS raw_index (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id TEXT NOT NULL,
                source_id TEXT NOT NULL,
                request_url TEXT NOT NULL,
                content_hash TEXT NOT NULL,
                fetched_at TEXT NOT NULL,
                raw_file_path TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS quality_reports (
                task_id TEXT PRIMARY KEY,
                domain TEXT NOT NULL,
                report_json TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
            """
        )

    def _create_domain_tables(self, connection: sqlite3.Connection, domain: str) -> None:
        common_columns = """
            record_id TEXT PRIMARY KEY,
            primary_entity TEXT NOT NULL,
            title TEXT NOT NULL,
            source_id TEXT NOT NULL,
            source_type TEXT NOT NULL,
            source_label TEXT NOT NULL,
            source_tag TEXT,
            source_url TEXT NOT NULL,
            published_at TEXT NOT NULL,
            collected_at TEXT NOT NULL,
            relevance_score REAL NOT NULL,
            topic_tags_json TEXT NOT NULL,
            extra_json TEXT NOT NULL
        """
        statements = {
            "jobs": f"CREATE TABLE IF NOT EXISTS core_jobs_postings ({common_columns});",
            "finance": f"CREATE TABLE IF NOT EXISTS core_finance_events ({common_columns});",
            "company_intel": f"CREATE TABLE IF NOT EXISTS core_company_events ({common_columns});",
            "public_sentiment": f"CREATE TABLE IF NOT EXISTS core_sentiment_posts ({common_columns}, content_text TEXT NOT NULL);",
        }
        connection.executescript(statements[domain])

    def _insert_domain_records(self, connection: sqlite3.Connection, domain: str, records: list[NormalizedRecord]) -> None:
        if not records:
            return
        if domain == "public_sentiment":
            connection.executemany(
                """
                INSERT OR REPLACE INTO core_sentiment_posts (
                    record_id, primary_entity, title, source_id, source_type, source_label, source_tag,
                    source_url, published_at, collected_at, relevance_score,
                    topic_tags_json, extra_json, content_text
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        r.record_id,
                        r.primary_entity,
                        r.title,
                        r.source_id,
                        r.source_type,
                        r.source_label,
                        r.source_tag,
                        r.source_url,
                        r.published_at,
                        r.collected_at,
                        r.relevance_score,
                        json.dumps(r.topic_tags, ensure_ascii=False),
                        json.dumps(r.extra, ensure_ascii=False),
                        r.content_text,
                    )
                    for r in records
                ],
            )
            return
        table_name = {
            "jobs": "core_jobs_postings",
            "finance": "core_finance_events",
            "company_intel": "core_company_events",
        }[domain]
        connection.executemany(
            f"""
            INSERT OR REPLACE INTO {table_name} (
                record_id, primary_entity, title, source_id, source_type, source_label, source_tag,
                source_url, published_at, collected_at, relevance_score,
                topic_tags_json, extra_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    r.record_id,
                    r.primary_entity,
                    r.title,
                    r.source_id,
                    r.source_type,
                    r.source_label,
                    r.source_tag,
                    r.source_url,
                    r.published_at,
                    r.collected_at,
                    r.relevance_score,
                    json.dumps(r.topic_tags, ensure_ascii=False),
                    json.dumps(r.extra, ensure_ascii=False),
                )
                for r in records
            ],
        )

