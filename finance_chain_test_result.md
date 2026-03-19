# Finance Chain Test Result

Date: 2026-03-19

This file records the exact outputs captured during the finance end-to-end chain test. Data snippets below are copied as-is from command output or generated artifacts and were not edited.

## Current Project Status

- Shared fetch layer is in place: `FetchClient + RateLimiter + Scheduler`.
- Real live-source chains now exist for `company_intel`, `jobs`, `public_sentiment`, and `finance`.
- Generic connector coverage is now `html + rss + json_api`.
- CLI can validate tasks, run tasks, inspect selected sources, inspect stored status, and inspect stored reports.
- The first live `finance` source added in this step is a JSON API pipeline for quarterly earnings data.

## Process Overview

1. Added a new live `finance` source profile under `configs/sources/finance/`.
2. Extended the generic `json_api` connector with `literal:` fields and `$root.` field extraction.
3. Added a new example finance task under `tasks/examples/`.
4. Ran `sources`, `validate`, `run`, `status`, and `report` for the finance task.
5. Captured exact command outputs and exact generated data samples into this markdown file.

## Scope

- Domain: `finance`
- Example task: `tasks/examples/finance_ibm_earnings_recent.json`
- Live source: `configs/sources/finance/alpha_vantage_demo_earnings.json`
- Base dir used for this run: `tmp_finance_chain/`

## Commands And Exact Outputs

### `python -m app.interfaces.cli.main --base-dir D:\wsq\projects\db-output\tmp_finance_chain sources --task-file D:\wsq\projects\db-output\tasks\examples\finance_ibm_earnings_recent.json`

Exit code: `0`

```json
{
  "total": 7,
  "sources": [
    {
      "source_id": "qianxin_news",
      "domain": "company_intel",
      "connector_kind": "regex_html_list",
      "source_channel": "html",
      "source_type": "official_company_news",
      "source_label": "Qianxin News",
      "base_url": "https://www.qianxin.com",
      "first_page_url": "https://www.qianxin.com/news/list",
      "max_pages": 8,
      "max_items_per_fetch": 100,
      "rate_limit_qps": 1.0,
      "rate_limit_burst": 1,
      "max_concurrency": 1,
      "timeout_seconds": null
    },
    {
      "source_id": "qianxin_report",
      "domain": "company_intel",
      "connector_kind": "regex_html_list",
      "source_channel": "html",
      "source_type": "official_company_report",
      "source_label": "Qianxin Reports",
      "base_url": "https://www.qianxin.com",
      "first_page_url": "https://www.qianxin.com/report/index",
      "max_pages": 8,
      "max_items_per_fetch": 100,
      "rate_limit_qps": 1.0,
      "rate_limit_burst": 1,
      "max_concurrency": 1,
      "timeout_seconds": null
    },
    {
      "source_id": "qianxin_update",
      "domain": "company_intel",
      "connector_kind": "regex_html_list",
      "source_channel": "html",
      "source_type": "official_company_update",
      "source_label": "Qianxin Product Updates",
      "base_url": "https://www.qianxin.com",
      "first_page_url": "https://www.qianxin.com/support/update",
      "max_pages": 8,
      "max_items_per_fetch": 100,
      "rate_limit_qps": 1.0,
      "rate_limit_burst": 1,
      "max_concurrency": 1,
      "timeout_seconds": null
    },
    {
      "source_id": "alpha_vantage_demo_earnings",
      "domain": "finance",
      "connector_kind": "json_api",
      "source_channel": "api",
      "source_type": "public_finance_api",
      "source_label": "Alpha Vantage Demo Earnings",
      "base_url": "https://www.alphavantage.co",
      "first_page_url": "https://www.alphavantage.co/query",
      "max_pages": 1,
      "max_items_per_fetch": 12,
      "rate_limit_qps": 0.5,
      "rate_limit_burst": 1,
      "max_concurrency": 1,
      "timeout_seconds": 20
    },
    {
      "source_id": "python_org_jobs",
      "domain": "jobs",
      "connector_kind": "regex_html_list",
      "source_channel": "html",
      "source_type": "public_jobs_board",
      "source_label": "Python.org Jobs",
      "base_url": "https://www.python.org",
      "first_page_url": "https://www.python.org/jobs/",
      "max_pages": 1,
      "max_items_per_fetch": 100,
      "rate_limit_qps": 1.0,
      "rate_limit_burst": 1,
      "max_concurrency": 1,
      "timeout_seconds": null
    },
    {
      "source_id": "python_org_jobs_rss",
      "domain": "jobs",
      "connector_kind": "rss_feed",
      "source_channel": "rss",
      "source_type": "public_jobs_rss",
      "source_label": "Python.org Jobs RSS",
      "base_url": "https://www.python.org",
      "first_page_url": "https://www.python.org/jobs/feed/rss/",
      "max_pages": 1,
      "max_items_per_fetch": 50,
      "rate_limit_qps": 1.0,
      "rate_limit_burst": 1,
      "max_concurrency": 1,
      "timeout_seconds": null
    },
    {
      "source_id": "hn_algolia_company_story_search",
      "domain": "public_sentiment",
      "connector_kind": "json_api",
      "source_channel": "api",
      "source_type": "public_forum_api",
      "source_label": "Hacker News Algolia Company Story Search",
      "base_url": "https://hn.algolia.com",
      "first_page_url": "https://hn.algolia.com/api/v1/search_by_date",
      "max_pages": 1,
      "max_items_per_fetch": 50,
      "rate_limit_qps": 1.0,
      "rate_limit_burst": 1,
      "max_concurrency": 1,
      "timeout_seconds": null
    }
  ],
  "task": {
    "task_id": "finance-ibm-earnings-001",
    "domain": "finance",
    "scenario_template": "investment_financial_report_basic",
    "target_count": 1,
    "topic_scope": [
      "financial_report"
    ],
    "time_range": {
      "start": "2023-01-01T00:00:00",
      "end": "2026-03-19T23:59:59",
      "timezone": "UTC"
    },
    "selection_mode": "explicit"
  },
  "selected_sources": [
    {
      "source_id": "alpha_vantage_demo_earnings",
      "domain": "finance",
      "connector_kind": "json_api",
      "source_channel": "api",
      "source_type": "public_finance_api",
      "source_label": "Alpha Vantage Demo Earnings",
      "base_url": "https://www.alphavantage.co",
      "first_page_url": "https://www.alphavantage.co/query",
      "max_pages": 1,
      "max_items_per_fetch": 12,
      "rate_limit_qps": 0.5,
      "rate_limit_burst": 1,
      "max_concurrency": 1,
      "timeout_seconds": 20
    }
  ]
}
```

