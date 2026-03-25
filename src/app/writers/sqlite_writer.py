from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path

from app.models.records import NormalizedRecord, RunArtifacts


_COMPANY_PROJECT_TOKEN_STOPWORDS = {
    'IDC',
    'GARTNER',
    'SIEM',
    'MAGIC',
    'QUADRANT',
    'MARKETGLANCE',
    'IT',
    'WEB',
    'Q1',
    'Q2',
    'Q3',
    'Q4',
    'GITHUB',
    'AIAGENT',
}

_COMPANY_NAME_STOPWORDS = {
    '\u5947\u5b89\u4fe1',
    '\u5947\u5b89\u4fe1\u96c6\u56e2',
    '\u4ea7\u54c1\u516c\u544a',
    '\u5347\u7ea7\u516c\u544a',
}

_COMPANY_DOCUMENT_MARKERS = (
    '\u62a5\u544a',
    '\u7814\u7a76',
    '\u6307\u5357',
    '\u767d\u76ae\u4e66',
    '\u901a\u544a',
)

_COMPANY_PROJECT_NAME_MARKERS = (
    '\u5e73\u53f0',
    '\u7cfb\u7edf',
    '\u6d4f\u89c8\u5668',
    '\u65b9\u6848',
    '\u667a\u80fd\u4f53',
    '\u4f34\u4fa3',
    '\u7f51\u5173',
    '\u9632\u706b\u5899',
    '\u5f15\u64ce',
    '\u7ec8\u7aef',
    '\u5de5\u4f5c\u53f0',
    '\u9879\u76ee',
)

_COMPANY_PROJECT_NOISE_MARKERS = (
    '\u4e2d\u56fd\u4f01\u4e1a\u5bb6',
    '\u592e\u89c6',
    '\u8d22\u7ecf',
    '\u8bc4\u8bba',
    '\u65b0\u95fb\u8054\u64ad',
    '\u7ecf\u6d4e\u534a\u5c0f\u65f6',
    '\u4e24\u4f1a',
    '\u521b\u5ba2\u6c47',
)

_SENTIMENT_POSITIVE_CUES = (
    ('good', r'\bgood\b', 1.0),
    ('great', r'\bgreat\b', 1.2),
    ('better', r'\bbetter\b', 0.8),
    ('improve', r'\bimprov(?:e|es|ed|ing)\b', 0.8),
    ('helpful', r'\bhelpful\b', 1.0),
    ('useful', r'\buseful\b', 1.0),
    ('innovative', r'\binnovative\b', 0.8),
    ('powerful', r'\bpowerful\b', 0.8),
    ('fast', r'\bfast\b', 0.5),
    ('love', r'\blove\b', 1.2),
    ('success', r'\bsuccess(?:ful)?\b', 1.0),
    ('leading', r'\bleading\b', 0.8),
    ('best', r'\bbest\b', 1.2),
    ('no api key needed', r'no api key needed', 1.5),
    ('no extra billing', r'no extra billing', 1.5),
    ('simplify', r'\bsimplif(?:y|ies|ied|ying)\b', 0.8),
    ('easier', r'\beasier\b', 0.8),
    ('reusable', r'\breusable\b', 0.6),
    ('\u597d\u8bc4', '\u597d\u8bc4', 1.2),
    ('\u65b9\u4fbf', '\u65b9\u4fbf', 0.8),
    ('\u6709\u7528', '\u6709\u7528', 1.0),
    ('\u6613\u7528', '\u6613\u7528', 0.8),
    ('\u63d0\u5347', '\u63d0\u5347', 0.8),
    ('\u6539\u5584', '\u6539\u5584', 0.8),
    ('\u7a33\u5b9a', '\u7a33\u5b9a', 0.8),
    ('\u5f3a\u5927', '\u5f3a\u5927', 0.8),
    ('\u559c\u6b22', '\u559c\u6b22', 1.0),
    ('\u9886\u5148', '\u9886\u5148', 0.8),
)

