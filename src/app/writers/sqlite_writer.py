from __future__ import annotations

import json
import math
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
    'IDCMARKETGLANCE',
    'GITHUBADVISORYDATA',
}

_COMPANY_NAME_STOPWORDS = {
    '奇安信',
    '奇安信集团',
    '产品公告',
    '升级公告',
}

_COMPANY_DOCUMENT_MARKERS = (
    '报告',
    '研究',
    '指南',
    '白皮书',
    '通告',
)

_COMPANY_PROJECT_NAME_MARKERS = (
    '平台',
    '系统',
    '浏览器',
    '方案',
    '伴侣',
    '网关',
    '防火墙',
    '引擎',
    '终端',
    '工作台',
    '项目',
)

_COMPANY_PROJECT_NOISE_MARKERS = (
    '中国企业家',
    '央视',
    '财经',
    '评论',
    '新闻联播',
    '经济半小时',
    '两会',
    '创客汇',
    '媒体聚焦',
    '独家对话',
)

_COMPANY_PROJECT_SENTENCE_PUNCTUATION = re.compile(r'[:：|?!？！；;，,。]')
_COMPANY_PROJECT_MODEL_TOKEN_PATTERN = re.compile(r'^[A-Z]{2,}(?:-[A-Z]{1,})+$')

_SENTIMENT_POSITIVE_CUES = (
    ('good', '\\bgood\\b', 1.0),
    ('great', '\\bgreat\\b', 1.2),
    ('better', '\\bbetter\\b', 0.8),
    ('improve', '\\bimprov(?:e|es|ed|ing)\\b', 0.8),
    ('helpful', '\\bhelpful\\b', 1.0),
    ('useful', '\\buseful\\b', 1.0),
    ('innovative', '\\binnovative\\b', 0.8),
    ('powerful', '\\bpowerful\\b', 0.8),
    ('fast', '\\bfast\\b', 0.5),
    ('love', '\\blove\\b', 1.2),
    ('success', '\\bsuccess(?:ful)?\\b', 1.0),
    ('leading', '\\bleading\\b', 0.8),
    ('best', '\\bbest\\b', 1.2),
    ('stable', '\\bstable\\b', 0.8),
    ('reliable', '\\breliable\\b', 0.8),
    ('solid', '\\bsolid\\b', 0.6),
    ('worth it', 'worth it', 0.8),
    ('works well', 'works well', 0.8),
    ('no api key needed', 'no api key needed', 1.5),
    ('no extra billing', 'no extra billing', 1.5),
    ('simplify', '\\bsimplif(?:y|ies|ied|ying)\\b', 0.8),
    ('easier', '\\beasier\\b', 0.8),
    ('reusable', '\\breusable\\b', 0.6),
    ('好评', '好评', 1.2),
    ('方便', '方便', 0.8),
    ('有用', '有用', 1.0),
    ('易用', '易用', 0.8),
    ('提升', '提升', 0.8),
    ('改善', '改善', 0.8),
    ('稳定', '稳定', 0.8),
    ('强大', '强大', 0.8),
    ('喜欢', '喜欢', 1.0),
    ('领先', '领先', 0.8),
)

_SENTIMENT_NEGATIVE_CUES = (
    ('under fire', 'under fire', 1.6),
    ('critic', '\\bcritic(?:s|ism)?\\b', 1.0),
    ('disgusting', '\\bdisgusting\\b', 1.5),
    ('bad', '\\bbad\\b', 1.0),
    ('worse', '\\bworse\\b', 1.0),
    ('risk', '\\brisk(?:s)?\\b', 0.8),
    ('unsafe', '\\bunsafe\\b', 1.5),
    ('fail', '\\bfail(?:ure|ed|ing)?\\b', 1.0),
    ('cut back', 'cut back', 1.2),
    ('concern', '\\bconcern(?:s)?\\b', 0.8),
    ('issue', '\\bissue(?:s)?\\b', 0.8),
    ('shutting down', '\\bshut(?:ting)? down\\b', 1.6),
    ('shutdown', '\\bshutdown\\b', 1.5),
    ('gave up', '\\bg(?:ive|ave) up\\b', 1.4),
    ('killed', '\\bkill(?:ed|ing)?\\b', 1.4),
    ('abandoned', '\\babandon(?:ed|ing)?\\b', 1.4),
    ('broken', '\\bbroken\\b', 1.2),
    ('buggy', '\\bbuggy\\b', 1.0),
    ('unstable', '\\bunstable\\b', 1.1),
    ('no longer works', 'no longer works', 1.4),
    ('does not work', "does(?:n't| not) work", 1.4),
    ('not worth', 'not worth', 1.2),
    ('争议', '争议', 1.0),
    ('批评', '批评', 1.0),
    ('糟糕', '糟糕', 1.2),
    ('风险', '风险', 0.8),
    ('问题', '问题', 0.8),
    ('担忧', '担忧', 0.8),
    ('失望', '失望', 1.0),
    ('翻车', '翻车', 1.2),
    ('裁员', '裁员', 1.0),
    ('下线', '下线', 1.5),
    ('停用', '停用', 1.3),
    ('放弃', '放弃', 1.3),
    ('砍掉', '砍掉', 1.3),
    ('不稳定', '不稳定', 1.0),
    ('不靠谱', '不靠谱', 1.1),
    ('不推荐', '不推荐', 1.2),
)

