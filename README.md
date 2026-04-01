# db-output

A local-first, rule-driven data collection and structured output tool for finance, jobs, company intelligence, and scoped public sentiment workflows.

## Current Scope

The repository currently includes:

- Four first-level domains: `finance`, `jobs`, `company_intel`, `public_sentiment`
- A local CLI for validation, execution, source preview, task listing, status inspection, and report loading
- A local Web workspace for task drafting, document import, recent task reuse, and result preview
- Three persistence layers: `raw`, `normalized`, `artifacts`
- SQLite output designed for easy manual verification
- Generic `HTML`, `RSS`, and `JSON API` connectors
- Domain-specific helper tables such as skills, company projects, and sentiment topics
- Local report artifacts such as `quality_report`, `run_report`, `domain_summary`, and `result_preview`

## Architecture

The core code does not hardcode specific companies or websites.

- Task JSON describes domain, targets, time range, and source policy
- `src/app/sources/registry.py` loads source definitions from `configs/sources/<domain>/*.json`
- `src/app/services/task_service.py` selects matching sources and builds task artifacts
- Generic connectors under `src/app/connectors/` execute fetching and parsing
- Topic filtering is driven by both `task.topic_scope` and per-source `topic_terms`
- SQLite is the main external output, but the system still keeps `raw` and `normalized` as internal truth layers

## Quick Start

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e .
```

The install creates two entry points:

- `db-output`
- `db-output-web`

The default output root is `data/`.

## CLI Usage

Validate a task:

```powershell
db-output validate tasks/examples/company_qianxin_recent_half_year.json
```

List configured sources:

```powershell
db-output sources --domain jobs
```

Preview which sources a task will select:

```powershell
db-output sources --task-file tasks/examples/jobs_python_org_rss_recent.json
```

Run example tasks:

```powershell
db-output run tasks/examples/company_qianxin_recent_half_year.json
db-output run tasks/examples/jobs_python_org_recent.json
db-output run tasks/examples/jobs_python_org_rss_recent.json
db-output run tasks/examples/public_sentiment_openai_tech_recent.json
db-output run tasks/examples/finance_ibm_earnings_recent.json
db-output run tasks/examples/finance_ibm_daily_quotes_recent.json
db-output run tasks/examples/finance_sec_press_recent.json
```

List completed task runs:

```powershell
db-output tasks --domain jobs
db-output tasks --limit 10
```

Inspect task status and artifact paths:

```powershell
db-output status job-python-org-rss-001
```

Load stored run and quality reports:

```powershell
db-output report job-python-org-rss-001 --kind all
```

`db-output logs <task_id>` is an alias of `report`.

## Web Workspace

Start the local Web UI:

```powershell
db-output-web --base-dir data
```

Or run the module directly:

```powershell
$env:PYTHONPATH='src'
python -m app.interfaces.web.server --base-dir data
```

Default address: `http://127.0.0.1:8765`

The current Web UI supports:

- Drafting tasks from a form
- Importing `.json`, `.md`, and `.txt` files
- Validating and running tasks
- Loading historical task reports
- Rendering `result_preview` and `domain_summary`
- Reusing recently completed task payloads

## Output Layout

Each task usually writes the following files:

- `data/raw/<domain>/<task_id>/source_local.jsonl.gz`
- `data/normalized/<domain>/<task_id>/normalized.jsonl.gz`
- `data/artifacts/<domain>/<task_id>/result.sqlite`
- `data/artifacts/<domain>/<task_id>/quality_report.json`
- `data/artifacts/<domain>/<task_id>/run_report.json`

Layer purpose:

- `raw`: connector-level source records
- `normalized`: cleaned, unified candidate records
- `artifacts`: SQLite, reports, and logs

## SQLite Output Model

### jobs

- `core_jobs_postings`: main postings table
- `core_jobs_skills`: helper table for extracted technologies and engineering keywords

### company_intel

- `core_company_events`: main event table
- `core_company_profiles`: helper table for company profile aggregation
- `core_company_projects`: helper table for products, platforms, and projects

### finance

- `core_finance_events`: main finance event table
- `core_finance_metrics`: helper table for extracted metrics
- `core_finance_instruments`: helper table for tracked symbols / instruments

### public_sentiment

- `core_sentiment_posts`: main post table
- `core_sentiment_topics`: topic aggregation table with sentiment counts, representative samples, cue counts, and share / balance fields

## Reports and Preview Payloads

`db-output status` and `db-output report` now expose richer payloads than the early skeleton version.

Important fields include:

- `task_payload`: a reusable task JSON snapshot
- `selected_sources`: source summaries used by the task
- `quality_report`: counts, warnings, fetch stats, and domain summary
- `result_preview`: lightweight tabular preview for CLI / Web display
- `domain_summary`: cards, sections, and narrative text for each domain

`result_preview` uses a common structure:

- `kind`
- `tables[]`
- `tables[].title`
- `tables[].description`
- `tables[].columns`
- `tables[].rows`

Current preview focus by domain:

- `jobs`: latest postings and top skills
- `company_intel`: event samples and top projects
- `finance`: latest metrics and tracked instruments
- `public_sentiment`: post samples and topic observations

See `result_report_guide.md` for the current report and output details.

## Example Tasks

Task examples are stored under `tasks/examples/`.

Typical examples include:

- `jobs_python_org_recent.json`
- `jobs_python_org_rss_recent.json`
- `company_qianxin_recent_half_year.json`
- `public_sentiment_openai_tech_recent.json`
- `finance_ibm_earnings_recent.json`
- `finance_ibm_daily_quotes_recent.json`
- `finance_sec_press_recent.json`

## Quality Behavior

- `quality_policy.dedupe_mode=strict` deduplicates by `dedupe_key` before SQLite write
- `quality_policy.required_fields` and `quality_policy.max_missing_ratio` filter low-quality records before final output
- `normalized.jsonl.gz` keeps normalized candidates, while SQLite stores only post-quality rows
- `quality_report.warnings` records fallback, retries, dedupe removals, quality drops, and output truncation

## Related Notes

- `result_report_guide.md`: report payload and output-table guide
- `finance_chain_test_result.md`: finance daily quote chain verification note