### `python -m app.interfaces.cli.main --base-dir D:\wsq\projects\db-output\tmp_finance_chain validate D:\wsq\projects\db-output\tasks\examples\finance_ibm_earnings_recent.json`

Exit code: `0`

```json
{
  "ok": true,
  "task": {
    "task_id": "finance-ibm-earnings-001",
    "domain": "finance",
    "scenario_template": "investment_financial_report_basic",
    "target_count": 1,
    "topic_scope": [
      "financial_report"
    ],
    "time_range": {
      "start": "2023-01-01T00:00:00",
      "end": "2026-03-19T23:59:59",
      "timezone": "UTC"
    },
    "selection_mode": "explicit"
  },
  "selected_sources": [
    "alpha_vantage_demo_earnings"
  ],
  "selected_source_details": [
    {
      "source_id": "alpha_vantage_demo_earnings",
      "domain": "finance",
      "connector_kind": "json_api",
      "source_channel": "api",
      "source_type": "public_finance_api",
      "source_label": "Alpha Vantage Demo Earnings",
      "base_url": "https://www.alphavantage.co",
      "first_page_url": "https://www.alphavantage.co/query",
      "max_pages": 1,
      "max_items_per_fetch": 12,
      "rate_limit_qps": 0.5,
      "rate_limit_burst": 1,
      "max_concurrency": 1,
      "timeout_seconds": 20
    }
  ],
  "supported_domains": [
    "company_intel",
    "finance",
    "jobs",
    "public_sentiment"
  ]
}
```

### `python -m app.interfaces.cli.main --base-dir D:\wsq\projects\db-output\tmp_finance_chain run D:\wsq\projects\db-output\tasks\examples\finance_ibm_earnings_recent.json`

Exit code: `0`

