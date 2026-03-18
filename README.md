# db-output

A local-first, rule-driven data collection project for investment and job-hunting workflows.

## Current scope

This repository currently contains:

- `需求文档_v0.1.md`
- `实现方案_v0.1.md`
- a runnable Python project skeleton
- a local CLI for task validation and execution
- a source catalog CLI for inspecting configured source websites
- three-layer persistence for `raw`, `normalized`, and `artifacts`
- a SQLite writer for verification-friendly outputs
- configuration-driven source profiles under `configs/sources/`
- generic HTML and RSS connectors instead of hardcoded site-specific core connectors

## Architecture note

The core code does not hardcode specific target companies anymore.

- Task JSON describes the domain, targets, time range, and source policy
- `src/app/sources/registry.py` loads source website definitions from `configs/sources/<domain>/*.json`
- `src/app/services/task_service.py` asks the registry for matching source profiles
- Generic connectors in `src/app/connectors/` execute the selected profiles
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

Outputs are written under `data/` by default.
