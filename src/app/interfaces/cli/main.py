from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from app.models.task_spec import TaskSpec, TaskValidationError
from app.services.task_service import TaskService


def configure_stdio() -> None:
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        if stream is None or not hasattr(stream, "reconfigure"):
            continue
        try:
            stream.reconfigure(encoding="utf-8", errors="backslashreplace")
        except Exception:
            pass


def load_task(path: Path) -> TaskSpec:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    return TaskSpec.from_dict(payload)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="db-output", description="Rule-driven data collection skeleton")
    parser.add_argument("--base-dir", default="data", help="Base directory for raw/normalized/artifacts output")
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate_parser = subparsers.add_parser("validate", help="Validate a task JSON file")
    validate_parser.add_argument("task_file", help="Path to the task JSON file")

    run_parser = subparsers.add_parser("run", help="Run the local dry-run pipeline for a task JSON file")
    run_parser.add_argument("task_file", help="Path to the task JSON file")

    sources_parser = subparsers.add_parser("sources", help="List configured source profiles or preview task source selection")
    sources_parser.add_argument("--domain", help="Filter configured source profiles by domain")
    sources_parser.add_argument("--channel", choices=["html", "rss", "api"], help="Filter configured source profiles by channel")
    sources_parser.add_argument("--task-file", help="Optional task JSON file used to preview selected sources")

    tasks_parser = subparsers.add_parser("tasks", help="List completed task runs from local artifacts")
    tasks_parser.add_argument("--domain", help="Filter completed task runs by domain")
    tasks_parser.add_argument("--status", help="Filter completed task runs by status")
    tasks_parser.add_argument("--limit", type=int, help="Limit the number of returned task runs")

    status_parser = subparsers.add_parser("status", help="Show stored status, counts, and artifact paths for a task run")
    status_parser.add_argument("task_id", help="Task ID to inspect")
    status_parser.add_argument("--domain", help="Optional domain filter when task IDs are ambiguous")

    report_parser = subparsers.add_parser(
        "report",
        aliases=["logs"],
        help="Show stored run or quality reports for a completed task",
    )
    report_parser.add_argument("task_id", help="Task ID to inspect")
    report_parser.add_argument("--domain", help="Optional domain filter when task IDs are ambiguous")
    report_parser.add_argument("--kind", choices=["run", "quality", "all"], default="all", help="Which stored report payload to show")

    return parser


def main(argv: list[str] | None = None) -> int:
    configure_stdio()
    parser = build_parser()
    args = parser.parse_args(argv)
    service = TaskService(base_dir=Path(args.base_dir))

    try:
        if args.command == "sources":
            task = load_task(Path(args.task_file)) if args.task_file else None
            result = service.list_sources(domain=args.domain, channel=args.channel, task=task)
        elif args.command == "tasks":
            result = service.list_task_runs(domain=args.domain, status=args.status, limit=args.limit)
        elif args.command == "status":
            result = service.get_task_status(task_id=args.task_id, domain=args.domain)
        elif args.command in {"report", "logs"}:
            result = service.get_task_report(task_id=args.task_id, domain=args.domain, kind=args.kind)
        else:
            task = load_task(Path(args.task_file))
            if args.command == "validate":
                result = service.validate_task(task)
            else:
                result = service.run_task(task)
    except (FileNotFoundError, json.JSONDecodeError, TaskValidationError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
