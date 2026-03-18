# db-output

A local-first, rule-driven data collection project for investment and job-hunting workflows.

## Current scope

This repository currently contains:

- `需求文档_v0.1.md`
- `实现方案_v0.1.md`
- a runnable Python project skeleton
- a local CLI for task validation and dry-run execution
- three-layer persistence paths for `raw`, `normalized`, and `artifacts`
- a SQLite writer that creates the first verification-friendly output

## Quick start

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e .
```

Validate a task:

```powershell
db-output validate tasks/examples/jobs_sample.json
```

Run a local dry-run task:

```powershell
db-output run tasks/examples/jobs_sample.json
```

Outputs are written under `data/` by default.
