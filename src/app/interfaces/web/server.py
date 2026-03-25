from __future__ import annotations

import argparse
import json
import mimetypes
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from app.domain_plugins.registry import DomainRegistry
from app.interfaces.web.helpers import (
    WebInputError,
    build_task_payload_from_form,
    extract_task_payload_from_document,
    load_example_task,
    summarize_example_tasks,
)
from app.models.task_spec import TaskSpec, TaskValidationError
from app.services.task_service import TaskService
from app.sources.registry import SourceRegistry

MAX_REQUEST_BYTES = 1_000_000


class WebApplication:
    def __init__(self, base_dir: Path) -> None:
        self.base_dir = base_dir
        self.service = TaskService(base_dir=base_dir)
        self.domain_registry = DomainRegistry()
        self.source_registry = SourceRegistry(config_root=Path(__file__).resolve().parents[4] / "configs" / "sources")
        self.example_dir = Path(__file__).resolve().parents[4] / "tasks" / "examples"
        self.static_dir = Path(__file__).resolve().parent / "static"

    def metadata(self) -> dict[str, Any]:
        domains = []
        for name in self.domain_registry.names():
            plugin = self.domain_registry.get(name)
            domains.append(
                {
                    "name": name,
                    "topics": sorted(plugin.allowed_topics),
                }
            )
        sources = {}
        for profile in self.source_registry.list_profiles():
            sources.setdefault(profile.domain, []).append(profile.to_summary())
        for items in sources.values():
            items.sort(key=lambda item: item["source_id"])
        return {
            "domains": domains,
            "sources": sources,
            "examples": summarize_example_tasks(self.example_dir),
        }

    def load_example(self, name: str) -> dict[str, Any]:
        return load_example_task(self.example_dir, name)

    def build_task_from_form(self, payload: dict[str, Any]) -> dict[str, Any]:
        return build_task_payload_from_form(payload)

    def import_document(self, filename: str, content: str) -> dict[str, Any]:
        return extract_task_payload_from_document(filename, content)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="db-output-web", description="Local web UI for db-output")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind the local web server")
    parser.add_argument("--port", type=int, default=8765, help="Port to bind the local web server")
    parser.add_argument("--base-dir", default="data", help="Base directory for raw/normalized/artifacts output")
    return parser