```json
{
  "status": "success",
  "created_at": "2026-03-19T06:49:41.329201+00:00",
  "selected_sources": [
    {
      "source_id": "alpha_vantage_demo_earnings",
      "domain": "finance",
      "connector_kind": "json_api",
      "source_channel": "api",
      "source_type": "public_finance_api",
      "source_label": "Alpha Vantage Demo Earnings",
      "base_url": "https://www.alphavantage.co",
      "first_page_url": "https://www.alphavantage.co/query",
      "max_pages": 1,
      "max_items_per_fetch": 12,
      "rate_limit_qps": 0.5,
      "rate_limit_burst": 1,
      "max_concurrency": 1,
      "timeout_seconds": 20
    }
  ],
  "artifacts": {
    "raw_file": "D:\\wsq\\projects\\db-output\\tmp_finance_chain\\raw\\finance\\finance-ibm-earnings-001\\source_local.jsonl.gz",
    "normalized_file": "D:\\wsq\\projects\\db-output\\tmp_finance_chain\\normalized\\finance\\finance-ibm-earnings-001\\normalized.jsonl.gz",
    "sqlite_file": "D:\\wsq\\projects\\db-output\\tmp_finance_chain\\artifacts\\finance\\finance-ibm-earnings-001\\result.sqlite",
    "quality_report_file": "D:\\wsq\\projects\\db-output\\tmp_finance_chain\\artifacts\\finance\\finance-ibm-earnings-001\\quality_report.json",
    "run_report_file": "D:\\wsq\\projects\\db-output\\tmp_finance_chain\\artifacts\\finance\\finance-ibm-earnings-001\\run_report.json"
  },
  "quality_report": {
    "task_id": "finance-ibm-earnings-001",
    "domain": "finance",
    "raw_count": 12,
    "normalized_count": 12,
    "deduped_count": 12,
    "output_count": 12,
    "dropped_by_relevance": 0,
    "dropped_by_quality": 0,
    "missing_field_stats": {},
    "source_stats": {
      "alpha_vantage_demo_earnings": 12
    },
    "fetch_stats": {
      "task_id": "finance-ibm-earnings-001",
      "total_requests": 1,
      "successful_requests": 1,
      "failed_requests": 0,
      "total_retries": 0,
      "total_wait_ms": 0,
      "status_codes": {
        "200": 1
      },
      "error_types": {},
      "source_stats": {
        "alpha_vantage_demo_earnings": {
          "requests": 1,
          "successful_requests": 1,
          "failed_requests": 0,
          "retries": 0,
          "wait_ms": 0,
          "status_codes": {
            "200": 1
          }
        }
      },
      "recent_errors": []
    },
    "error_stats": {},
    "warnings": []
  }
}
```

### `python -m app.interfaces.cli.main --base-dir D:\wsq\projects\db-output\tmp_finance_chain status finance-ibm-earnings-001`

Exit code: `0`

