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
            "finance": (
                f"CREATE TABLE IF NOT EXISTS core_finance_events ({common_columns});"
                "CREATE TABLE IF NOT EXISTS core_finance_instruments ("
                "instrument_id TEXT PRIMARY KEY,"
                "primary_entity TEXT NOT NULL,"
                "symbol TEXT NOT NULL,"
                "instrument_name TEXT,"
                "market TEXT,"
                "currency TEXT,"
                "source_id TEXT NOT NULL,"
                "source_label TEXT NOT NULL,"
                "last_seen_at TEXT NOT NULL,"
                "extra_json TEXT NOT NULL"
                ");"
                "CREATE TABLE IF NOT EXISTS core_finance_metrics ("
                "metric_record_id TEXT PRIMARY KEY,"
                "record_id TEXT NOT NULL,"
                "primary_entity TEXT NOT NULL,"
                "metric_name TEXT NOT NULL,"
                "metric_value TEXT NOT NULL,"
                "metric_unit TEXT,"
                "currency TEXT,"
                "published_at TEXT NOT NULL,"
                "source_id TEXT NOT NULL,"
                "source_url TEXT NOT NULL,"
                "extra_json TEXT NOT NULL"
                ");"
            ),
            "company_intel": f"CREATE TABLE IF NOT EXISTS core_company_events ({common_columns});",
            "public_sentiment": (
                f"CREATE TABLE IF NOT EXISTS core_sentiment_posts ({common_columns}, content_text TEXT NOT NULL);"
                "CREATE TABLE IF NOT EXISTS core_sentiment_topics ("
                "topic_record_id TEXT PRIMARY KEY,"
                "primary_entity TEXT NOT NULL,"
                "topic_name TEXT NOT NULL,"
                "post_count INTEGER NOT NULL,"
                "first_published_at TEXT NOT NULL,"
                "last_published_at TEXT NOT NULL,"
                "sample_record_id TEXT NOT NULL,"
                "sample_title TEXT NOT NULL,"
                "source_ids_json TEXT NOT NULL,"
                "extra_json TEXT NOT NULL"
                ");"
            ),
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
            self._insert_sentiment_topics(connection, records)
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
        if domain == "finance":
            self._insert_finance_instruments(connection, records)
            self._insert_finance_metrics(connection, records)

    def _insert_finance_instruments(self, connection: sqlite3.Connection, records: list[NormalizedRecord]) -> None:
        instrument_rows: dict[str, tuple] = {}
        for record in records:
            symbol = str(record.extra.get("symbol", "") or "").strip()
            if not symbol:
                continue
            instrument_name = str(record.extra.get("instrument_name", "") or record.extra.get("company_name", "") or record.primary_entity)
            market = str(record.extra.get("market", "") or "")
            currency = str(record.extra.get("currency", "") or "")
            instrument_id = symbol.upper()
            instrument_rows[instrument_id] = (
                instrument_id,
                record.primary_entity,
                symbol,
                instrument_name,
                market,
                currency,
                record.source_id,
                record.source_label,
                record.published_at,
                json.dumps(record.extra, ensure_ascii=False),
            )
        if not instrument_rows:
            return
        connection.executemany(
            """
            INSERT OR REPLACE INTO core_finance_instruments (
                instrument_id, primary_entity, symbol, instrument_name, market, currency,
                source_id, source_label, last_seen_at, extra_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            list(instrument_rows.values()),
        )

    def _insert_finance_metrics(self, connection: sqlite3.Connection, records: list[NormalizedRecord]) -> None:
        metric_rows = []
        for record in records:
            metric_name = str(record.extra.get("metric_name", "")).strip()
            metric_value = str(record.extra.get("metric_value", "")).strip()
            if not metric_name or not metric_value:
                continue
            metric_rows.append(
                (
                    f"{record.record_id}:{metric_name}",
                    record.record_id,
                    record.primary_entity,
                    metric_name,
                    metric_value,
                    str(record.extra.get("metric_unit", "") or ""),
                    str(record.extra.get("currency", "") or ""),
                    record.published_at,
                    record.source_id,
                    record.source_url,
                    json.dumps(record.extra, ensure_ascii=False),
                )
            )
        if not metric_rows:
            return
        connection.executemany(
            """
            INSERT OR REPLACE INTO core_finance_metrics (
                metric_record_id, record_id, primary_entity, metric_name, metric_value,
                metric_unit, currency, published_at, source_id, source_url, extra_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            metric_rows,
        )

    def _insert_sentiment_topics(self, connection: sqlite3.Connection, records: list[NormalizedRecord]) -> None:
        topic_rows: dict[str, dict[str, object]] = {}
        for record in records:
            topic_names = self._sentiment_topic_names(record)
            for topic_name in topic_names:
                topic_record_id = f"{record.primary_entity}::{topic_name}"
                row = topic_rows.get(topic_record_id)
                if row is None:
                    row = {
                        "topic_record_id": topic_record_id,
                        "primary_entity": record.primary_entity,
                        "topic_name": topic_name,
                        "post_count": 0,
                        "first_published_at": record.published_at,
                        "last_published_at": record.published_at,
                        "sample_record_id": record.record_id,
                        "sample_title": record.title,
                        "source_ids": set(),
                        "sample_source_url": record.source_url,
                    }
                    topic_rows[topic_record_id] = row
                row["post_count"] = int(row["post_count"]) + 1
                source_ids = row["source_ids"]
                if isinstance(source_ids, set):
                    source_ids.add(record.source_id)
                if record.published_at < str(row["first_published_at"]):
                    row["first_published_at"] = record.published_at
                if record.published_at >= str(row["last_published_at"]):
                    row["last_published_at"] = record.published_at
                    row["sample_record_id"] = record.record_id
                    row["sample_title"] = record.title
                    row["sample_source_url"] = record.source_url
        if not topic_rows:
            return
        connection.executemany(
            """
            INSERT OR REPLACE INTO core_sentiment_topics (
                topic_record_id, primary_entity, topic_name, post_count,
                first_published_at, last_published_at, sample_record_id,
                sample_title, source_ids_json, extra_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    str(row["topic_record_id"]),
                    str(row["primary_entity"]),
                    str(row["topic_name"]),
                    int(row["post_count"]),
                    str(row["first_published_at"]),
                    str(row["last_published_at"]),
                    str(row["sample_record_id"]),
                    str(row["sample_title"]),
                    json.dumps(sorted(row["source_ids"]), ensure_ascii=False),
                    json.dumps({"sample_source_url": row["sample_source_url"]}, ensure_ascii=False),
                )
                for row in topic_rows.values()
            ],
        )

    def _sentiment_topic_names(self, record: NormalizedRecord) -> list[str]:
        raw_topics = record.extra.get("matched_topics", record.topic_tags)
        if isinstance(raw_topics, str):
            values = [raw_topics]
        elif isinstance(raw_topics, (list, tuple, set)):
            values = [str(topic) for topic in raw_topics]
        else:
            return []
        seen: set[str] = set()
        result: list[str] = []
        for value in values:
            topic = value.strip()
            if not topic or topic in seen:
                continue
            seen.add(topic)
            result.append(topic)
        return result