def make_handler(app: WebApplication) -> type[BaseHTTPRequestHandler]:
    class WebHandler(BaseHTTPRequestHandler):
        server_version = "db-output-web/0.1"

        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            if parsed.path == "/":
                self._send_static("index.html", "text/html; charset=utf-8")
                return
            if parsed.path == "/app.css":
                self._send_static("app.css", "text/css; charset=utf-8")
                return
            if parsed.path == "/app.js":
                self._send_static("app.js", "application/javascript; charset=utf-8")
                return
            if parsed.path == "/api/meta":
                self._send_json({"ok": True, "meta": app.metadata()})
                return
            if parsed.path == "/api/example":
                params = parse_qs(parsed.query)
                name = params.get("name", [""])[0]
                if not name:
                    self._send_error_json(HTTPStatus.BAD_REQUEST, "example name is required")
                    return
                try:
                    payload = app.load_example(name)
                except FileNotFoundError as exc:
                    self._send_error_json(HTTPStatus.NOT_FOUND, str(exc))
                    return
                self._send_json({"ok": True, "task": payload})
                return
            self._send_error_json(HTTPStatus.NOT_FOUND, "route not found")

        def do_POST(self) -> None:
            parsed = urlparse(self.path)
            try:
                payload = self._read_json_body()
                if parsed.path == "/api/draft/form":
                    task_payload = app.build_task_from_form(payload)
                    self._send_json({"ok": True, "task": task_payload})
                    return
                if parsed.path == "/api/draft/document":
                    file_name = str(payload.get("file_name", ""))
                    content = str(payload.get("content", ""))
                    result = app.import_document(file_name, content)
                    self._send_json({"ok": True, **result})
                    return
                if parsed.path == "/api/validate":
                    task = TaskSpec.from_dict(dict(payload.get("task", {})))
                    self._send_json({"ok": True, "result": app.service.validate_task(task)})
                    return
                if parsed.path == "/api/run":
                    task = TaskSpec.from_dict(dict(payload.get("task", {})))
                    self._send_json({"ok": True, "result": app.service.run_task(task)})
                    return
                if parsed.path == "/api/status":
                    task_id = str(payload.get("task_id", "")).strip()
                    if not task_id:
                        raise WebInputError("task_id is required")
                    domain = str(payload.get("domain", "") or "").strip() or None
                    self._send_json({"ok": True, "result": app.service.get_task_status(task_id=task_id, domain=domain)})
                    return
                if parsed.path == "/api/report":
                    task_id = str(payload.get("task_id", "")).strip()
                    if not task_id:
                        raise WebInputError("task_id is required")
                    domain = str(payload.get("domain", "") or "").strip() or None
                    kind = str(payload.get("kind", "all") or "all")
                    self._send_json({"ok": True, "result": app.service.get_task_report(task_id=task_id, domain=domain, kind=kind)})
                    return
                if parsed.path == "/api/tasks":
                    domain = str(payload.get("domain", "") or "").strip() or None
                    status = str(payload.get("status", "") or "").strip() or None
                    limit_value = payload.get("limit")
                    limit = int(limit_value) if limit_value not in {None, ""} else None
                    self._send_json({"ok": True, "result": app.service.list_task_runs(domain=domain, status=status, limit=limit)})
                    return
                self._send_error_json(HTTPStatus.NOT_FOUND, "route not found")
            except (json.JSONDecodeError, WebInputError, TaskValidationError, FileNotFoundError, ValueError) as exc:
                self._send_error_json(HTTPStatus.BAD_REQUEST, str(exc))
            except Exception as exc:  # pragma: no cover - safety net for the local tool server
                self._send_error_json(HTTPStatus.INTERNAL_SERVER_ERROR, str(exc))

        def log_message(self, format: str, *args: object) -> None:  # noqa: A003
            return

        def _read_json_body(self) -> dict[str, Any]:
            length_header = self.headers.get("Content-Length", "0")
            try:
                content_length = int(length_header)
            except ValueError as exc:
                raise WebInputError("invalid Content-Length") from exc
            if content_length < 1:
                raise WebInputError("request body is required")
            if content_length > MAX_REQUEST_BYTES:
                raise WebInputError(f"request body too large: {content_length} bytes")
            raw = self.rfile.read(content_length)
            return json.loads(raw.decode("utf-8"))

        def _send_static(self, name: str, content_type: str) -> None:
            path = app.static_dir / name
            if not path.exists():
                self._send_error_json(HTTPStatus.NOT_FOUND, f"static file not found: {name}")
                return
            payload = path.read_bytes()
            self.send_response(HTTPStatus.OK)
            self._send_common_headers(content_type=content_type, content_length=len(payload))
            self.end_headers()
            self.wfile.write(payload)

        def _send_json(self, payload: dict[str, Any], status: HTTPStatus = HTTPStatus.OK) -> None:
            raw = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
            self.send_response(status)
            self._send_common_headers(content_type="application/json; charset=utf-8", content_length=len(raw))
            self.end_headers()
            self.wfile.write(raw)

        def _send_error_json(self, status: HTTPStatus, message: str) -> None:
            self._send_json({"ok": False, "error": message}, status=status)

        def _send_common_headers(self, *, content_type: str, content_length: int) -> None:
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(content_length))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; object-src 'none'; base-uri 'self'; frame-ancestors 'none'")

    return WebHandler


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    app = WebApplication(base_dir=Path(args.base_dir))
    handler = make_handler(app)
    server = ThreadingHTTPServer((args.host, args.port), handler)
    print(f"db-output web available at http://{args.host}:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())