```json
{
  "task": {
    "task_id": "finance-ibm-earnings-001",
    "domain": "finance",
    "scenario_template": "investment_financial_report_basic",
    "target_count": 1,
    "topic_scope": [
      "financial_report"
    ],
    "time_range": {
      "start": "2023-01-01T00:00:00",
      "end": "2026-03-19T23:59:59",
      "timezone": "UTC"
    },
    "selection_mode": "explicit"
  },
  "status": "success",
  "created_at": "2026-03-19T06:49:41.329201+00:00",
  "updated_at": "2026-03-19T06:49:42.165762+00:00",
  "artifacts_dir": "D:\\wsq\\projects\\db-output\\tmp_finance_chain\\artifacts\\finance\\finance-ibm-earnings-001",
  "artifacts": {
    "raw_file": "D:\\wsq\\projects\\db-output\\tmp_finance_chain\\raw\\finance\\finance-ibm-earnings-001\\source_local.jsonl.gz",
    "normalized_file": "D:\\wsq\\projects\\db-output\\tmp_finance_chain\\normalized\\finance\\finance-ibm-earnings-001\\normalized.jsonl.gz",
    "sqlite_file": "D:\\wsq\\projects\\db-output\\tmp_finance_chain\\artifacts\\finance\\finance-ibm-earnings-001\\result.sqlite",
    "quality_report_file": "D:\\wsq\\projects\\db-output\\tmp_finance_chain\\artifacts\\finance\\finance-ibm-earnings-001\\quality_report.json",
    "run_report_file": "D:\\wsq\\projects\\db-output\\tmp_finance_chain\\artifacts\\finance\\finance-ibm-earnings-001\\run_report.json"
  },
  "selected_sources": [
    {
      "source_id": "alpha_vantage_demo_earnings",
      "domain": "finance",
      "connector_kind": "json_api",
      "source_channel": "api",
      "source_type": "public_finance_api",
      "source_label": "Alpha Vantage Demo Earnings",
      "base_url": "https://www.alphavantage.co",
      "first_page_url": "https://www.alphavantage.co/query",
      "max_pages": 1,
      "max_items_per_fetch": 12,
      "rate_limit_qps": 0.5,
      "rate_limit_burst": 1,
      "max_concurrency": 1,
      "timeout_seconds": 20
    }
  ],
  "quality_report": {
    "task_id": "finance-ibm-earnings-001",
    "domain": "finance",
    "raw_count": 12,
    "normalized_count": 12,
    "deduped_count": 12,
    "output_count": 12,
    "dropped_by_relevance": 0,
    "dropped_by_quality": 0,
    "missing_field_stats": {},
    "source_stats": {
      "alpha_vantage_demo_earnings": 12
    },
    "fetch_stats": {
      "task_id": "finance-ibm-earnings-001",
      "total_requests": 1,
      "successful_requests": 1,
      "failed_requests": 0,
      "total_retries": 0,
      "total_wait_ms": 0,
      "status_codes": {
        "200": 1
      },
      "error_types": {},
      "source_stats": {
        "alpha_vantage_demo_earnings": {
          "requests": 1,
          "successful_requests": 1,
          "failed_requests": 0,
          "retries": 0,
          "wait_ms": 0,
          "status_codes": {
            "200": 1
          }
        }
      },
      "recent_errors": []
    },
    "error_stats": {},
    "warnings": []
  }
}
```

### `python -m app.interfaces.cli.main --base-dir D:\wsq\projects\db-output\tmp_finance_chain report finance-ibm-earnings-001 --kind all`

Exit code: `0`