_SENTIMENT_NEGATED_NEGATIVE_CUES = (
    ('not bad', 'not bad', 1.0),
    ('not worse', 'not worse', 1.0),
    ('no problem', 'no problem', 1.0),
    ('no problems', 'no problems', 1.0),
    ('without issue', 'without issue', 0.8),
    ('without issues', 'without issues', 0.8),
    ('not terrible', 'not terrible', 1.1),
    ('not awful', 'not awful', 1.1),
    ('not broken', 'not broken', 1.0),
    ('not unstable', 'not unstable', 1.0),
    ('不差', '不差', 1.0),
    ('没问题', '没问题', 1.0),
    ('没有问题', '没有问题', 1.0),
    ('无问题', '无问题', 1.0),
    ('没那么差', '没那么差', 1.0),
    ('不算差', '不算差', 0.8),
)

_SENTIMENT_NEGATED_POSITIVE_CUES = (
    ('not good', 'not good', 1.0),
    ('not great', 'not great', 1.2),
    ('not helpful', 'not helpful', 1.0),
    ('not useful', 'not useful', 1.0),
    ('not better', 'not better', 0.8),
    ('not stable', 'not stable', 1.0),
    ('not reliable', 'not reliable', 1.0),
    ("can't recommend", "can't recommend", 1.2),
    ('cannot recommend', 'cannot recommend', 1.2),
    ("wouldn't recommend", "wouldn't recommend", 1.2),
    ('not recommended', 'not recommended', 1.2),
    ('不好', '不好', 1.0),
    ('不好用', '不好用', 1.2),
    ('不稳定', '不稳定', 1.0),
    ('不方便', '不方便', 1.0),
    ('没用', '没用', 1.0),
    ('不靠谱', '不靠谱', 1.1),
    ('不推荐', '不推荐', 1.2),
)

_SENTIMENT_INTENSIFIERS = (
    ('\\breally\\b', 1.2),
    ('\\bvery\\b', 1.2),
    ('\\bsuper\\b', 1.3),
    ('\\bextremely\\b', 1.5),
    ('\\bserious(?:ly)?\\b', 1.25),
    ('\\bmajor\\b', 1.2),
    ('\\bhuge\\b', 1.2),
    ('非常', 1.3),
    ('特别', 1.3),
    ('极其', 1.4),
    ('很', 1.1),
    ('太', 1.15),
)

_SENTIMENT_DOWNTONERS = (
    ('\\bslightly\\b', 0.7),
    ('\\bsomewhat\\b', 0.8),
    ('kind of', 0.75),
    ('a bit', 0.75),
    ('a little', 0.75),
    ('\\brelatively\\b', 0.85),
    ('有点', 0.75),
    ('有一点', 0.75),
    ('略微', 0.7),
    ('比较', 0.85),
    ('还算', 0.85),
)

