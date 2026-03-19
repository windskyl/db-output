# db-output

A local-first, rule-driven data collection project for investment and job-hunting workflows.

## Current scope

This repository currently contains:

- the requirements document
- the implementation plan
- a runnable Python project skeleton
- a local CLI for task validation and execution
- a source catalog CLI for inspecting configured source websites
- a task run inspection CLI for completed local artifacts
- three-layer persistence for `raw`, `normalized`, and `artifacts`
- a SQLite writer for verification-friendly outputs
- configuration-driven source profiles under `configs/sources/`
- generic HTML, RSS, and JSON API connectors instead of hardcoded site-specific core connectors
- shared topic and target relevance matching used by all current connector types

## Architecture note

The core code does not hardcode specific target companies anymore.

- Task JSON describes the domain, targets, time range, and source policy
- `src/app/sources/registry.py` loads source website definitions from `configs/sources/<domain>/*.json`
- `src/app/services/task_service.py` asks the registry for matching source profiles
- Generic connectors in `src/app/connectors/` execute the selected profiles
- Topic restriction is driven by `task.topic_scope` plus optional `topic_terms` in each source profile
- Switching to another site of the same structure should require a new source profile, not a new core connector

This means version `v0.1` uses a manually maintained source catalog. The business layer triggers source selection; connectors only execute the chosen source profiles.

## Quick start

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e .
```

Validate a task:

```powershell
db-output validate tasks/examples/company_qianxin_recent_half_year.json
```

Inspect configured source profiles:

```powershell
db-output sources --domain jobs
```

Preview which configured sources a task will use:

```powershell
db-output sources --task-file tasks/examples/jobs_python_org_rss_recent.json
```

Run a company intelligence task:

```powershell
db-output run tasks/examples/company_qianxin_recent_half_year.json
```

Run a jobs task:

```powershell
db-output run tasks/examples/jobs_python_org_recent.json
```

Run a jobs RSS task:

```powershell
db-output run tasks/examples/jobs_python_org_rss_recent.json
```

Run a public sentiment API task:

```powershell
db-output run tasks/examples/public_sentiment_openai_tech_recent.json
```

List completed local task runs:

```powershell
db-output tasks --domain jobs
```

Show stored status, counts, and artifact paths for a task:

```powershell
db-output status job-python-org-rss-001
```

Open the stored run and quality reports for a task:

```powershell
db-output report job-python-org-rss-001 --kind all
```

`db-output logs <task_id>` is available as an alias of `report`.

Outputs are written under `data/` by default.
