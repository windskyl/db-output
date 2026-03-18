# db-output

A local-first, rule-driven data collection project for investment and job-hunting workflows.

## Current scope

This repository currently contains:

- `需求文档_v0.1.md`
- `实现方案_v0.1.md`
- a runnable Python project skeleton
- a local CLI for task validation and execution
- three-layer persistence for `raw`, `normalized`, and `artifacts`
- a SQLite writer for verification-friendly outputs
- configuration-driven source profiles under `configs/sources/`
- a generic HTML regex connector instead of hardcoded site-specific core connectors

## Architecture note

The core code does not hardcode specific target companies anymore.

- Core connector logic lives in `src/app/connectors/regex_html_list.py`
- Source websites are defined in `configs/sources/<domain>/*.json`
- Task JSON selects sources by `source_policy.whitelist`
- Switching to another site of the same structure should require a new source profile, not a new core connector

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

Run a company intelligence task:

```powershell
db-output run tasks/examples/company_qianxin_recent_half_year.json
```

Run a jobs task:

```powershell
db-output run tasks/examples/jobs_python_org_recent.json
```

Outputs are written under `data/` by default.