_SENTIMENT_NEGATIVE_CUES = (
    ('under fire', r'under fire', 1.5),
    ('critic', r'\bcritic(?:s|ism)?\b', 1.0),
    ('disgusting', r'\bdisgusting\b', 1.5),
    ('bad', r'\bbad\b', 1.0),
    ('worse', r'\bworse\b', 1.0),
    ('risk', r'\brisk(?:s)?\b', 0.8),
    ('unsafe', r'\bunsafe\b', 1.5),
    ('fail', r'\bfail(?:ure|ed|ing)?\b', 1.0),
    ('cut back', r'cut back', 1.2),
    ('concern', r'\bconcern(?:s)?\b', 0.8),
    ('issue', r'\bissue(?:s)?\b', 0.8),
    ('\u4e89\u8bae', '\u4e89\u8bae', 1.0),
    ('\u6279\u8bc4', '\u6279\u8bc4', 1.0),
    ('\u7cdf\u7cd5', '\u7cdf\u7cd5', 1.2),
    ('\u98ce\u9669', '\u98ce\u9669', 0.8),
    ('\u95ee\u9898', '\u95ee\u9898', 0.8),
    ('\u62c5\u5fe7', '\u62c5\u5fe7', 0.8),
    ('\u5931\u671b', '\u5931\u671b', 1.0),
    ('\u7ffb\u8f66', '\u7ffb\u8f66', 1.2),
    ('\u88c1\u5458', '\u88c1\u5458', 1.0),
)

_SENTIMENT_NEGATED_NEGATIVE_CUES = (
    ('not bad', r'not bad', 1.0),
    ('not worse', r'not worse', 1.0),
    ('no problem', r'no problem', 1.0),
    ('no problems', r'no problems', 1.0),
    ('without issue', r'without issue', 0.8),
    ('without issues', r'without issues', 0.8),
    ('\u4e0d\u5dee', '\u4e0d\u5dee', 1.0),
    ('\u6ca1\u95ee\u9898', '\u6ca1\u95ee\u9898', 1.0),
    ('\u6ca1\u6709\u95ee\u9898', '\u6ca1\u6709\u95ee\u9898', 1.0),
    ('\u65e0\u95ee\u9898', '\u65e0\u95ee\u9898', 1.0),
)

_SENTIMENT_NEGATED_POSITIVE_CUES = (
    ('not good', r'not good', 1.0),
    ('not great', r'not great', 1.2),
    ('not helpful', r'not helpful', 1.0),
    ('not useful', r'not useful', 1.0),
    ('not better', r'not better', 0.8),
    ('\u4e0d\u597d', '\u4e0d\u597d', 1.0),
    ('\u4e0d\u597d\u7528', '\u4e0d\u597d\u7528', 1.2),
    ('\u4e0d\u7a33\u5b9a', '\u4e0d\u7a33\u5b9a', 1.0),
    ('\u4e0d\u65b9\u4fbf', '\u4e0d\u65b9\u4fbf', 1.0),
    ('\u6ca1\u7528', '\u6ca1\u7528', 1.0),
)

_JOB_SKILL_PATTERNS = (
    ('Python', 'language', (r'\bpython\b',)),
    ('Django', 'framework', (r'\bdjango\b',)),
    ('Flask', 'framework', (r'\bflask\b',)),
    ('FastAPI', 'framework', (r'\bfastapi\b',)),
    ('DevOps', 'practice', (r'\bdevops\b',)),
    ('Cloud', 'domain', (r'\bcloud\b',)),
    ('Web', 'domain', (r'\bweb\b',)),
    ('Security', 'domain', (r'\bsecurity\b',)),
    ('Backend', 'domain', (r'\bback[\s-]?end\b',)),
    ('Frontend', 'domain', (r'\bfront[\s-]?end\b',)),
    ('Support', 'domain', (r'\bsupport\b',)),
    ('AWS', 'cloud', (r'\baws\b', r'amazon web services')),
    ('Azure', 'cloud', (r'\bazure\b',)),
    ('GCP', 'cloud', (r'\bgcp\b', r'google cloud')),
    ('Docker', 'tool', (r'\bdocker\b',)),
    ('Kubernetes', 'tool', (r'\bkubernetes\b',)),
    ('Terraform', 'tool', (r'\bterraform\b',)),
    ('Grafana', 'tool', (r'\bgrafana\b',)),
    ('CI/CD', 'practice', (r'\bci/cd\b', r'\bci cd\b')),
    ('Linux', 'platform', (r'\blinux\b',)),
    ('Unix', 'platform', (r'\bunix\b',)),
    ('Documentation', 'practice', (r'\bdocumentation\b', r'\bdocumenting\b')),
    ('Monitoring', 'domain', (r'\bmonitoring\b',)),
    ('Visualization', 'domain', (r'\bvisualization\b',)),
    ('Federated Learning', 'domain', (r'federated learning',)),
    ('Open Source', 'practice', (r'open-source', r'open source')),
    ('APPFL', 'tool', (r'\bappfl\b',)),
    ('Big Data', 'domain', (r'big data',)),
    ('Performance', 'practice', (r'\bperformance\b',)),
    ('Scalability', 'practice', (r'\bscalability\b',)),
    ('Automation', 'practice', (r'\bautomation\b',)),
)


