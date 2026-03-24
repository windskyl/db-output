from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from app.models.records import NormalizedRecord, RunArtifacts
from app.writers.sqlite_writer import SQLiteWriter


class SQLiteWriterTests(unittest.TestCase):
    def test_finance_records_are_written_to_metrics_and_instruments_tables(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            base = Path(temp_dir)
            artifacts = RunArtifacts(
                task_id='finance-ibm-earnings-001',
                domain='finance',
                raw_file=str(base / 'raw.jsonl.gz'),
                normalized_file=str(base / 'normalized.jsonl.gz'),
                sqlite_file=str(base / 'result.sqlite'),
                quality_report_file=str(base / 'quality_report.json'),
                run_report_file=str(base / 'run_report.json'),
            )
            record = NormalizedRecord(
                task_id='finance-ibm-earnings-001',
                domain='finance',
                record_id='finance-ibm-earnings-001-alpha_vantage_demo_earnings-1',
                dedupe_key='alpha_vantage_demo_earnings:2026-01-29:Quarterly Earnings',
                source_id='alpha_vantage_demo_earnings',
                source_type='public_finance_api',
                source_label='Alpha Vantage Demo Earnings',
                source_tag='quarterly_earnings',
                source_url='https://www.alphavantage.co/query?function=EARNINGS&symbol=IBM&apikey=demo',
                published_at='2026-01-29',
                collected_at='2026-03-19T10:00:00+00:00',
                primary_entity='IBM',
                topic_tags=['financial_report'],
                title='Quarterly Earnings',
                content_text='3.92',
                relevance_score=0.7,
                extra={
                    'metric_name': 'reported_eps',
                    'metric_value': '3.92',
                    'estimated_eps': '3.75',
                    'surprise': '0.17',
                    'surprise_percentage': '4.5333',
                    'report_time': 'post-market',
                    'reported_date': '2026-01-29',
                    'fiscal_date_ending': '2025-12-31',
                    'symbol': 'IBM',
                    'market': 'NYSE',
                    'currency': 'USD',
                },
            )
            run_summary = {
                'task_id': 'finance-ibm-earnings-001',
                'domain': 'finance',
                'scenario_template': 'investment_financial_report_basic',
                'status': 'success',
                'raw_count': 1,
                'normalized_count': 1,
                'output_count': 1,
                'quality_report': {'task_id': 'finance-ibm-earnings-001', 'domain': 'finance', 'output_count': 1},
            }

            SQLiteWriter().write(run_summary, [record], artifacts)

            connection = sqlite3.connect(artifacts.sqlite_file)
            try:
                event_count = connection.execute('SELECT COUNT(*) FROM core_finance_events').fetchone()[0]
                metric_row = connection.execute(
                    'SELECT record_id, primary_entity, metric_name, metric_value, source_id, extra_json FROM core_finance_metrics'
                ).fetchone()
                instrument_row = connection.execute(
                    'SELECT instrument_id, primary_entity, symbol, instrument_name, market, currency, source_id FROM core_finance_instruments'
                ).fetchone()
            finally:
                connection.close()

            self.assertEqual(event_count, 1)
            self.assertEqual(metric_row[0], record.record_id)
            self.assertEqual(metric_row[1], 'IBM')
            self.assertEqual(metric_row[2], 'reported_eps')
            self.assertEqual(metric_row[3], '3.92')
            self.assertEqual(metric_row[4], 'alpha_vantage_demo_earnings')
            self.assertEqual(json.loads(metric_row[5])['estimated_eps'], '3.75')

            self.assertEqual(instrument_row[0], 'IBM')
            self.assertEqual(instrument_row[1], 'IBM')
            self.assertEqual(instrument_row[2], 'IBM')
            self.assertEqual(instrument_row[3], 'IBM')
            self.assertEqual(instrument_row[4], 'NYSE')
            self.assertEqual(instrument_row[5], 'USD')
            self.assertEqual(instrument_row[6], 'alpha_vantage_demo_earnings')

    def test_jobs_records_are_written_to_skills_table(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            base = Path(temp_dir)
            artifacts = RunArtifacts(
                task_id='job-python-org-001',
                domain='jobs',
                raw_file=str(base / 'raw.jsonl.gz'),
                normalized_file=str(base / 'normalized.jsonl.gz'),
                sqlite_file=str(base / 'result.sqlite'),
                quality_report_file=str(base / 'quality_report.json'),
                run_report_file=str(base / 'run_report.json'),
            )
            records = [
                NormalizedRecord(
                    task_id='job-python-org-001',
                    domain='jobs',
                    record_id='job-python-org-001-python_org_jobs-1',
                    dedupe_key='python_org_jobs:2026-03-06:1',
                    source_id='python_org_jobs',
                    source_type='public_jobs_board',
                    source_label='Python.org Jobs',
                    source_tag='',
                    source_url='https://www.python.org/jobs/8052/',
                    published_at='2026-03-06',
                    collected_at='2026-03-20T10:00:00+00:00',
                    primary_entity='DivIHN Integration Inc',
                    topic_tags=['backend'],
                    title='Senior Python Developer/DevOps Engineer',
                    content_text='Back end , Cloud , DevOps, Security',
                    relevance_score=0.7,
                    extra={'category': 'Developer / Engineer'},
                ),
                NormalizedRecord(
                    task_id='job-python-org-001',
                    domain='jobs',
                    record_id='job-python-org-001-python_org_jobs_rss-2',
                    dedupe_key='python_org_jobs_rss:2026-03-07:2',
                    source_id='python_org_jobs_rss',
                    source_type='public_jobs_rss',
                    source_label='Python.org Jobs RSS',
                    source_tag='',
                    source_url='https://www.python.org/jobs/8050/',
                    published_at='2026-03-07',
                    collected_at='2026-03-20T10:01:00+00:00',
                    primary_entity='Six Feet Up',
                    topic_tags=['backend'],
                    title='Senior Python Developer',
                    content_text='Proficient in Django, Flask, AWS, Azure, GCP, Docker, Kubernetes, Terraform and Grafana with CI/CD automation.',
                    relevance_score=0.72,
                    extra={'category': 'Developer / Engineer'},
                ),
            ]
            run_summary = {
                'task_id': 'job-python-org-001',
                'domain': 'jobs',
                'scenario_template': 'job_hunt_engineering_basic',
                'status': 'success',
                'raw_count': 2,
                'normalized_count': 2,
                'output_count': 2,
                'quality_report': {'task_id': 'job-python-org-001', 'domain': 'jobs', 'output_count': 2},
            }

            SQLiteWriter().write(run_summary, records, artifacts)

            connection = sqlite3.connect(artifacts.sqlite_file)
            try:
                posting_count = connection.execute('SELECT COUNT(*) FROM core_jobs_postings').fetchone()[0]
                skill_rows = connection.execute(
                    'SELECT record_id, skill_name, skill_type, evidence_field FROM core_jobs_skills ORDER BY record_id, skill_name'
                ).fetchall()
            finally:
                connection.close()

            self.assertEqual(posting_count, 2)
            skill_map = {(row[0], row[1]): (row[2], row[3]) for row in skill_rows}
            self.assertIn(('job-python-org-001-python_org_jobs-1', 'Python'), skill_map)
            self.assertIn(('job-python-org-001-python_org_jobs-1', 'DevOps'), skill_map)
            self.assertIn(('job-python-org-001-python_org_jobs-1', 'Cloud'), skill_map)
            self.assertIn(('job-python-org-001-python_org_jobs-1', 'Backend'), skill_map)
            self.assertEqual(skill_map[('job-python-org-001-python_org_jobs-1', 'Python')], ('language', 'title'))
            self.assertEqual(skill_map[('job-python-org-001-python_org_jobs-1', 'Cloud')], ('domain', 'content_text'))

            self.assertIn(('job-python-org-001-python_org_jobs_rss-2', 'Django'), skill_map)
            self.assertIn(('job-python-org-001-python_org_jobs_rss-2', 'Flask'), skill_map)
            self.assertIn(('job-python-org-001-python_org_jobs_rss-2', 'AWS'), skill_map)
            self.assertIn(('job-python-org-001-python_org_jobs_rss-2', 'Docker'), skill_map)
            self.assertIn(('job-python-org-001-python_org_jobs_rss-2', 'Kubernetes'), skill_map)
            self.assertIn(('job-python-org-001-python_org_jobs_rss-2', 'Terraform'), skill_map)
            self.assertIn(('job-python-org-001-python_org_jobs_rss-2', 'Grafana'), skill_map)
            self.assertIn(('job-python-org-001-python_org_jobs_rss-2', 'CI/CD'), skill_map)
    def test_company_intel_records_are_aggregated_into_profile_and_project_tables(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            base = Path(temp_dir)
            artifacts = RunArtifacts(
                task_id='company-qianxin-001',
                domain='company_intel',
                raw_file=str(base / 'raw.jsonl.gz'),
                normalized_file=str(base / 'normalized.jsonl.gz'),
                sqlite_file=str(base / 'result.sqlite'),
                quality_report_file=str(base / 'quality_report.json'),
                run_report_file=str(base / 'run_report.json'),
            )
            records = [
                NormalizedRecord(
                    task_id='company-qianxin-001',
                    domain='company_intel',
                    record_id='company-qianxin-001-qianxin-news-1',
                    dedupe_key='qianxin_news:2026-03-16:news-1',
                    source_id='qianxin_news',
                    source_type='official_company_news',
                    source_label='Qianxin News',
                    source_tag='',
                    source_url='https://www.qianxin.com/news/detail?news_id=14628',
                    published_at='2026-03-16',
                    collected_at='2026-03-20T10:00:00+00:00',
                    primary_entity='\u5947\u5b89\u4fe1',
                    topic_tags=['product_update', 'tech_blog'],
                    title='\u5947\u5b89\u4fe1\u53d1\u5e03\u201c\u9f99\u867e\u5b89\u5168\u4f34\u4fa3\u201d\uff0c\u7834\u89e3\u4f01\u4e1a\u201c\u60f3\u7528\u4e0d\u6562\u7528\u201d\u96be\u9898',
                    content_text='\u4f9d\u6258 OpenClaw \u4e0e SAFESKILL \u5e73\u53f0\u63d0\u4f9b\u65b0\u7684\u667a\u80fd\u4f53\u5b89\u5168\u65b9\u6848\u3002',
                    relevance_score=0.8,
                    extra={},
                ),
                NormalizedRecord(
                    task_id='company-qianxin-001',
                    domain='company_intel',
                    record_id='company-qianxin-001-qianxin-report-2',
                    dedupe_key='qianxin_report:2025-12-11:report-2',
                    source_id='qianxin_report',
                    source_type='official_company_report',
                    source_label='Qianxin Reports',
                    source_tag='\u8d5b\u8fea\u987e\u95ee',
                    source_url='https://www.qianxin.com/report/detail/rid/102',
                    published_at='2025-12-11',
                    collected_at='2026-03-20T10:01:00+00:00',
                    primary_entity='\u5947\u5b89\u4fe1',
                    topic_tags=['company_profile'],
                    title='\u4e2d\u56fd\u5a01\u80c1\u60c5\u62a5\u5e02\u573a\u7814\u7a76\u62a5\u544a\uff082025\uff09',
                    content_text='\u62a5\u544a\u663e\u793a\u5947\u5b89\u4fe1\u96c6\u56e2\u5728\u5a01\u80c1\u60c5\u62a5\u9886\u57df\u6301\u7eed\u9886\u8dd1\u3002',
                    relevance_score=0.78,
                    extra={},
                ),
                NormalizedRecord(
                    task_id='company-qianxin-001',
                    domain='company_intel',
                    record_id='company-qianxin-001-qianxin-update-3',
                    dedupe_key='qianxin_update:2026-01-19:update-3',
                    source_id='qianxin_update',
                    source_type='official_company_update',
                    source_label='Qianxin Product Updates',
                    source_tag='\u5347\u7ea7\u516c\u544a',
                    source_url='https://static01-www.qianxin.com/qaxweb/example.pdf',
                    published_at='2026-01-19',
                    collected_at='2026-03-20T10:02:00+00:00',
                    primary_entity='\u5947\u5b89\u4fe1',
                    topic_tags=['product_update'],
                    title='\u7f51\u795eSecSSL3600\u5b89\u5168\u63a5\u5165\u7f51\u5173\u7cfb\u7edfV5.0\u4ea7\u54c1\u7248\u672c\u5347\u7ea7\u516c\u544a',
                    content_text='\u5347\u7ea7\u516c\u544a',
                    relevance_score=0.77,
                    extra={},
                ),
            ]
            run_summary = {
                'task_id': 'company-qianxin-001',
                'domain': 'company_intel',
                'scenario_template': 'company_due_diligence',
                'status': 'success',
                'raw_count': 3,
                'normalized_count': 3,
                'output_count': 3,
                'quality_report': {'task_id': 'company-qianxin-001', 'domain': 'company_intel', 'output_count': 3},
            }

            SQLiteWriter().write(run_summary, records, artifacts)

            connection = sqlite3.connect(artifacts.sqlite_file)
            try:
                event_count = connection.execute('SELECT COUNT(*) FROM core_company_events').fetchone()[0]
                profile_row = connection.execute(
                    'SELECT company_id, company_name, evidence_count, first_published_at, last_published_at, sample_title, source_ids_json '
                    'FROM core_company_profiles'
                ).fetchone()
                project_rows = connection.execute(
                    'SELECT project_name, project_type, mention_count, sample_title FROM core_company_projects ORDER BY project_name'
                ).fetchall()
            finally:
                connection.close()

            self.assertEqual(event_count, 3)
            self.assertEqual(profile_row[0], '\u5947\u5b89\u4fe1')
            self.assertEqual(profile_row[1], '\u5947\u5b89\u4fe1')
            self.assertEqual(profile_row[2], 3)
            self.assertEqual(profile_row[3], '2025-12-11')
            self.assertEqual(profile_row[4], '2026-03-16')
            self.assertEqual(profile_row[5], '\u4e2d\u56fd\u5a01\u80c1\u60c5\u62a5\u5e02\u573a\u7814\u7a76\u62a5\u544a\uff082025\uff09')
            self.assertEqual(json.loads(profile_row[6]), ['qianxin_news', 'qianxin_report', 'qianxin_update'])

            project_map = {row[0]: row[1:] for row in project_rows}
            self.assertIn('\u9f99\u867e\u5b89\u5168\u4f34\u4fa3', project_map)
            self.assertEqual(project_map['\u9f99\u867e\u5b89\u5168\u4f34\u4fa3'][0], 'product_or_platform')
            self.assertEqual(project_map['\u9f99\u867e\u5b89\u5168\u4f34\u4fa3'][1], 1)
            self.assertEqual(project_map['\u9f99\u867e\u5b89\u5168\u4f34\u4fa3'][2], '\u5947\u5b89\u4fe1\u53d1\u5e03\u201c\u9f99\u867e\u5b89\u5168\u4f34\u4fa3\u201d\uff0c\u7834\u89e3\u4f01\u4e1a\u201c\u60f3\u7528\u4e0d\u6562\u7528\u201d\u96be\u9898')

            self.assertIn('OpenClaw', project_map)
            self.assertIn('SAFESKILL', project_map)
            self.assertIn('\u7f51\u795eSecSSL3600\u5b89\u5168\u63a5\u5165\u7f51\u5173\u7cfb\u7edfV5.0', project_map)
            self.assertEqual(project_map['\u7f51\u795eSecSSL3600\u5b89\u5168\u63a5\u5165\u7f51\u5173\u7cfb\u7edfV5.0'][0], 'product_update')

    def test_rewriting_same_sqlite_file_replaces_previous_rows(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            base = Path(temp_dir)
            artifacts = RunArtifacts(
                task_id='job-sample-001',
                domain='jobs',
                raw_file=str(base / 'raw.jsonl.gz'),
                normalized_file=str(base / 'normalized.jsonl.gz'),
                sqlite_file=str(base / 'result.sqlite'),
                quality_report_file=str(base / 'quality_report.json'),
                run_report_file=str(base / 'run_report.json'),
            )
            first_records = [
                NormalizedRecord(
                    task_id='job-sample-001',
                    domain='jobs',
                    record_id='job-sample-001-source-1',
                    dedupe_key='source:1',
                    source_id='source',
                    source_type='public_jobs_board',
                    source_label='Example',
                    source_tag='engineering',
                    source_url='https://example.com/jobs/1',
                    published_at='2026-03-18',
                    collected_at='2026-03-20T10:00:00+00:00',
                    primary_entity='Acme',
                    topic_tags=['backend'],
                    title='Backend Engineer',
                    content_text='Backend work',
                    relevance_score=0.7,
                    extra={},
                ),
                NormalizedRecord(
                    task_id='job-sample-001',
                    domain='jobs',
                    record_id='job-sample-001-source-2',
                    dedupe_key='source:2',
                    source_id='source',
                    source_type='public_jobs_board',
                    source_label='Example',
                    source_tag='engineering',
                    source_url='https://example.com/jobs/2',
                    published_at='2026-03-19',
                    collected_at='2026-03-20T10:01:00+00:00',
                    primary_entity='Acme',
                    topic_tags=['backend'],
                    title='Data Engineer',
                    content_text='Data work',
                    relevance_score=0.7,
                    extra={},
                ),
            ]
            second_records = [first_records[0]]
            run_summary = {
                'task_id': 'job-sample-001',
                'domain': 'jobs',
                'scenario_template': 'job_hunt_engineering_basic',
                'status': 'success',
                'raw_count': 2,
                'normalized_count': 2,
                'output_count': 2,
                'quality_report': {'task_id': 'job-sample-001', 'domain': 'jobs', 'output_count': 2},
            }
            writer = SQLiteWriter()
            writer.write(run_summary, first_records, artifacts)
            writer.write({**run_summary, 'raw_count': 1, 'normalized_count': 1, 'output_count': 1}, second_records, artifacts)

            connection = sqlite3.connect(artifacts.sqlite_file)
            try:
                row_count = connection.execute('SELECT COUNT(*) FROM core_jobs_postings').fetchone()[0]
            finally:
                connection.close()

            self.assertEqual(row_count, 1)

    def test_public_sentiment_records_are_aggregated_into_topic_table(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            base = Path(temp_dir)
            artifacts = RunArtifacts(
                task_id='public-sentiment-openai-001',
                domain='public_sentiment',
                raw_file=str(base / 'raw.jsonl.gz'),
                normalized_file=str(base / 'normalized.jsonl.gz'),
                sqlite_file=str(base / 'result.sqlite'),
                quality_report_file=str(base / 'quality_report.json'),
                run_report_file=str(base / 'run_report.json'),
            )
            records = [
                NormalizedRecord(
                    task_id='public-sentiment-openai-001',
                    domain='public_sentiment',
                    record_id='public-sentiment-openai-001-hn-1',
                    dedupe_key='hn:2026-03-18:OpenAI API rollout',
                    source_id='hn_algolia_company_story_search',
                    source_type='public_forum_api',
                    source_label='HN Algolia',
                    source_tag='story',
                    source_url='https://news.ycombinator.com/item?id=1',
                    published_at='2026-03-18',
                    collected_at='2026-03-20T10:00:00+00:00',
                    primary_entity='OpenAI',
                    topic_tags=['tech_stack_engineering'],
                    title='OpenAI shipped a great API update',
                    content_text='Developers love the helpful SDK improvements and better docs.',
                    relevance_score=0.8,
                    extra={'matched_topics': ['tech_stack_engineering']},
                ),
                NormalizedRecord(
                    task_id='public-sentiment-openai-001',
                    domain='public_sentiment',
                    record_id='public-sentiment-openai-001-hn-2',
                    dedupe_key='hn:2026-03-19:OpenAI leadership memo',
                    source_id='hn_algolia_company_story_search',
                    source_type='public_forum_api',
                    source_label='HN Algolia',
                    source_tag='story',
                    source_url='https://news.ycombinator.com/item?id=2',
                    published_at='2026-03-19',
                    collected_at='2026-03-20T10:05:00+00:00',
                    primary_entity='OpenAI',
                    topic_tags=['tech_stack_engineering', 'management_culture'],
                    title='OpenAI is under fire from critics again',
                    content_text='Critics call the latest remarks bad and raise serious concerns.',
                    relevance_score=0.82,
                    extra={'matched_topics': ['tech_stack_engineering', 'management_culture']},
                ),
            ]
            run_summary = {
                'task_id': 'public-sentiment-openai-001',
                'domain': 'public_sentiment',
                'scenario_template': 'company_sentiment_tracking_basic',
                'status': 'success',
                'raw_count': 2,
                'normalized_count': 2,
                'output_count': 2,
                'quality_report': {'task_id': 'public-sentiment-openai-001', 'domain': 'public_sentiment', 'output_count': 2},
            }

            SQLiteWriter().write(run_summary, records, artifacts)

            connection = sqlite3.connect(artifacts.sqlite_file)
            try:
                post_count = connection.execute('SELECT COUNT(*) FROM core_sentiment_posts').fetchone()[0]
                post_rows = connection.execute(
                    'SELECT record_id, sentiment_label, sentiment_score FROM core_sentiment_posts ORDER BY record_id'
                ).fetchall()
                topic_rows = connection.execute(
                    'SELECT primary_entity, topic_name, post_count, positive_count, neutral_count, negative_count, average_sentiment_score, sample_title, source_ids_json '
                    'FROM core_sentiment_topics ORDER BY topic_name'
                ).fetchall()
            finally:
                connection.close()

            self.assertEqual(post_count, 2)
            self.assertEqual(post_rows[0][0], 'public-sentiment-openai-001-hn-1')
            self.assertEqual(post_rows[0][1], 'positive')
            self.assertGreater(post_rows[0][2], 0.0)
            self.assertEqual(post_rows[1][0], 'public-sentiment-openai-001-hn-2')
            self.assertEqual(post_rows[1][1], 'negative')
            self.assertLess(post_rows[1][2], 0.0)

            self.assertEqual(len(topic_rows), 2)
            self.assertEqual(topic_rows[0][0], 'OpenAI')
            self.assertEqual(topic_rows[0][1], 'management_culture')
            self.assertEqual(topic_rows[0][2], 1)
            self.assertEqual(topic_rows[0][3], 0)
            self.assertEqual(topic_rows[0][4], 0)
            self.assertEqual(topic_rows[0][5], 1)
            self.assertLess(topic_rows[0][6], 0.0)
            self.assertEqual(topic_rows[0][7], 'OpenAI is under fire from critics again')
            self.assertEqual(json.loads(topic_rows[0][8]), ['hn_algolia_company_story_search'])

            self.assertEqual(topic_rows[1][0], 'OpenAI')
            self.assertEqual(topic_rows[1][1], 'tech_stack_engineering')
            self.assertEqual(topic_rows[1][2], 2)
            self.assertEqual(topic_rows[1][3], 1)
            self.assertEqual(topic_rows[1][4], 0)
            self.assertEqual(topic_rows[1][5], 1)
            self.assertEqual(topic_rows[1][6], 0.0)
            self.assertEqual(topic_rows[1][7], 'OpenAI is under fire from critics again')
            self.assertEqual(json.loads(topic_rows[1][8]), ['hn_algolia_company_story_search'])


if __name__ == '__main__':
    unittest.main()