```json
{
  "task": {
    "task_id": "finance-ibm-earnings-001",
    "domain": "finance",
    "scenario_template": "investment_financial_report_basic",
    "target_count": 1,
    "topic_scope": [
      "financial_report"
    ],
    "time_range": {
      "start": "2023-01-01T00:00:00",
      "end": "2026-03-19T23:59:59",
      "timezone": "UTC"
    },
    "selection_mode": "explicit"
  },
  "status": "success",
  "created_at": "2026-03-19T06:49:41.329201+00:00",
  "updated_at": "2026-03-19T06:49:42.165762+00:00",
  "files": {
    "run_report_file": "D:\\wsq\\projects\\db-output\\tmp_finance_chain\\artifacts\\finance\\finance-ibm-earnings-001\\run_report.json",
    "quality_report_file": "D:\\wsq\\projects\\db-output\\tmp_finance_chain\\artifacts\\finance\\finance-ibm-earnings-001\\quality_report.json"
  },
  "run_report": {
    "task": {
      "task_id": "finance-ibm-earnings-001",
      "domain": "finance",
      "scenario_template": "investment_financial_report_basic",
      "target_count": 1,
      "topic_scope": [
        "financial_report"
      ],
      "time_range": {
        "start": "2023-01-01T00:00:00",
        "end": "2026-03-19T23:59:59",
        "timezone": "UTC"
      },
      "selection_mode": "explicit"
    },
    "selected_sources": [
      {
        "source_id": "alpha_vantage_demo_earnings",
        "domain": "finance",
        "connector_kind": "json_api",
        "source_channel": "api",
        "source_type": "public_finance_api",
        "source_label": "Alpha Vantage Demo Earnings",
        "base_url": "https://www.alphavantage.co",
        "first_page_url": "https://www.alphavantage.co/query",
        "max_pages": 1,
        "max_items_per_fetch": 12,
        "rate_limit_qps": 0.5,
        "rate_limit_burst": 1,
        "max_concurrency": 1,
        "timeout_seconds": 20
      }
    ],
    "artifacts": {
      "raw_file": "D:\\wsq\\projects\\db-output\\tmp_finance_chain\\raw\\finance\\finance-ibm-earnings-001\\source_local.jsonl.gz",
      "normalized_file": "D:\\wsq\\projects\\db-output\\tmp_finance_chain\\normalized\\finance\\finance-ibm-earnings-001\\normalized.jsonl.gz",
      "sqlite_file": "D:\\wsq\\projects\\db-output\\tmp_finance_chain\\artifacts\\finance\\finance-ibm-earnings-001\\result.sqlite",
      "quality_report_file": "D:\\wsq\\projects\\db-output\\tmp_finance_chain\\artifacts\\finance\\finance-ibm-earnings-001\\quality_report.json",
      "run_report_file": "D:\\wsq\\projects\\db-output\\tmp_finance_chain\\artifacts\\finance\\finance-ibm-earnings-001\\run_report.json"
    },
    "status": "success",
    "created_at": "2026-03-19T06:49:41.329201+00:00",
    "quality_summary": {
      "raw_count": 12,
      "normalized_count": 12,
      "output_count": 12,
      "warning_count": 0,
      "fetch_request_count": 1,
      "fetch_retry_count": 0,
      "fetch_failure_count": 0,
      "source_stats": {
        "alpha_vantage_demo_earnings": 12
      }
    }
  },
  "quality_report": {
    "task_id": "finance-ibm-earnings-001",
    "domain": "finance",
    "raw_count": 12,
    "normalized_count": 12,
    "deduped_count": 12,
    "output_count": 12,
    "dropped_by_relevance": 0,
    "dropped_by_quality": 0,
    "missing_field_stats": {},
    "source_stats": {
      "alpha_vantage_demo_earnings": 12
    },
    "fetch_stats": {
      "task_id": "finance-ibm-earnings-001",
      "total_requests": 1,
      "successful_requests": 1,
      "failed_requests": 0,
      "total_retries": 0,
      "total_wait_ms": 0,
      "status_codes": {
        "200": 1
      },
      "error_types": {},
      "source_stats": {
        "alpha_vantage_demo_earnings": {
          "requests": 1,
          "successful_requests": 1,
          "failed_requests": 0,
          "retries": 0,
          "wait_ms": 0,
          "status_codes": {
            "200": 1
          }
        }
      },
      "recent_errors": []
    },
    "error_stats": {},
    "warnings": []
  }
}
```

## Artifact Paths

- `D:\wsq\projects\db-output\tmp_finance_chain\raw\finance\finance-ibm-earnings-001\source_local.jsonl.gz`
- `D:\wsq\projects\db-output\tmp_finance_chain\normalized\finance\finance-ibm-earnings-001\normalized.jsonl.gz`
- `D:\wsq\projects\db-output\tmp_finance_chain\artifacts\finance\finance-ibm-earnings-001\result.sqlite`
- `D:\wsq\projects\db-output\tmp_finance_chain\artifacts\finance\finance-ibm-earnings-001\quality_report.json`
- `D:\wsq\projects\db-output\tmp_finance_chain\artifacts\finance\finance-ibm-earnings-001\run_report.json`

## Raw Data Samples

The following lines are exact raw JSONL lines from the generated `raw` artifact.

