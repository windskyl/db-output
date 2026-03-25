from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from app.models.records import NormalizedRecord, RunArtifacts
from app.services.task_service import TaskService


class DomainSummaryTests(unittest.TestCase):
    def test_jobs_domain_summary_includes_top_skills_and_companies(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            base = Path(temp_dir)
            artifacts = RunArtifacts(
                task_id='jobs-summary-001',
                domain='jobs',
                raw_file=str(base / 'raw.jsonl.gz'),
                normalized_file=str(base / 'normalized.jsonl.gz'),
                sqlite_file=str(base / 'result.sqlite'),
                quality_report_file=str(base / 'quality_report.json'),
                run_report_file=str(base / 'run_report.json'),
            )
            records = [
                NormalizedRecord(
                    task_id='jobs-summary-001',
                    domain='jobs',
                    record_id='jobs-summary-001-1',
                    dedupe_key='1',
                    source_id='python_org_jobs',
                    source_type='public_jobs_board',
                    source_label='Python.org Jobs',
                    source_tag='',
                    source_url='https://example.com/jobs/1',
                    published_at='2026-03-24',
                    collected_at='2026-03-24T00:00:00+00:00',
                    primary_entity='Acme',
                    topic_tags=['backend'],
                    title='Senior Python Developer/DevOps Engineer',
                    content_text='Cloud, Security, DevOps',
                    relevance_score=0.7,
                    extra={'category': 'Developer / Engineer'},
                ),
                NormalizedRecord(
                    task_id='jobs-summary-001',
                    domain='jobs',
                    record_id='jobs-summary-001-2',
                    dedupe_key='2',
                    source_id='python_org_jobs',
                    source_type='public_jobs_board',
                    source_label='Python.org Jobs',
                    source_tag='',
                    source_url='https://example.com/jobs/2',
                    published_at='2026-03-24',
                    collected_at='2026-03-24T00:01:00+00:00',
                    primary_entity='Acme',
                    topic_tags=['backend'],
                    title='Python Software Engineer',
                    content_text='Backend, Web',
                    relevance_score=0.7,
                    extra={'category': 'Developer / Engineer'},
                ),
            ]
            service = TaskService(base_dir=base)
            run_summary = {
                'task_id': 'jobs-summary-001',
                'domain': 'jobs',
                'scenario_template': 'job_hunt_engineering_basic',
                'status': 'success',
                'raw_count': 2,
                'normalized_count': 2,
                'output_count': 2,
                'quality_report': {'task_id': 'jobs-summary-001', 'domain': 'jobs', 'output_count': 2},
            }
            service.writer.write(run_summary, records, artifacts)

            summary = service._build_domain_report_summary('jobs', Path(artifacts.sqlite_file))

            self.assertEqual(summary['kind'], 'jobs')
            self.assertEqual(summary['cards'][0]['value'], 2)
            self.assertEqual(summary['sections'][0]['title'], 'Top companies')
            self.assertEqual(summary['sections'][0]['items'][0]['label'], 'Acme')
            self.assertEqual(summary['sections'][1]['title'], 'Top skills')
            self.assertEqual(summary['sections'][1]['items'][0]['label'], 'Python')
            self.assertIn('job postings', summary['narrative'])
            self.assertIn('job postings', summary['narrative'])

    def test_company_intel_domain_summary_includes_top_projects(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            base = Path(temp_dir)
            artifacts = RunArtifacts(
                task_id='company-summary-001',
                domain='company_intel',
                raw_file=str(base / 'raw.jsonl.gz'),
                normalized_file=str(base / 'normalized.jsonl.gz'),
                sqlite_file=str(base / 'result.sqlite'),
                quality_report_file=str(base / 'quality_report.json'),
                run_report_file=str(base / 'run_report.json'),
            )
            records = [
                NormalizedRecord(
                    task_id='company-summary-001',
                    domain='company_intel',
                    record_id='company-summary-001-1',
                    dedupe_key='1',
                    source_id='qianxin_news',
                    source_type='official_company_news',
                    source_label='Qianxin News',
                    source_tag='',
                    source_url='https://example.com/news/1',
                    published_at='2026-03-24',
                    collected_at='2026-03-24T00:00:00+00:00',
                    primary_entity='奇安信',
                    topic_tags=['product_update', 'tech_blog'],
                    title='奇安信发布“龙虾安全伴侣”，破解企业“想用不敢用”难题',
                    content_text='OpenClaw 与 SAFESKILL 平台提供新的智能体安全方案。',
                    relevance_score=0.7,
                    extra={},
                ),
            ]
            service = TaskService(base_dir=base)
            run_summary = {
                'task_id': 'company-summary-001',
                'domain': 'company_intel',
                'scenario_template': 'company_due_diligence',
                'status': 'success',
                'raw_count': 1,
                'normalized_count': 1,
                'output_count': 1,
                'quality_report': {'task_id': 'company-summary-001', 'domain': 'company_intel', 'output_count': 1},
            }
            service.writer.write(run_summary, records, artifacts)

            summary = service._build_domain_report_summary('company_intel', Path(artifacts.sqlite_file))

            self.assertEqual(summary['kind'], 'company_intel')
            self.assertEqual(summary['sections'][0]['title'], 'Tracked companies')
            self.assertEqual(summary['sections'][0]['items'][0]['label'], '奇安信')
            self.assertEqual(summary['sections'][1]['title'], 'Top projects')
            self.assertEqual(summary['sections'][1]['items'][0]['label'], 'OpenClaw')
            self.assertIn('company-intel events', summary['narrative'])
            self.assertIn('company-intel events', summary['narrative'])

    def test_finance_domain_summary_includes_metrics_and_instruments(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            base = Path(temp_dir)
            artifacts = RunArtifacts(
                task_id='finance-summary-001',
                domain='finance',
                raw_file=str(base / 'raw.jsonl.gz'),
                normalized_file=str(base / 'normalized.jsonl.gz'),
                sqlite_file=str(base / 'result.sqlite'),
                quality_report_file=str(base / 'quality_report.json'),
                run_report_file=str(base / 'run_report.json'),
            )
            records = [
                NormalizedRecord(
                    task_id='finance-summary-001',
                    domain='finance',
                    record_id='finance-summary-001-1',
                    dedupe_key='1',
                    source_id='alpha_vantage_demo_daily_quotes',
                    source_type='public_finance_api',
                    source_label='Alpha Vantage Demo Daily Quotes',
                    source_tag='daily_quote',
                    source_url='https://example.com/finance/1',
                    published_at='2026-03-24',
                    collected_at='2026-03-24T00:00:00+00:00',
                    primary_entity='IBM',
                    topic_tags=['market_quote'],
                    title='Daily Market Quote',
                    content_text='251.60',
                    relevance_score=0.7,
                    extra={'symbol': 'IBM', 'metric_name': 'close', 'metric_value': '251.60'},
                ),
            ]
            service = TaskService(base_dir=base)
            run_summary = {
                'task_id': 'finance-summary-001',
                'domain': 'finance',
                'scenario_template': 'investment_market_quote_basic',
                'status': 'success',
                'raw_count': 1,
                'normalized_count': 1,
                'output_count': 1,
                'quality_report': {'task_id': 'finance-summary-001', 'domain': 'finance', 'output_count': 1},
            }
            service.writer.write(run_summary, records, artifacts)

            summary = service._build_domain_report_summary('finance', Path(artifacts.sqlite_file))

            self.assertEqual(summary['kind'], 'finance')
            self.assertEqual(summary['cards'][0]['value'], 1)
            self.assertEqual(summary['sections'][0]['title'], 'Tracked instruments')
            self.assertEqual(summary['sections'][0]['items'][0]['label'], 'IBM')
            self.assertEqual(summary['sections'][1]['title'], 'Top metrics')
            self.assertEqual(summary['sections'][1]['items'][0]['label'], 'close')
            self.assertIn('finance events', summary['narrative'])
            self.assertIn('finance events', summary['narrative'])


if __name__ == '__main__':
    unittest.main()