class SQLiteWriter:
    def write(self, run_summary: dict, records: list[NormalizedRecord], artifacts: RunArtifacts) -> None:
        sqlite_path = Path(artifacts.sqlite_file)
        sqlite_path.parent.mkdir(parents=True, exist_ok=True)
        if sqlite_path.exists():
            sqlite_path.unlink()
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
            "jobs": (
                f"CREATE TABLE IF NOT EXISTS core_jobs_postings ({common_columns});"
                "CREATE TABLE IF NOT EXISTS core_jobs_skills ("
                "skill_record_id TEXT PRIMARY KEY,"
                "record_id TEXT NOT NULL,"
                "primary_entity TEXT NOT NULL,"
                "skill_name TEXT NOT NULL,"
                "skill_type TEXT NOT NULL,"
                "evidence_field TEXT NOT NULL,"
                "source_id TEXT NOT NULL,"
                "source_url TEXT NOT NULL,"
                "published_at TEXT NOT NULL,"
                "extra_json TEXT NOT NULL"
                ");"
            ),
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
            "company_intel": (
                f"CREATE TABLE IF NOT EXISTS core_company_events ({common_columns});"
                "CREATE TABLE IF NOT EXISTS core_company_profiles ("
                "company_id TEXT PRIMARY KEY,"
                "primary_entity TEXT NOT NULL,"
                "company_name TEXT NOT NULL,"
                "evidence_count INTEGER NOT NULL,"
                "first_published_at TEXT NOT NULL,"
                "last_published_at TEXT NOT NULL,"
                "sample_record_id TEXT NOT NULL,"
                "sample_title TEXT NOT NULL,"
                "profile_summary TEXT,"
                "source_ids_json TEXT NOT NULL,"
                "extra_json TEXT NOT NULL"
                ");"
                "CREATE TABLE IF NOT EXISTS core_company_projects ("
                "project_id TEXT PRIMARY KEY,"
                "primary_entity TEXT NOT NULL,"
                "project_name TEXT NOT NULL,"
                "project_type TEXT NOT NULL,"
                "mention_count INTEGER NOT NULL,"
                "first_published_at TEXT NOT NULL,"
                "last_published_at TEXT NOT NULL,"
                "sample_record_id TEXT NOT NULL,"
                "sample_title TEXT NOT NULL,"
                "source_ids_json TEXT NOT NULL,"
                "extra_json TEXT NOT NULL"
                ");"
            ),
            "public_sentiment": (
                f"CREATE TABLE IF NOT EXISTS core_sentiment_posts ({common_columns}, content_text TEXT NOT NULL, sentiment_label TEXT NOT NULL, sentiment_score REAL NOT NULL, sentiment_positive_cues_json TEXT NOT NULL, sentiment_negative_cues_json TEXT NOT NULL);"
                "CREATE TABLE IF NOT EXISTS core_sentiment_topics ("
                "topic_record_id TEXT PRIMARY KEY,"
                "primary_entity TEXT NOT NULL,"
                "topic_name TEXT NOT NULL,"
                "post_count INTEGER NOT NULL,"
                "positive_count INTEGER NOT NULL,"
                "neutral_count INTEGER NOT NULL,"
                "negative_count INTEGER NOT NULL,"
                "average_sentiment_score REAL NOT NULL,"
                "dominant_sentiment_label TEXT NOT NULL,"
                "first_published_at TEXT NOT NULL,"
                "last_published_at TEXT NOT NULL,"
                "sample_record_id TEXT NOT NULL,"
                "sample_title TEXT NOT NULL,"
                "most_positive_record_id TEXT,"
                "most_positive_title TEXT,"
                "most_negative_record_id TEXT,"
                "most_negative_title TEXT,"
                "most_neutral_record_id TEXT,"
                "most_neutral_title TEXT,"
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
            post_rows = []
            sentiment_analyses: dict[str, dict[str, object]] = {}
            for record in records:
                analysis = self._analyze_sentiment(record)
                sentiment_analyses[record.record_id] = analysis
                post_rows.append(
                    (
                        record.record_id,
                        record.primary_entity,
                        record.title,
                        record.source_id,
                        record.source_type,
                        record.source_label,
                        record.source_tag,
                        record.source_url,
                        record.published_at,
                        record.collected_at,
                        record.relevance_score,
                        json.dumps(record.topic_tags, ensure_ascii=False),
                        json.dumps(record.extra, ensure_ascii=False),
                        record.content_text,
                        analysis["label"],
                        analysis["score"],
                        json.dumps(analysis["positive_cues"], ensure_ascii=False),
                        json.dumps(analysis["negative_cues"], ensure_ascii=False),
                    )
                )
            connection.executemany(
                """
                INSERT OR REPLACE INTO core_sentiment_posts (
                    record_id, primary_entity, title, source_id, source_type, source_label, source_tag,
                    source_url, published_at, collected_at, relevance_score,
                    topic_tags_json, extra_json, content_text, sentiment_label, sentiment_score,
                    sentiment_positive_cues_json, sentiment_negative_cues_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                post_rows,
            )
            self._insert_sentiment_topics(connection, records, sentiment_analyses)
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
        if domain == "jobs":
            self._insert_job_skills(connection, records)
        if domain == "finance":
            self._insert_finance_instruments(connection, records)
            self._insert_finance_metrics(connection, records)
        if domain == "company_intel":
            self._insert_company_profiles(connection, records)
            self._insert_company_projects(connection, records)

    def _insert_job_skills(self, connection: sqlite3.Connection, records: list[NormalizedRecord]) -> None:
        skill_rows = []
        for record in records:
            for skill_name, skill_type, evidence_field in self._extract_job_skills(record):
                skill_id = re.sub(r'[^a-z0-9]+', '-', skill_name.lower()).strip('-')
                skill_rows.append(
                    (
                        f"{record.record_id}:{skill_id}",
                        record.record_id,
                        record.primary_entity,
                        skill_name,
                        skill_type,
                        evidence_field,
                        record.source_id,
                        record.source_url,
                        record.published_at,
                        json.dumps(
                            {
                                'category': str(record.extra.get('category', '') or ''),
                                'source_tag': record.source_tag,
                            },
                            ensure_ascii=False,
                        ),
                    )
                )
        if not skill_rows:
            return
        connection.executemany(
            """
            INSERT OR REPLACE INTO core_jobs_skills (
                skill_record_id, record_id, primary_entity, skill_name, skill_type,
                evidence_field, source_id, source_url, published_at, extra_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            skill_rows,
        )

    def _extract_job_skills(self, record: NormalizedRecord) -> list[tuple[str, str, str]]:
        matches: dict[str, tuple[str, str]] = {}
        for field_name, text in self._job_skill_sources(record).items():
            lower_text = text.lower()
            for skill_name, skill_type, patterns in _JOB_SKILL_PATTERNS:
                if skill_name in matches:
                    continue
                if any(re.search(pattern, lower_text) for pattern in patterns):
                    matches[skill_name] = (skill_type, field_name)
        return [(skill_name, skill_type, evidence_field) for skill_name, (skill_type, evidence_field) in matches.items()]

    def _job_skill_sources(self, record: NormalizedRecord) -> dict[str, str]:
        return {
            'title': record.title,
            'content_text': record.content_text,
            'category': str(record.extra.get('category', '') or ''),
            'source_tag': record.source_tag,
        }
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

    def _insert_company_profiles(self, connection: sqlite3.Connection, records: list[NormalizedRecord]) -> None:
        profile_rows: dict[str, dict[str, object]] = {}
        for record in records:
            company_id = record.primary_entity.strip()
            if not company_id:
                continue
            signal = self._company_profile_signal(record)
            row = profile_rows.get(company_id)
            if row is None:
                row = {
                    "company_id": company_id,
                    "primary_entity": record.primary_entity,
                    "company_name": record.primary_entity,
                    "evidence_count": 0,
                    "first_published_at": record.published_at,
                    "last_published_at": record.published_at,
                    "sample_record_id": record.record_id,
                    "sample_title": record.title,
                    "profile_summary": record.content_text,
                    "source_ids": set(),
                    "sample_source_url": record.source_url,
                    "sample_source_id": record.source_id,
                    "sample_topic_tags": list(record.topic_tags),
                    "sample_signal": signal,
                    "sample_published_at": record.published_at,
                }
                profile_rows[company_id] = row
            row["evidence_count"] = int(row["evidence_count"]) + 1
            source_ids = row["source_ids"]
            if isinstance(source_ids, set):
                source_ids.add(record.source_id)
            if record.published_at < str(row["first_published_at"]):
                row["first_published_at"] = record.published_at
            if record.published_at > str(row["last_published_at"]):
                row["last_published_at"] = record.published_at
            current_signal = int(row["sample_signal"])
            current_published_at = str(row["sample_published_at"])
            if signal > current_signal or (signal == current_signal and record.published_at >= current_published_at):
                row["sample_record_id"] = record.record_id
                row["sample_title"] = record.title
                row["profile_summary"] = record.content_text
                row["sample_source_url"] = record.source_url
                row["sample_source_id"] = record.source_id
                row["sample_topic_tags"] = list(record.topic_tags)
                row["sample_signal"] = signal
                row["sample_published_at"] = record.published_at
        if not profile_rows:
            return
        connection.executemany(
            """
            INSERT OR REPLACE INTO core_company_profiles (
                company_id, primary_entity, company_name, evidence_count,
                first_published_at, last_published_at, sample_record_id,
                sample_title, profile_summary, source_ids_json, extra_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    str(row["company_id"]),
                    str(row["primary_entity"]),
                    str(row["company_name"]),
                    int(row["evidence_count"]),
                    str(row["first_published_at"]),
                    str(row["last_published_at"]),
                    str(row["sample_record_id"]),
                    str(row["sample_title"]),
                    str(row["profile_summary"]),
                    json.dumps(sorted(row["source_ids"]), ensure_ascii=False),
                    json.dumps(
                        {
                            "sample_source_url": row["sample_source_url"],
                            "sample_source_id": row["sample_source_id"],
                            "sample_topic_tags": row["sample_topic_tags"],
                        },
                        ensure_ascii=False,
                    ),
                )
                for row in profile_rows.values()
            ],
        )

    def _insert_company_projects(self, connection: sqlite3.Connection, records: list[NormalizedRecord]) -> None:
        project_rows: dict[str, dict[str, object]] = {}
        for record in records:
            project_names = self._extract_company_project_names(record)
            if not project_names:
                continue
            project_type = self._company_project_type(record)
            for project_name in project_names:
                project_id = self._company_project_id(record.primary_entity, project_name)
                row = project_rows.get(project_id)
                if row is None:
                    row = {
                        "project_id": project_id,
                        "primary_entity": record.primary_entity,
                        "project_name": project_name,
                        "project_type": project_type,
                        "mention_count": 0,
                        "first_published_at": record.published_at,
                        "last_published_at": record.published_at,
                        "sample_record_id": record.record_id,
                        "sample_title": record.title,
                        "source_ids": set(),
                        "sample_source_url": record.source_url,
                        "sample_source_tag": record.source_tag,
                    }
                    project_rows[project_id] = row
                row["mention_count"] = int(row["mention_count"]) + 1
                source_ids = row["source_ids"]
                if isinstance(source_ids, set):
                    source_ids.add(record.source_id)
                current_type = str(row["project_type"])
                if self._company_project_type_rank(project_type) >= self._company_project_type_rank(current_type):
                    row["project_type"] = project_type
                if record.published_at < str(row["first_published_at"]):
                    row["first_published_at"] = record.published_at
                if record.published_at >= str(row["last_published_at"]):
                    row["last_published_at"] = record.published_at
                    row["sample_record_id"] = record.record_id
                    row["sample_title"] = record.title
                    row["sample_source_url"] = record.source_url
                    row["sample_source_tag"] = record.source_tag
        if not project_rows:
            return
        connection.executemany(
            """
            INSERT OR REPLACE INTO core_company_projects (
                project_id, primary_entity, project_name, project_type,
                mention_count, first_published_at, last_published_at,
                sample_record_id, sample_title, source_ids_json, extra_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    str(row["project_id"]),
                    str(row["primary_entity"]),
                    str(row["project_name"]),
                    str(row["project_type"]),
                    int(row["mention_count"]),
                    str(row["first_published_at"]),
                    str(row["last_published_at"]),
                    str(row["sample_record_id"]),
                    str(row["sample_title"]),
                    json.dumps(sorted(row["source_ids"]), ensure_ascii=False),
                    json.dumps(
                        {
                            "sample_source_url": row["sample_source_url"],
                            "sample_source_tag": row["sample_source_tag"],
                        },
                        ensure_ascii=False,
                    ),
                )
                for row in project_rows.values()
            ],
        )

    def _insert_sentiment_topics(self, connection: sqlite3.Connection, records: list[NormalizedRecord], sentiment_analyses: dict[str, dict[str, object]]) -> None:
        topic_rows: dict[str, dict[str, object]] = {}
        for record in records:
            analysis = sentiment_analyses[record.record_id]
            sentiment_label = str(analysis["label"])
            sentiment_score = float(analysis["score"])
            positive_cues = list(analysis["positive_cues"])
            negative_cues = list(analysis["negative_cues"])
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
                        "positive_count": 0,
                        "neutral_count": 0,
                        "negative_count": 0,
                        "sentiment_score_sum": 0.0,
                        "first_published_at": record.published_at,
                        "last_published_at": record.published_at,
                        "sample_record_id": record.record_id,
                        "sample_title": record.title,
                        "source_ids": set(),
                        "sample_source_url": record.source_url,
                        "most_positive_record_id": None,
                        "most_positive_title": None,
                        "most_positive_score": None,
                        "most_positive_cues": [],
                        "positive_cue_counts": {},
                        "most_negative_record_id": None,
                        "most_negative_title": None,
                        "most_negative_score": None,
                        "most_negative_cues": [],
                        "negative_cue_counts": {},
                        "most_neutral_record_id": None,
                        "most_neutral_title": None,
                        "most_neutral_abs_score": None,
                        "most_neutral_cues": [],
                    }
                    topic_rows[topic_record_id] = row
                row["post_count"] = int(row["post_count"]) + 1
                row[f"{sentiment_label}_count"] = int(row[f"{sentiment_label}_count"]) + 1
                row["sentiment_score_sum"] = float(row["sentiment_score_sum"]) + float(sentiment_score)
                self._merge_cue_counts(row["positive_cue_counts"], positive_cues)
                self._merge_cue_counts(row["negative_cue_counts"], negative_cues)
                if sentiment_label == "positive":
                    current_positive = row["most_positive_score"]
                    if current_positive is None or float(sentiment_score) >= float(current_positive):
                        row["most_positive_score"] = float(sentiment_score)
                        row["most_positive_record_id"] = record.record_id
                        row["most_positive_title"] = record.title
                        row["most_positive_cues"] = positive_cues
                if sentiment_label == "negative":
                    current_negative = row["most_negative_score"]
                    if current_negative is None or float(sentiment_score) <= float(current_negative):
                        row["most_negative_score"] = float(sentiment_score)
                        row["most_negative_record_id"] = record.record_id
                        row["most_negative_title"] = record.title
                        row["most_negative_cues"] = negative_cues
                neutral_distance = abs(float(sentiment_score))
                current_neutral_distance = row["most_neutral_abs_score"]
                if current_neutral_distance is None or neutral_distance <= float(current_neutral_distance):
                    row["most_neutral_abs_score"] = neutral_distance
                    row["most_neutral_record_id"] = record.record_id
                    row["most_neutral_title"] = record.title
                    row["most_neutral_cues"] = positive_cues if positive_cues else negative_cues
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
                positive_count, neutral_count, negative_count, average_sentiment_score,
                dominant_sentiment_label, first_published_at, last_published_at, sample_record_id,
                sample_title, most_positive_record_id, most_positive_title,
                most_negative_record_id, most_negative_title, most_neutral_record_id,
                most_neutral_title, source_ids_json, extra_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    str(row["topic_record_id"]),
                    str(row["primary_entity"]),
                    str(row["topic_name"]),
                    int(row["post_count"]),
                    int(row["positive_count"]),
                    int(row["neutral_count"]),
                    int(row["negative_count"]),
                    round(float(row["sentiment_score_sum"]) / max(int(row["post_count"]), 1), 4),
                    self._dominant_sentiment_label(row),
                    str(row["first_published_at"]),
                    str(row["last_published_at"]),
                    str(row["sample_record_id"]),
                    str(row["sample_title"]),
                    row["most_positive_record_id"],
                    row["most_positive_title"],
                    row["most_negative_record_id"],
                    row["most_negative_title"],
                    row["most_neutral_record_id"],
                    row["most_neutral_title"],
                    json.dumps(sorted(row["source_ids"]), ensure_ascii=False),
                    json.dumps(
                        {
                            "sample_source_url": row["sample_source_url"],
                            "most_positive_cues": row["most_positive_cues"],
                            "most_negative_cues": row["most_negative_cues"],
                            "most_neutral_cues": row["most_neutral_cues"],
                            "positive_cue_counts": self._serialize_cue_counts(row["positive_cue_counts"]),
                            "negative_cue_counts": self._serialize_cue_counts(row["negative_cue_counts"]),
                        },
                        ensure_ascii=False,
                    ),
                )
                for row in topic_rows.values()
            ],
        )

    def _company_profile_signal(self, record: NormalizedRecord) -> int:
        if record.source_type == 'official_company_report':
            return 3
        if 'company_profile' in record.topic_tags:
            return 2
        if record.source_type == 'official_company_news':
            return 1
        return 0

    def _company_project_type(self, record: NormalizedRecord) -> str:
        lower_text = f"{record.title} {record.content_text}".lower()
        if record.source_type == 'official_company_update' or record.source_tag in {'\u5347\u7ea7\u516c\u544a', '\u4ea7\u54c1\u516c\u544a'}:
            return 'product_update'
        if record.source_type == 'official_company_report':
            return 'market_report'
        if any(hint in lower_text for hint in ('openclaw', 'safeskill', '\u5e73\u53f0', '\u65b9\u6848', '\u667a\u80fd\u4f53', '\u6280\u672f')):
            return 'product_or_platform'
        return 'company_project'

    def _company_project_type_rank(self, project_type: str) -> int:
        return {
            'product_update': 3,
            'product_or_platform': 2,
            'market_report': 1,
            'company_project': 0,
        }.get(project_type, 0)

    def _extract_company_project_names(self, record: NormalizedRecord) -> list[str]:
        if record.source_type == 'official_company_report':
            return []

        candidates: list[str] = []
        update_candidate = self._extract_update_project_name(record.title)
        if update_candidate:
            candidates.append(update_candidate)

        combined_text = f"{record.title}\n{record.content_text}"
        for pattern in (r'\u201c([^\u201d]{2,40})\u201d', r'"([^"]{2,40})"', r'\u300a([^\u300b]{2,60})\u300b'):
            for match in re.findall(pattern, combined_text):
                candidate = self._normalize_project_candidate(match)
                if self._is_valid_company_project_candidate(candidate) and self._looks_like_company_project_name(candidate):
                    candidates.append(candidate)

        for token in re.findall(r'[A-Za-z][A-Za-z0-9-]{2,20}', combined_text):
            candidate = token.strip('-')
            if self._is_valid_company_project_token(candidate):
                candidates.append(candidate)

        return self._dedupe_preserve_order(candidates)

    def _extract_update_project_name(self, title: str) -> str | None:
        candidate = re.sub(r'(\u4ea7\u54c1\u7248\u672c)?\u5347\u7ea7\u516c\u544a.*$', '', title).strip(' -\u2014')
        candidate = re.sub(r'\u66f4\u65b0\u901a\u544a.*$', '', candidate).strip(' -\u2014')
        candidate = re.sub(r'\u4ea7\u54c1\u516c\u544a.*$', '', candidate).strip(' -\u2014')
        candidate = re.sub(r'^\u5947\u5b89\u4fe1\u96c6\u56e2\d{4}\u5e74\d{2}\u6708', '', candidate).strip(' -\u2014')
        candidate = self._normalize_project_candidate(candidate)
        if not candidate or '\u8865\u4e01\u5e93' in candidate:
            return None
        return candidate if self._is_valid_company_project_candidate(candidate) else None

    def _normalize_project_candidate(self, value: str) -> str:
        candidate = ' '.join(str(value).replace('\u3000', ' ').split())
        candidate = candidate.strip(" \t\r\n-:,.;()[]<>'\"")
        return candidate.strip("\u2014\u3001\u3002\u300a\u300b\u3010\u3011\u201c\u201d\uff08\uff09\uff1a\uff0c\uff1b")

    def _is_valid_company_project_candidate(self, candidate: str) -> bool:
        if not candidate or len(candidate) < 2 or len(candidate) > 80:
            return False
        if candidate in _COMPANY_NAME_STOPWORDS:
            return False
        if any(marker in candidate for marker in _COMPANY_PROJECT_NOISE_MARKERS):
            return False
        if '+' in candidate and not any(char.isdigit() for char in candidate):
            return False
        if candidate.isascii() and len(candidate.split()) >= 3:
            return False
        if any(marker in candidate for marker in _COMPANY_DOCUMENT_MARKERS):
            return False
        if re.search(r'[:|闁挎稑琚埀顒€鍋婄槐鎺楁晬?!]', candidate):
            return False
        if len(candidate) > 18 and not re.search(r'[A-Za-z0-9-]', candidate):
            return False
        return True

    def _looks_like_company_project_name(self, candidate: str) -> bool:
        if re.search(r'[:|闁挎稑琚埀顒€鍋婄槐鎺楁晬?!]', candidate):
            return True
        return any(marker in candidate for marker in _COMPANY_PROJECT_NAME_MARKERS)
    def _is_valid_company_project_token(self, token: str) -> bool:
        upper = token.upper()
        if upper in _COMPANY_PROJECT_TOKEN_STOPWORDS:
            return False
        if any(marker in token for marker in _COMPANY_PROJECT_NOISE_MARKERS):
            return False
        if token.islower() and not any(char.isdigit() for char in token):
            return False
        if any(char.isdigit() for char in token):
            return True
        if token.upper() == token:
            return len(token) >= 5
        return any(char.isupper() for char in token[1:])

    def _company_project_id(self, primary_entity: str, project_name: str) -> str:
        normalized = re.sub(r'\s+', '', project_name).lower()
        return f"{primary_entity}::{normalized}"

    def _merge_cue_counts(self, counts: dict[str, int], cues: list[str]) -> None:
        for cue in cues:
            counts[cue] = counts.get(cue, 0) + 1

    def _serialize_cue_counts(self, counts: dict[str, int]) -> list[dict[str, object]]:
        return [
            {"cue": cue, "count": count}
            for cue, count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))
        ]

    def _dominant_sentiment_label(self, row: dict[str, object]) -> str:
        positive_count = int(row["positive_count"])
        neutral_count = int(row["neutral_count"])
        negative_count = int(row["negative_count"])
        if positive_count > neutral_count and positive_count > negative_count:
            return "positive"
        if negative_count > neutral_count and negative_count > positive_count:
            return "negative"
        return "neutral"

    def _analyze_sentiment(self, record: NormalizedRecord) -> dict[str, object]:
        text = f"{record.title} {record.content_text}".lower()
        positive_override_matches = self._match_sentiment_cues(text, _SENTIMENT_NEGATED_NEGATIVE_CUES)
        negative_override_matches = self._match_sentiment_cues(text, _SENTIMENT_NEGATED_POSITIVE_CUES)
        base_text = text
        for _, pattern, _ in _SENTIMENT_NEGATED_NEGATIVE_CUES + _SENTIMENT_NEGATED_POSITIVE_CUES:
            base_text = re.sub(pattern, ' ', base_text)
        positive_matches = positive_override_matches + self._match_sentiment_cues(base_text, _SENTIMENT_POSITIVE_CUES)
        negative_matches = negative_override_matches + self._match_sentiment_cues(base_text, _SENTIMENT_NEGATIVE_CUES)
        positive_score_total = sum(match["weight"] for match in positive_matches)
        negative_score_total = sum(match["weight"] for match in negative_matches)
        total_score = positive_score_total + negative_score_total
        if total_score == 0:
            return {
                "label": "neutral",
                "score": 0.0,
                "positive_cues": [],
                "negative_cues": [],
            }
        score = round((positive_score_total - negative_score_total) / total_score, 4)
        if score >= 0.2:
            label = "positive"
        elif score <= -0.2:
            label = "negative"
        else:
            label = "neutral"
        return {
            "label": label,
            "score": score,
            "positive_cues": [str(match["label"]) for match in positive_matches],
            "negative_cues": [str(match["label"]) for match in negative_matches],
        }

    def _classify_sentiment(self, record: NormalizedRecord) -> tuple[str, float]:
        analysis = self._analyze_sentiment(record)
        return str(analysis["label"]), float(analysis["score"])

    def _match_sentiment_cues(self, text: str, cues: tuple[tuple[str, str, float], ...]) -> list[dict[str, object]]:
        matches: list[dict[str, object]] = []
        for label, pattern, weight in cues:
            if re.search(pattern, text):
                matches.append({"label": label, "weight": float(weight)})
        return matches

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

    def _dedupe_preserve_order(self, values: list[str]) -> list[str]:
        seen: set[str] = set()
        result: list[str] = []
        for value in values:
            key = value.lower()
            if key in seen:
                continue
            seen.add(key)
            result.append(value)
        return result