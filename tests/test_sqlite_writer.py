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
    def test_jobs_skill_extraction_filters_broad_noise_but_keeps_specific_phrases(self) -> None:
        writer = SQLiteWriter()
        noisy_record = NormalizedRecord(
            task_id='job-skill-noise-001',
            domain='jobs',
            record_id='noise',
            dedupe_key='noise',
            source_id='jobs',
            source_type='public_jobs_board',
            source_label='Jobs Board',
            source_tag='',
            source_url='https://example.com/noise',
            published_at='2026-03-31',
            collected_at='2026-03-31T00:00:00+00:00',
            primary_entity='Example Co',
            topic_tags=['backend'],
            title='Senior Software Engineer',
            content_text='Build a SaaS web platform, collaborate with customer support, and improve reliability, performance, and security across the product.',
            relevance_score=0.7,
            extra={'category': 'Software Engineering'},
        )
        precise_record = NormalizedRecord(
            task_id='job-skill-noise-001',
            domain='jobs',
            record_id='precise',
            dedupe_key='precise',
            source_id='jobs',
            source_type='public_jobs_board',
            source_label='Jobs Board',
            source_tag='',
            source_url='https://example.com/precise',
            published_at='2026-03-31',
            collected_at='2026-03-31T00:00:00+00:00',
            primary_entity='Example Co',
            topic_tags=['backend'],
            title='Senior Backend Engineer',
            content_text='Build backend services, maintain security policies, and do performance tuning for web applications running on AWS.',
            relevance_score=0.7,
            extra={'category': 'Software Engineering'},
        )

        noisy_skills = {name for name, _, _ in writer._extract_job_skills(noisy_record)}
        precise_skills = {name for name, _, _ in writer._extract_job_skills(precise_record)}

        self.assertNotIn('Support', noisy_skills)
        self.assertNotIn('Web', noisy_skills)
        self.assertNotIn('Security', noisy_skills)
        self.assertNotIn('Performance', noisy_skills)

        self.assertIn('Backend', precise_skills)
        self.assertIn('Web', precise_skills)
        self.assertIn('Security', precise_skills)
        self.assertIn('Performance', precise_skills)
        self.assertIn('AWS', precise_skills)

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
            self.assertNotIn('\u7f51\u795eSecSSL3600\u5b89\u5168\u63a5\u5165\u7f51\u5173\u7cfb\u7edfV5.0\u4ea7\u54c1\u7248\u672c\u5347\u7ea7\u516c\u544a', project_map)

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
    def test_company_intel_project_extraction_filters_media_article_and_announcement_noise(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            base = Path(temp_dir)
            artifacts = RunArtifacts(
                task_id='company-qianxin-noise-001',
                domain='company_intel',
                raw_file=str(base / 'raw.jsonl.gz'),
                normalized_file=str(base / 'normalized.jsonl.gz'),
                sqlite_file=str(base / 'result.sqlite'),
                quality_report_file=str(base / 'quality_report.json'),
                run_report_file=str(base / 'run_report.json'),
            )
            records = [
                NormalizedRecord(
                    task_id='company-qianxin-noise-001',
                    domain='company_intel',
                    record_id='company-qianxin-noise-001-news-1',
                    dedupe_key='qianxin_news:2026-03-10:noise-1',
                    source_id='qianxin_news',
                    source_type='official_company_news',
                    source_label='Qianxin News',
                    source_tag='',
                    source_url='https://www.qianxin.com/news/detail?news_id=1',
                    published_at='2026-03-10',
                    collected_at='2026-03-20T10:00:00+00:00',
                    primary_entity='\u5947\u5b89\u4fe1',
                    topic_tags=['tech_blog'],
                    title='\u300a\u4e2d\u56fd\u4f01\u4e1a\u5bb6\u300b\u72ec\u5bb6\u5bf9\u8bdd\u9f50\u5411\u4e1c\uff1a\u4e0d\u60f3\u88ab\u6dd8\u6c70\uff0c\u5c31\u8981\u62e5\u62b1AI',
                    content_text='\u8fd9\u662f\u4e00\u7bc7\u4ee5\u89c2\u70b9\u4e3a\u4e3b\u7684\u5a92\u4f53\u6587\u7ae0\u3002',
                    relevance_score=0.7,
                    extra={},
                ),
                NormalizedRecord(
                    task_id='company-qianxin-noise-001',
                    domain='company_intel',
                    record_id='company-qianxin-noise-001-news-2',
                    dedupe_key='qianxin_news:2026-03-11:good-2',
                    source_id='qianxin_news',
                    source_type='official_company_news',
                    source_label='Qianxin News',
                    source_tag='',
                    source_url='https://www.qianxin.com/news/detail?news_id=2',
                    published_at='2026-03-11',
                    collected_at='2026-03-20T10:01:00+00:00',
                    primary_entity='\u5947\u5b89\u4fe1',
                    topic_tags=['product_update', 'tech_blog'],
                    title='\u5947\u5b89\u4fe1\u53d1\u5e03\u201c\u9f99\u867e\u5b89\u5168\u4f34\u4fa3\u201d\uff0c\u7834\u89e3\u4f01\u4e1a\u201c\u60f3\u7528\u4e0d\u6562\u7528\u201d\u96be\u9898',
                    content_text='OpenClaw \u4e0e SAFESKILL \u5e73\u53f0\u63d0\u4f9b\u65b0\u7684\u667a\u80fd\u4f53\u5b89\u5168\u65b9\u6848\u3002',
                    relevance_score=0.8,
                    extra={},
                ),
                NormalizedRecord(
                    task_id='company-qianxin-noise-001',
                    domain='company_intel',
                    record_id='company-qianxin-noise-001-news-3',
                    dedupe_key='qianxin_news:2026-03-12:good-3',
                    source_id='qianxin_news',
                    source_type='official_company_news',
                    source_label='Qianxin News',
                    source_tag='',
                    source_url='https://www.qianxin.com/news/detail?news_id=3',
                    published_at='2026-03-12',
                    collected_at='2026-03-20T10:02:00+00:00',
                    primary_entity='\u5947\u5b89\u4fe1',
                    topic_tags=['product_update', 'tech_blog'],
                    title='\u5947\u5b89\u4fe1\u53d1\u5e03\u4ee3\u7801\u5b89\u5168\u667a\u80fd\u4f53\uff0c\u6253\u9020\u201c\u4e13\u5bb6\u7ea7\u5927\u8111+\u591a\u667a\u80fd\u4f53\u534f\u540c\u201d\u95ed\u73af',
                    content_text='QcodeAgents \u4e3a\u4f01\u4e1a\u63d0\u4f9b\u5168\u573a\u666f\u667a\u80fd\u4f53\u5b89\u5168\u80fd\u529b\u3002',
                    relevance_score=0.8,
                    extra={},
                ),
                NormalizedRecord(
                    task_id='company-qianxin-noise-001',
                    domain='company_intel',
                    record_id='company-qianxin-noise-001-news-4',
                    dedupe_key='qianxin_news:2026-03-13:good-4',
                    source_id='qianxin_news',
                    source_type='official_company_news',
                    source_label='Qianxin News',
                    source_tag='',
                    source_url='https://www.qianxin.com/news/detail?news_id=4',
                    published_at='2026-03-13',
                    collected_at='2026-03-20T10:03:00+00:00',
                    primary_entity='\u5947\u5b89\u4fe1',
                    topic_tags=['tech_blog'],
                    title='OpenClaw \u5b89\u5168\u98ce\u9669\u6392\u67e5\u6307\u5357\uff1a\u5728\u6548\u7387\u4e0e\u5b89\u5168\u4e4b\u95f4\u5bfb\u627e\u5e73\u8861',
                    content_text='GitHubAdvisoryData \u63d0\u4f9b\u4e86\u5f00\u6e90\u6f0f\u6d1e\u60c5\u62a5\uff0cOpenClaw \u63d0\u4f9b\u98ce\u9669\u6392\u67e5\u80fd\u529b\u3002',
                    relevance_score=0.78,
                    extra={},
                ),
                NormalizedRecord(
                    task_id='company-qianxin-noise-001',
                    domain='company_intel',
                    record_id='company-qianxin-noise-001-news-5',
                    dedupe_key='qianxin_news:2026-03-14:noise-5',
                    source_id='qianxin_news',
                    source_type='official_company_news',
                    source_label='Qianxin News',
                    source_tag='',
                    source_url='https://www.qianxin.com/news/detail?news_id=5',
                    published_at='2026-03-14',
                    collected_at='2026-03-20T10:04:00+00:00',
                    primary_entity='\u5947\u5b89\u4fe1',
                    topic_tags=['product_update', 'tech_blog'],
                    title='OpenClaw\u7206\u706b\uff0cAI\u667a\u80fd\u4f53\u6570\u636e\u3001\u5185\u5bb9\u3001\u6743\u9650\u4e09\u5927\u98ce\u9669\u5982\u4f55\u515c\u5e95\uff1f',
                    content_text='OpenClaw \u8ba9\u4f01\u4e1a\u80fd\u591f\u770b\u6e05\u6570\u636e\u4e0e\u6743\u9650\u98ce\u9669\u3002',
                    relevance_score=0.77,
                    extra={},
                ),
                NormalizedRecord(
                    task_id='company-qianxin-noise-001',
                    domain='company_intel',
                    record_id='company-qianxin-noise-001-news-6',
                    dedupe_key='qianxin_news:2026-03-15:noise-6',
                    source_id='qianxin_news',
                    source_type='official_company_news',
                    source_label='Qianxin News',
                    source_tag='',
                    source_url='https://www.qianxin.com/news/detail?news_id=6',
                    published_at='2026-03-15',
                    collected_at='2026-03-20T10:05:00+00:00',
                    primary_entity='\u5947\u5b89\u4fe1',
                    topic_tags=['company_profile', 'tech_blog'],
                    title='IDC\u6700\u65b0\u62a5\u544a\uff1a\u5947\u5b89\u4fe1\u9886\u8dd1\u201cAI+\u5b89\u5168\u201d\u53cc\u8d5b\u9053\uff0c\u8986\u76d6\u9886\u57df\u518d\u521b\u65b0\u9ad8',
                    content_text='IDCMarketGlance\uff1a\u4e2d\u56fd\u5b89\u5168\u667a\u80fd\u4f53\uff0c2026Q1\u3002',
                    relevance_score=0.76,
                    extra={},
                ),
                NormalizedRecord(
                    task_id='company-qianxin-noise-001',
                    domain='company_intel',
                    record_id='company-qianxin-noise-001-update-7',
                    dedupe_key='qianxin_update:2026-03-16:update-7',
                    source_id='qianxin_update',
                    source_type='official_company_update',
                    source_label='Qianxin Product Updates',
                    source_tag='\u5347\u7ea7\u516c\u544a',
                    source_url='https://www.qianxin.com/update/detail?update_id=7',
                    published_at='2026-03-16',
                    collected_at='2026-03-20T10:06:00+00:00',
                    primary_entity='\u5947\u5b89\u4fe1',
                    topic_tags=['product_update'],
                    title='\u5947\u5b89\u4fe1\u7f51\u795e\u7f51\u7edc\u5b89\u5168\u5ba1\u8ba1\u7cfb\u7edfV7.0\u4ea7\u54c1NSA-FB-L\u578b\u53f7\u6b63\u5f0f\u505c\u552e\u516c\u544a',
                    content_text='\u505c\u552e\u516c\u544a',
                    relevance_score=0.77,
                    extra={},
                ),
                NormalizedRecord(
                    task_id='company-qianxin-noise-001',
                    domain='company_intel',
                    record_id='company-qianxin-noise-001-update-8',
                    dedupe_key='qianxin_update:2026-03-17:update-8',
                    source_id='qianxin_update',
                    source_type='official_company_update',
                    source_label='Qianxin Product Updates',
                    source_tag='\u5347\u7ea7\u516c\u544a',
                    source_url='https://www.qianxin.com/update/detail?update_id=8',
                    published_at='2026-03-17',
                    collected_at='2026-03-20T10:07:00+00:00',
                    primary_entity='\u5947\u5b89\u4fe1',
                    topic_tags=['product_update'],
                    title='\u5b89\u5168\u7f16\u6392\u81ea\u52a8\u5316\u4e0e\u54cd\u5e94\u7cfb\u7edf\uff08SOAR\uff09\u4ea7\u54c1\u6b63\u5f0f\u505c\u552e\u516c\u544a',
                    content_text='\u505c\u552e\u516c\u544a',
                    relevance_score=0.77,
                    extra={},
                ),
            ]
            run_summary = {
                'task_id': 'company-qianxin-noise-001',
                'domain': 'company_intel',
                'scenario_template': 'company_due_diligence',
                'status': 'success',
                'raw_count': 8,
                'normalized_count': 8,
                'output_count': 8,
                'quality_report': {'task_id': 'company-qianxin-noise-001', 'domain': 'company_intel', 'output_count': 8},
            }

            SQLiteWriter().write(run_summary, records, artifacts)

            connection = sqlite3.connect(artifacts.sqlite_file)
            try:
                project_names = [row[0] for row in connection.execute('SELECT project_name FROM core_company_projects ORDER BY project_name').fetchall()]
            finally:
                connection.close()

            self.assertIn('OpenClaw', project_names)
            self.assertIn('SAFESKILL', project_names)
            self.assertIn('\u9f99\u867e\u5b89\u5168\u4f34\u4fa3', project_names)
            self.assertIn('QcodeAgents', project_names)
            self.assertIn('\u5947\u5b89\u4fe1\u7f51\u795e\u7f51\u7edc\u5b89\u5168\u5ba1\u8ba1\u7cfb\u7edfV7.0', project_names)
            self.assertIn('\u5b89\u5168\u7f16\u6392\u81ea\u52a8\u5316\u4e0e\u54cd\u5e94\u7cfb\u7edf\uff08SOAR\uff09', project_names)
            self.assertNotIn('\u4e2d\u56fd\u4f01\u4e1a\u5bb6', project_names)
            self.assertNotIn('\u300a\u4e2d\u56fd\u4f01\u4e1a\u5bb6\u300b\u72ec\u5bb6\u5bf9\u8bdd\u9f50\u5411\u4e1c\uff1a\u4e0d\u60f3\u88ab\u6dd8\u6c70\uff0c\u5c31\u8981\u62e5\u62b1AI', project_names)
            self.assertNotIn('\u591a\u667a\u80fd\u4f53\u534f\u540c', project_names)
            self.assertNotIn('\u5168\u573a\u666f\u667a\u80fd\u4f53', project_names)
            self.assertNotIn('GitHubAdvisoryData', project_names)
            self.assertNotIn('IDCMarketGlance', project_names)
            self.assertNotIn('OpenClaw\u7206\u706b\uff0cAI\u667a\u80fd\u4f53\u6570\u636e\u3001\u5185\u5bb9\u3001\u6743\u9650\u4e09\u5927\u98ce\u9669\u5982\u4f55\u515c\u5e95\uff1f', project_names)
            self.assertNotIn('\u5947\u5b89\u4fe1\u7f51\u795e\u7f51\u7edc\u5b89\u5168\u5ba1\u8ba1\u7cfb\u7edfV7.0\u4ea7\u54c1NSA-FB-L\u578b\u53f7\u6b63\u5f0f\u505c\u552e\u516c\u544a', project_names)
            self.assertNotIn('NSA-FB-L', project_names)

            self.assertNotIn('\u300a\u4e2d\u56fd\u4f01\u4e1a\u5bb6\u300b\u72ec\u5bb6\u5bf9\u8bdd\u9f50\u5411\u4e1c\uff1a\u4e0d\u60f3\u88ab\u6dd8\u6c70\uff0c\u5c31\u8981\u62e5\u62b1AI', project_names)
    def test_public_sentiment_negation_rules_flip_basic_polarity(self) -> None:
        writer = SQLiteWriter()
        negative_record = NormalizedRecord(
            task_id='public-sentiment-openai-003',
            domain='public_sentiment',
            record_id='neg',
            dedupe_key='neg',
            source_id='hn',
            source_type='public_forum_api',
            source_label='HN',
            source_tag='story',
            source_url='https://example.com/neg',
            published_at='2026-03-24',
            collected_at='2026-03-24T00:00:00+00:00',
            primary_entity='OpenAI',
            topic_tags=['tech_stack_engineering'],
            title='The latest update is not good',
            content_text='Users say the rollout is not good.',
            relevance_score=0.7,
            extra={},
        )
        positive_record = NormalizedRecord(
            task_id='public-sentiment-openai-003',
            domain='public_sentiment',
            record_id='pos',
            dedupe_key='pos',
            source_id='hn',
            source_type='public_forum_api',
            source_label='HN',
            source_tag='story',
            source_url='https://example.com/pos',
            published_at='2026-03-24',
            collected_at='2026-03-24T00:00:00+00:00',
            primary_entity='OpenAI',
            topic_tags=['tech_stack_engineering'],
            title='The latest update is not bad',
            content_text='The quality is not bad and keeps getting better.',
            relevance_score=0.7,
            extra={},
        )

        negative_label, negative_score = writer._classify_sentiment(negative_record)
        positive_label, positive_score = writer._classify_sentiment(positive_record)

        self.assertEqual(negative_label, 'negative')
        self.assertLess(negative_score, 0.0)
        self.assertEqual(positive_label, 'positive')
        self.assertGreater(positive_score, 0.0)
    def test_public_sentiment_strong_negative_cue_outweighs_single_positive_word(self) -> None:
        writer = SQLiteWriter()
        record = NormalizedRecord(
            task_id='public-sentiment-openai-004',
            domain='public_sentiment',
            record_id='weighted',
            dedupe_key='weighted',
            source_id='hn',
            source_type='public_forum_api',
            source_label='HN',
            source_tag='story',
            source_url='https://example.com/weighted',
            published_at='2026-03-24',
            collected_at='2026-03-24T00:00:00+00:00',
            primary_entity='OpenAI',
            topic_tags=['tech_stack_engineering'],
            title='OpenAI is under fire but the docs are good',
            content_text='OpenAI is under fire even though one part of the launch is good.',
            relevance_score=0.7,
            extra={},
        )

        label, score = writer._classify_sentiment(record)

        self.assertEqual(label, 'negative')
        self.assertLess(score, 0.0)
    def test_public_sentiment_chinese_cues_and_negation_are_classified_correctly(self) -> None:
        writer = SQLiteWriter()
        positive_record = NormalizedRecord(
            task_id='public-sentiment-openai-005',
            domain='public_sentiment',
            record_id='zh-pos',
            dedupe_key='zh-pos',
            source_id='hn',
            source_type='public_forum_api',
            source_label='HN',
            source_tag='story',
            source_url='https://example.com/zh-pos',
            published_at='2026-03-24',
            collected_at='2026-03-24T00:00:00+00:00',
            primary_entity='OpenAI',
            topic_tags=['tech_stack_engineering'],
            title='这个功能不差',
            content_text='整体更方便，也很有用，用户反馈很好评。',
            relevance_score=0.7,
            extra={},
        )
        negative_record = NormalizedRecord(
            task_id='public-sentiment-openai-005',
            domain='public_sentiment',
            record_id='zh-neg',
            dedupe_key='zh-neg',
            source_id='hn',
            source_type='public_forum_api',
            source_label='HN',
            source_tag='story',
            source_url='https://example.com/zh-neg',
            published_at='2026-03-24',
            collected_at='2026-03-24T00:00:00+00:00',
            primary_entity='OpenAI',
            topic_tags=['tech_stack_engineering'],
            title='这次升级不好用',
            content_text='用户批评这次改动有风险，也有不少问题。',
            relevance_score=0.7,
            extra={},
        )

        positive_analysis = writer._analyze_sentiment(positive_record)
        negative_analysis = writer._analyze_sentiment(negative_record)

        self.assertEqual(positive_analysis['label'], 'positive')
        self.assertIn('不差', positive_analysis['positive_cues'])
        self.assertIn('方便', positive_analysis['positive_cues'])
        self.assertIn('有用', positive_analysis['positive_cues'])

        self.assertEqual(negative_analysis['label'], 'negative')
        self.assertIn('不好', negative_analysis['negative_cues'])
        self.assertIn('不好用', negative_analysis['negative_cues'])
        self.assertIn('批评', negative_analysis['negative_cues'])
        self.assertIn('风险', negative_analysis['negative_cues'])

    def test_public_sentiment_problem_statement_with_clear_benefits_is_not_forced_negative(self) -> None:
        writer = SQLiteWriter()
        record = NormalizedRecord(
            task_id='public-sentiment-openai-002',
            domain='public_sentiment',
            record_id='public-sentiment-openai-002-hn-1',
            dedupe_key='hn:1',
            source_id='hn_algolia_company_story_search',
            source_type='public_forum_api',
            source_label='HN Algolia',
            source_tag='story',
            source_url='https://example.com/1',
            published_at='2026-03-24',
            collected_at='2026-03-24T00:00:00+00:00',
            primary_entity='OpenAI',
            topic_tags=['tech_stack_engineering'],
            title='Show HN: Sandbox policy builder',
            content_text='The problem is straightforward. No API key needed, no extra billing, and it simplifies repetitive rules.',
            relevance_score=0.7,
            extra={'matched_topics': ['tech_stack_engineering']},
        )

        analysis = writer._analyze_sentiment(record)

        self.assertEqual(analysis["label"], 'positive')
        self.assertGreater(analysis["score"], 0.0)
        self.assertIn('no api key needed', analysis["positive_cues"])
        self.assertIn('no extra billing', analysis["positive_cues"])
        self.assertIn('simplify', analysis["positive_cues"])
    def test_public_sentiment_shutdown_and_abandonment_phrases_are_negative(self) -> None:
        writer = SQLiteWriter()
        record = NormalizedRecord(
            task_id='public-sentiment-openai-006',
            domain='public_sentiment',
            record_id='shutdown',
            dedupe_key='shutdown',
            source_id='hn',
            source_type='public_forum_api',
            source_label='HN',
            source_tag='story',
            source_url='https://example.com/shutdown',
            published_at='2026-03-24',
            collected_at='2026-03-24T00:00:00+00:00',
            primary_entity='OpenAI',
            topic_tags=['tech_stack_engineering'],
            title='OpenAI is shutting down Sora',
            content_text='OpenAI gave up on Sora after the launch failed.',
            relevance_score=0.7,
            extra={},
        )

        analysis = writer._analyze_sentiment(record)

        self.assertEqual(analysis['label'], 'negative')
        self.assertLess(analysis['score'], -0.5)
        self.assertIn('shutting down', analysis['negative_cues'])
        self.assertIn('gave up', analysis['negative_cues'])
        self.assertIn('fail', analysis['negative_cues'])

    def test_public_sentiment_intensifiers_and_downtoners_change_score_magnitude(self) -> None:
        writer = SQLiteWriter()
        strong_record = NormalizedRecord(
            task_id='public-sentiment-openai-007',
            domain='public_sentiment',
            record_id='strong',
            dedupe_key='strong',
            source_id='hn',
            source_type='public_forum_api',
            source_label='HN',
            source_tag='story',
            source_url='https://example.com/strong',
            published_at='2026-03-24',
            collected_at='2026-03-24T00:00:00+00:00',
            primary_entity='OpenAI',
            topic_tags=['tech_stack_engineering'],
            title='The launch is very bad',
            content_text='Users say it is extremely unstable.',
            relevance_score=0.7,
            extra={},
        )
        soft_record = NormalizedRecord(
            task_id='public-sentiment-openai-007',
            domain='public_sentiment',
            record_id='soft',
            dedupe_key='soft',
            source_id='hn',
            source_type='public_forum_api',
            source_label='HN',
            source_tag='story',
            source_url='https://example.com/soft',
            published_at='2026-03-24',
            collected_at='2026-03-24T00:00:00+00:00',
            primary_entity='OpenAI',
            topic_tags=['tech_stack_engineering'],
            title='The launch is somewhat bad',
            content_text='It is a bit unstable.',
            relevance_score=0.7,
            extra={},
        )

        strong_analysis = writer._analyze_sentiment(strong_record)
        soft_analysis = writer._analyze_sentiment(soft_record)

        self.assertEqual(strong_analysis['label'], 'negative')
        self.assertEqual(soft_analysis['label'], 'negative')
        self.assertLess(strong_analysis['score'], soft_analysis['score'])
        self.assertGreater(abs(strong_analysis['score']), abs(soft_analysis['score']))

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
                    'SELECT record_id, sentiment_label, sentiment_score, sentiment_positive_cues_json, sentiment_negative_cues_json FROM core_sentiment_posts ORDER BY record_id'
                ).fetchall()
                topic_rows = connection.execute(
                    'SELECT primary_entity, topic_name, post_count, positive_count, neutral_count, negative_count, average_sentiment_score, dominant_sentiment_label, sample_title, most_positive_title, most_negative_title, most_neutral_title, extra_json '
                    'FROM core_sentiment_topics ORDER BY topic_name'
                ).fetchall()
            finally:
                connection.close()

            self.assertEqual(post_count, 2)
            self.assertEqual(post_rows[0][0], 'public-sentiment-openai-001-hn-1')
            self.assertEqual(post_rows[0][1], 'positive')
            self.assertGreater(post_rows[0][2], 0.0)
            self.assertIn('great', json.loads(post_rows[0][3]))
            self.assertIn('love', json.loads(post_rows[0][3]))
            self.assertEqual(json.loads(post_rows[0][4]), [])
            self.assertEqual(post_rows[1][0], 'public-sentiment-openai-001-hn-2')
            self.assertEqual(post_rows[1][1], 'negative')
            self.assertLess(post_rows[1][2], 0.0)
            self.assertIn('under fire', json.loads(post_rows[1][4]))
            self.assertIn('critic', json.loads(post_rows[1][4]))

            self.assertEqual(len(topic_rows), 2)
            self.assertEqual(topic_rows[0][0], 'OpenAI')
            self.assertEqual(topic_rows[0][1], 'management_culture')
            self.assertEqual(topic_rows[0][2], 1)
            self.assertEqual(topic_rows[0][3], 0)
            self.assertEqual(topic_rows[0][4], 0)
            self.assertEqual(topic_rows[0][5], 1)
            self.assertLess(topic_rows[0][6], 0.0)
            self.assertEqual(topic_rows[0][7], 'negative')
            self.assertEqual(topic_rows[0][8], 'OpenAI is under fire from critics again')
            self.assertIsNone(topic_rows[0][9])
            self.assertEqual(topic_rows[0][10], 'OpenAI is under fire from critics again')
            self.assertEqual(topic_rows[0][11], 'OpenAI is under fire from critics again')
            self.assertIn('under fire', json.loads(topic_rows[0][12])['most_negative_cues'])
            self.assertEqual(json.loads(topic_rows[0][12])['most_positive_cues'], [])
            self.assertEqual(json.loads(topic_rows[0][12])['positive_cue_counts'], [])
            self.assertEqual(json.loads(topic_rows[0][12])['negative_cue_counts'][0]['cue'], 'bad')

            self.assertEqual(topic_rows[1][0], 'OpenAI')
            self.assertEqual(topic_rows[1][1], 'tech_stack_engineering')
            self.assertEqual(topic_rows[1][2], 2)
            self.assertEqual(topic_rows[1][3], 1)
            self.assertEqual(topic_rows[1][4], 0)
            self.assertEqual(topic_rows[1][5], 1)
            self.assertAlmostEqual(topic_rows[1][6], 0.0, delta=0.02)
            self.assertEqual(topic_rows[1][7], 'neutral')
            self.assertEqual(topic_rows[1][8], 'OpenAI is under fire from critics again')
            self.assertEqual(topic_rows[1][9], 'OpenAI shipped a great API update')
            self.assertEqual(topic_rows[1][10], 'OpenAI is under fire from critics again')
            self.assertEqual(topic_rows[1][11], 'OpenAI shipped a great API update')
            self.assertIn('great', json.loads(topic_rows[1][12])['most_positive_cues'])
            self.assertIn('under fire', json.loads(topic_rows[1][12])['most_negative_cues'])
            self.assertIn('great', json.loads(topic_rows[1][12])['most_neutral_cues'])
            self.assertEqual(json.loads(topic_rows[1][12])['positive_cue_counts'][0]['cue'], 'better')
            self.assertEqual(json.loads(topic_rows[1][12])['positive_cue_counts'][0]['count'], 1)
            self.assertEqual(json.loads(topic_rows[1][12])['negative_cue_counts'][0]['cue'], 'bad')
            self.assertEqual(json.loads(topic_rows[1][12])['positive_share'], 0.5)
            self.assertEqual(json.loads(topic_rows[1][12])['negative_share'], 0.5)
            self.assertEqual(json.loads(topic_rows[1][12])['neutral_share'], 0.0)
            self.assertEqual(json.loads(topic_rows[1][12])['sentiment_balance'], 0.0)


if __name__ == '__main__':
    unittest.main()