```json
{"task_id": "finance-ibm-earnings-001", "domain": "finance", "source_id": "alpha_vantage_demo_earnings", "source_type": "public_finance_api", "source_label": "Alpha Vantage Demo Earnings", "fetched_at": "2026-03-19T06:49:41.325146+00:00", "request_url": "https://www.alphavantage.co/query?function=EARNINGS&symbol=IBM&apikey=demo", "http_status": 200, "content_hash": "alpha_vantage_demo_earnings:2026-01-28:2026-01-28", "raw_payload": {"source_item_id": "2026-01-28", "title": "Quarterly Earnings", "summary": "4.52", "published_at": "2026-01-28", "symbol": "IBM", "category": "quarterly_earnings", "metric_name": "reported_eps", "metric_value": "4.52", "estimated_eps": "4.29", "surprise": "0.23", "surprise_percentage": "5.3613", "report_time": "post-market", "reported_date": "2026-01-28", "fiscal_date_ending": "2025-12-31"}}
{"task_id": "finance-ibm-earnings-001", "domain": "finance", "source_id": "alpha_vantage_demo_earnings", "source_type": "public_finance_api", "source_label": "Alpha Vantage Demo Earnings", "fetched_at": "2026-03-19T06:49:41.325192+00:00", "request_url": "https://www.alphavantage.co/query?function=EARNINGS&symbol=IBM&apikey=demo", "http_status": 200, "content_hash": "alpha_vantage_demo_earnings:2025-10-22:2025-10-22", "raw_payload": {"source_item_id": "2025-10-22", "title": "Quarterly Earnings", "summary": "2.65", "published_at": "2025-10-22", "symbol": "IBM", "category": "quarterly_earnings", "metric_name": "reported_eps", "metric_value": "2.65", "estimated_eps": "2.45", "surprise": "0.2", "surprise_percentage": "8.1633", "report_time": "post-market", "reported_date": "2025-10-22", "fiscal_date_ending": "2025-09-30"}}
{"task_id": "finance-ibm-earnings-001", "domain": "finance", "source_id": "alpha_vantage_demo_earnings", "source_type": "public_finance_api", "source_label": "Alpha Vantage Demo Earnings", "fetched_at": "2026-03-19T06:49:41.325240+00:00", "request_url": "https://www.alphavantage.co/query?function=EARNINGS&symbol=IBM&apikey=demo", "http_status": 200, "content_hash": "alpha_vantage_demo_earnings:2025-07-23:2025-07-23", "raw_payload": {"source_item_id": "2025-07-23", "title": "Quarterly Earnings", "summary": "2.8", "published_at": "2025-07-23", "symbol": "IBM", "category": "quarterly_earnings", "metric_name": "reported_eps", "metric_value": "2.8", "estimated_eps": "2.65", "surprise": "0.15", "surprise_percentage": "5.6604", "report_time": "post-market", "reported_date": "2025-07-23", "fiscal_date_ending": "2025-06-30"}}
```

## Normalized Data Samples

The following lines are exact normalized JSONL lines from the generated `normalized` artifact.

```json
{"task_id": "finance-ibm-earnings-001", "domain": "finance", "record_id": "finance-ibm-earnings-001-alpha_vantage_demo_earnings-1", "dedupe_key": "alpha_vantage_demo_earnings:2026-01-28:Quarterly Earnings", "source_id": "alpha_vantage_demo_earnings", "source_type": "public_finance_api", "source_label": "Alpha Vantage Demo Earnings", "source_tag": "quarterly_earnings", "source_url": "https://www.alphavantage.co/query?function=EARNINGS&symbol=IBM&apikey=demo", "published_at": "2026-01-28", "collected_at": "2026-03-19T06:49:41.325146+00:00", "primary_entity": "IBM", "entity_tags": ["IBM"], "topic_tags": ["financial_report"], "title": "Quarterly Earnings", "content_text": "4.52", "relevance_score": 0.7, "quality_flags": [], "extra": {"scenario_template": "investment_financial_report_basic", "request_url": "https://www.alphavantage.co/query?function=EARNINGS&symbol=IBM&apikey=demo", "source_item_id": "2026-01-28", "category": "quarterly_earnings", "symbol": "IBM", "metric_name": "reported_eps", "metric_value": "4.52", "estimated_eps": "4.29", "surprise": "0.23", "surprise_percentage": "5.3613", "report_time": "post-market", "reported_date": "2026-01-28", "fiscal_date_ending": "2025-12-31"}}
{"task_id": "finance-ibm-earnings-001", "domain": "finance", "record_id": "finance-ibm-earnings-001-alpha_vantage_demo_earnings-2", "dedupe_key": "alpha_vantage_demo_earnings:2025-10-22:Quarterly Earnings", "source_id": "alpha_vantage_demo_earnings", "source_type": "public_finance_api", "source_label": "Alpha Vantage Demo Earnings", "source_tag": "quarterly_earnings", "source_url": "https://www.alphavantage.co/query?function=EARNINGS&symbol=IBM&apikey=demo", "published_at": "2025-10-22", "collected_at": "2026-03-19T06:49:41.325192+00:00", "primary_entity": "IBM", "entity_tags": ["IBM"], "topic_tags": ["financial_report"], "title": "Quarterly Earnings", "content_text": "2.65", "relevance_score": 0.7, "quality_flags": [], "extra": {"scenario_template": "investment_financial_report_basic", "request_url": "https://www.alphavantage.co/query?function=EARNINGS&symbol=IBM&apikey=demo", "source_item_id": "2025-10-22", "category": "quarterly_earnings", "symbol": "IBM", "metric_name": "reported_eps", "metric_value": "2.65", "estimated_eps": "2.45", "surprise": "0.2", "surprise_percentage": "8.1633", "report_time": "post-market", "reported_date": "2025-10-22", "fiscal_date_ending": "2025-09-30"}}
{"task_id": "finance-ibm-earnings-001", "domain": "finance", "record_id": "finance-ibm-earnings-001-alpha_vantage_demo_earnings-3", "dedupe_key": "alpha_vantage_demo_earnings:2025-07-23:Quarterly Earnings", "source_id": "alpha_vantage_demo_earnings", "source_type": "public_finance_api", "source_label": "Alpha Vantage Demo Earnings", "source_tag": "quarterly_earnings", "source_url": "https://www.alphavantage.co/query?function=EARNINGS&symbol=IBM&apikey=demo", "published_at": "2025-07-23", "collected_at": "2026-03-19T06:49:41.325240+00:00", "primary_entity": "IBM", "entity_tags": ["IBM"], "topic_tags": ["financial_report"], "title": "Quarterly Earnings", "content_text": "2.8", "relevance_score": 0.7, "quality_flags": [], "extra": {"scenario_template": "investment_financial_report_basic", "request_url": "https://www.alphavantage.co/query?function=EARNINGS&symbol=IBM&apikey=demo", "source_item_id": "2025-07-23", "category": "quarterly_earnings", "symbol": "IBM", "metric_name": "reported_eps", "metric_value": "2.8", "estimated_eps": "2.65", "surprise": "0.15", "surprise_percentage": "5.6604", "report_time": "post-market", "reported_date": "2025-07-23", "fiscal_date_ending": "2025-06-30"}}
```