_JOB_SKILL_PATTERNS = (
    ('Python', 'language', ('title', 'content_text', 'category', 'source_tag'), (r'\bpython\b',)),
    ('Django', 'framework', ('title', 'content_text', 'category', 'source_tag'), (r'\bdjango\b',)),
    ('Flask', 'framework', ('title', 'content_text', 'category', 'source_tag'), (r'\bflask\b',)),
    ('FastAPI', 'framework', ('title', 'content_text', 'category', 'source_tag'), (r'\bfastapi\b',)),
    ('DevOps', 'practice', ('title', 'content_text', 'category', 'source_tag'), (r'\bdevops\b',)),
    ('Cloud', 'domain', ('title', 'content_text', 'category', 'source_tag'), (r'\bcloud\b',)),
    ('Web', 'domain', ('title', 'content_text', 'category', 'source_tag'), (r'\bweb applications?\b', r'\bweb development\b', r'\bweb frameworks?\b', r'\bweb scrapers?\b')),
    ('Security', 'domain', ('title', 'content_text', 'category', 'source_tag'), (r'\bapplication security\b', r'\bcloud security\b', r'\bsecurity policies?\b', r'\bsecurity questionnaires?\b', r'\bsecurity best practices\b', r'\bsecurity requirements?\b', r'\bsecurity tooling\b', r'\bsecurity engineer(?:ing)?\b')),
    ('Backend', 'domain', ('title', 'content_text', 'category', 'source_tag'), (r'\bback[\s-]?end\b', r'\bbackend services?\b', r'\bbackend development\b')),
    ('Frontend', 'domain', ('title', 'content_text', 'category', 'source_tag'), (r'\bfront[\s-]?end\b', r'\bfrontend development\b', r'\bfrontend knowledge\b')),
    ('AWS', 'cloud', ('title', 'content_text', 'category', 'source_tag'), (r'\baws\b', r'amazon web services')),
    ('Azure', 'cloud', ('title', 'content_text', 'category', 'source_tag'), (r'\bazure\b',)),
    ('GCP', 'cloud', ('title', 'content_text', 'category', 'source_tag'), (r'\bgcp\b', r'google cloud')),
    ('Docker', 'tool', ('title', 'content_text', 'category', 'source_tag'), (r'\bdocker\b',)),
    ('Kubernetes', 'tool', ('title', 'content_text', 'category', 'source_tag'), (r'\bkubernetes\b',)),
    ('Terraform', 'tool', ('title', 'content_text', 'category', 'source_tag'), (r'\bterraform\b',)),
    ('Grafana', 'tool', ('title', 'content_text', 'category', 'source_tag'), (r'\bgrafana\b',)),
    ('CI/CD', 'practice', ('title', 'content_text', 'category', 'source_tag'), (r'\bci/cd\b', r'\bci cd\b')),
    ('Linux', 'platform', ('title', 'content_text', 'category', 'source_tag'), (r'\blinux\b',)),
    ('Unix', 'platform', ('title', 'content_text', 'category', 'source_tag'), (r'\bunix\b',)),
    ('Documentation', 'practice', ('title', 'content_text', 'category', 'source_tag'), (r'\bdocumentation\b', r'\bdocumenting\b', r'documentation-driven')),
    ('Monitoring', 'domain', ('title', 'content_text', 'category', 'source_tag'), (r'\bmonitoring\b',)),
    ('Visualization', 'domain', ('title', 'content_text', 'category', 'source_tag'), (r'\bvisualization\b',)),
    ('Federated Learning', 'domain', ('title', 'content_text', 'category', 'source_tag'), (r'federated learning',)),
    ('Open Source', 'practice', ('title', 'content_text', 'category', 'source_tag'), (r'open-source', r'open source')),
    ('APPFL', 'tool', ('title', 'content_text', 'category', 'source_tag'), (r'\bappfl\b',)),
    ('Big Data', 'domain', ('title', 'content_text', 'category', 'source_tag'), (r'big data',)),
    ('Performance', 'practice', ('title', 'content_text', 'category', 'source_tag'), (r'\bperformance tuning\b', r'\bperformance optimization\b', r'\bperformant\b', r'\bhigh-performance\b', r'\boptimi(?:s|z)e(?:d|s|ing)?\b[^.]{0,40}\bperformance\b')),
    ('Scalability', 'practice', ('title', 'content_text', 'category', 'source_tag'), (r'\bscalability\b', r'\bscalable\b')),
    ('Automation', 'practice', ('title', 'content_text', 'category', 'source_tag'), (r'\bautomation\b',)),
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
        sources = self._job_skill_sources(record)
        for skill_name, skill_type, fields, patterns in _JOB_SKILL_PATTERNS:
            if skill_name in matches:
                continue
            for field_name in fields:
                text = sources.get(field_name, '')
                lower_text = text.lower()
                if any(re.search(pattern, lower_text) for pattern in patterns):
                    matches[skill_name] = (skill_type, field_name)
                    break
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
                            "positive_share": round(int(row["positive_count"]) / max(int(row["post_count"]), 1), 4),
                            "neutral_share": round(int(row["neutral_count"]) / max(int(row["post_count"]), 1), 4),
                            "negative_share": round(int(row["negative_count"]) / max(int(row["post_count"]), 1), 4),
                            "sentiment_balance": round((int(row["positive_count"]) - int(row["negative_count"])) / max(int(row["post_count"]), 1), 4),
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
        candidate = title.strip()
        for pattern in (
            r'(?:产品版本)?升级公.*$',
            r'更新通告.*$',
            r'产品公告.*$',
            r'产品.*$',
            r'(?:部分型号)?正式停售公告.*$',
            r'正式停售公告.*$',
            r'停售公告.*$',
            r'正式停服公告.*$',
            r'停服公告.*$',
            r'公告.*$',
        ):
            candidate = re.sub(pattern, '', candidate).strip(' -—')
        candidate = re.sub(r'^奇安信集团\d{4}年\d{2}月', '', candidate).strip(' -—')
        candidate = self._normalize_project_candidate(candidate)
        if not candidate or '补丁库' in candidate:
            return None
        if not self._looks_like_company_project_name(candidate):
            return None
        return candidate if self._is_valid_company_project_candidate(candidate) else None

    def _normalize_project_candidate(self, value: str) -> str:
        candidate = ' '.join(str(value).replace('　', ' ').split())
        candidate = candidate.strip(" \t\r\n-:,.;[]<>'\"")
        return candidate.strip('—、。《》【】“”：，；')

    def _is_valid_company_project_candidate(self, candidate: str) -> bool:
        if not candidate or len(candidate) < 2 or len(candidate) > 80:
            return False
        if candidate in _COMPANY_NAME_STOPWORDS:
            return False
        if candidate.upper() in _COMPANY_PROJECT_TOKEN_STOPWORDS:
            return False
        if any(marker in candidate for marker in _COMPANY_PROJECT_NOISE_MARKERS):
            return False
        if '+' in candidate and not any(char.isdigit() for char in candidate):
            return False
        if candidate.isascii() and len(candidate.split()) >= 3:
            return False
        if any(marker in candidate for marker in _COMPANY_DOCUMENT_MARKERS):
            return False
        if _COMPANY_PROJECT_SENTENCE_PUNCTUATION.search(candidate):
            return False
        if len(candidate) > 18 and not re.search(r'[A-Za-z0-9-（）()]', candidate):
            return False
        if _COMPANY_PROJECT_MODEL_TOKEN_PATTERN.fullmatch(candidate):
            return False
        return True

    def _looks_like_company_project_name(self, candidate: str) -> bool:
        if _COMPANY_PROJECT_SENTENCE_PUNCTUATION.search(candidate):
            return False
        if candidate.isascii():
            return bool(re.search(r'[A-Z0-9-]', candidate))
        return any(marker in candidate for marker in _COMPANY_PROJECT_NAME_MARKERS)

    def _is_valid_company_project_token(self, token: str) -> bool:
        upper = token.upper()
        if upper in _COMPANY_PROJECT_TOKEN_STOPWORDS:
            return False
        if any(marker in token for marker in _COMPANY_PROJECT_NOISE_MARKERS):
            return False
        if _COMPANY_PROJECT_MODEL_TOKEN_PATTERN.fullmatch(token):
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
        signal_delta = positive_score_total - negative_score_total
        score = round(math.tanh(signal_delta / 2.5), 4)
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
            best_weight: float | None = None
            for match in re.finditer(pattern, text):
                adjusted_weight = float(weight) * self._sentiment_context_multiplier(text, match.start(), match.end())
                if best_weight is None or adjusted_weight > best_weight:
                    best_weight = adjusted_weight
            if best_weight is not None:
                matches.append({"label": label, "weight": round(float(best_weight), 4)})
        return matches

    def _sentiment_context_multiplier(self, text: str, start: int, end: int) -> float:
        window_start = max(0, start - 24)
        window_end = min(len(text), end + 12)
        context = text[window_start:window_end]
        intensifier_scale = 1.0
        downtoner_scale = 1.0
        for pattern, factor in _SENTIMENT_INTENSIFIERS:
            if re.search(pattern, context):
                intensifier_scale = max(intensifier_scale, float(factor))
        for pattern, factor in _SENTIMENT_DOWNTONERS:
            if re.search(pattern, context):
                downtoner_scale = min(downtoner_scale, float(factor))
        return round(intensifier_scale * downtoner_scale, 4)

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