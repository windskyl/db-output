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


if __name__ == '__main__':
    unittest.main()
