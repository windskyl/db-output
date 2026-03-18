from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from app.models.task_spec import TaskSpec, TaskValidationError
from app.services.task_service import TaskService


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

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    service = TaskService(base_dir=Path(args.base_dir))

    try:
        if args.command == "sources":
            task = load_task(Path(args.task_file)) if args.task_file else None
            result = service.list_sources(domain=args.domain, channel=args.channel, task=task)
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