## SQLite Samples

The following rows come directly from `core_finance_events`.

```json
{"record_id": "finance-ibm-earnings-001-alpha_vantage_demo_earnings-1", "primary_entity": "IBM", "title": "Quarterly Earnings", "published_at": "2026-01-28", "source_url": "https://www.alphavantage.co/query?function=EARNINGS&symbol=IBM&apikey=demo", "extra_json": "{\"scenario_template\": \"investment_financial_report_basic\", \"request_url\": \"https://www.alphavantage.co/query?function=EARNINGS&symbol=IBM&apikey=demo\", \"source_item_id\": \"2026-01-28\", \"category\": \"quarterly_earnings\", \"symbol\": \"IBM\", \"metric_name\": \"reported_eps\", \"metric_value\": \"4.52\", \"estimated_eps\": \"4.29\", \"surprise\": \"0.23\", \"surprise_percentage\": \"5.3613\", \"report_time\": \"post-market\", \"reported_date\": \"2026-01-28\", \"fiscal_date_ending\": \"2025-12-31\"}"}
{"record_id": "finance-ibm-earnings-001-alpha_vantage_demo_earnings-2", "primary_entity": "IBM", "title": "Quarterly Earnings", "published_at": "2025-10-22", "source_url": "https://www.alphavantage.co/query?function=EARNINGS&symbol=IBM&apikey=demo", "extra_json": "{\"scenario_template\": \"investment_financial_report_basic\", \"request_url\": \"https://www.alphavantage.co/query?function=EARNINGS&symbol=IBM&apikey=demo\", \"source_item_id\": \"2025-10-22\", \"category\": \"quarterly_earnings\", \"symbol\": \"IBM\", \"metric_name\": \"reported_eps\", \"metric_value\": \"2.65\", \"estimated_eps\": \"2.45\", \"surprise\": \"0.2\", \"surprise_percentage\": \"8.1633\", \"report_time\": \"post-market\", \"reported_date\": \"2025-10-22\", \"fiscal_date_ending\": \"2025-09-30\"}"}
{"record_id": "finance-ibm-earnings-001-alpha_vantage_demo_earnings-3", "primary_entity": "IBM", "title": "Quarterly Earnings", "published_at": "2025-07-23", "source_url": "https://www.alphavantage.co/query?function=EARNINGS&symbol=IBM&apikey=demo", "extra_json": "{\"scenario_template\": \"investment_financial_report_basic\", \"request_url\": \"https://www.alphavantage.co/query?function=EARNINGS&symbol=IBM&apikey=demo\", \"source_item_id\": \"2025-07-23\", \"category\": \"quarterly_earnings\", \"symbol\": \"IBM\", \"metric_name\": \"reported_eps\", \"metric_value\": \"2.8\", \"estimated_eps\": \"2.65\", \"surprise\": \"0.15\", \"surprise_percentage\": \"5.6604\", \"report_time\": \"post-market\", \"reported_date\": \"2025-07-23\", \"fiscal_date_ending\": \"2025-06-30\"}"}
```

## Stored Reports

### `quality_report.json`

```json
{
  "task_id": "finance-ibm-earnings-001",
  "domain": "finance",
  "raw_count": 12,
  "normalized_count": 12,
  "deduped_count": 12,
  "output_count": 12,
  "dropped_by_relevance": 0,
  "dropped_by_quality": 0,
  "missing_field_stats": {},
  "source_stats": {
    "alpha_vantage_demo_earnings": 12
  },
  "fetch_stats": {
    "task_id": "finance-ibm-earnings-001",
    "total_requests": 1,
    "successful_requests": 1,
    "failed_requests": 0,
    "total_retries": 0,
    "total_wait_ms": 0,
    "status_codes": {
      "200": 1
    },
    "error_types": {},
    "source_stats": {
      "alpha_vantage_demo_earnings": {
        "requests": 1,
        "successful_requests": 1,
        "failed_requests": 0,
        "retries": 0,
        "wait_ms": 0,
        "status_codes": {
          "200": 1
        }
      }
    },
    "recent_errors": []
  },
  "error_stats": {},
  "warnings": []
}
```

### `run_report.json`

```json
{
  "task": {
    "task_id": "finance-ibm-earnings-001",
    "domain": "finance",
    "scenario_template": "investment_financial_report_basic",
    "target_count": 1,
    "topic_scope": [
      "financial_report"
    ],
    "time_range": {
      "start": "2023-01-01T00:00:00",
      "end": "2026-03-19T23:59:59",
      "timezone": "UTC"
    },
    "selection_mode": "explicit"
  },
  "selected_sources": [
    {
      "source_id": "alpha_vantage_demo_earnings",
      "domain": "finance",
      "connector_kind": "json_api",
      "source_channel": "api",
      "source_type": "public_finance_api",
      "source_label": "Alpha Vantage Demo Earnings",
      "base_url": "https://www.alphavantage.co",
      "first_page_url": "https://www.alphavantage.co/query",
      "max_pages": 1,
      "max_items_per_fetch": 12,
      "rate_limit_qps": 0.5,
      "rate_limit_burst": 1,
      "max_concurrency": 1,
      "timeout_seconds": 20
    }
  ],
  "artifacts": {
    "raw_file": "D:\\wsq\\projects\\db-output\\tmp_finance_chain\\raw\\finance\\finance-ibm-earnings-001\\source_local.jsonl.gz",
    "normalized_file": "D:\\wsq\\projects\\db-output\\tmp_finance_chain\\normalized\\finance\\finance-ibm-earnings-001\\normalized.jsonl.gz",
    "sqlite_file": "D:\\wsq\\projects\\db-output\\tmp_finance_chain\\artifacts\\finance\\finance-ibm-earnings-001\\result.sqlite",
    "quality_report_file": "D:\\wsq\\projects\\db-output\\tmp_finance_chain\\artifacts\\finance\\finance-ibm-earnings-001\\quality_report.json",
    "run_report_file": "D:\\wsq\\projects\\db-output\\tmp_finance_chain\\artifacts\\finance\\finance-ibm-earnings-001\\run_report.json"
  },
  "status": "success",
  "created_at": "2026-03-19T06:49:41.329201+00:00",
  "quality_summary": {
    "raw_count": 12,
    "normalized_count": 12,
    "output_count": 12,
    "warning_count": 0,
    "fetch_request_count": 1,
    "fetch_retry_count": 0,
    "fetch_failure_count": 0,
    "source_stats": {
      "alpha_vantage_demo_earnings": 12
    }
  }
}
```