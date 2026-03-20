from __future__ import annotations

import base64
import hashlib
import json
from pathlib import Path

from app.fetching.models import FetchRequest, FetchResponse


class FetchCache:
    def __init__(self, root_dir: Path | None = None) -> None:
        self.root_dir = root_dir

    def set_root_dir(self, root_dir: Path | None) -> None:
        self.root_dir = root_dir

    def load(self, source_id: str, request: FetchRequest, headers: dict[str, str]) -> FetchResponse | None:
        path = self._entry_path(source_id=source_id, request=request, headers=headers)
        if path is None or not path.exists():
            return None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            body = base64.b64decode(str(payload.get("body_base64", "")).encode("ascii"))
            return FetchResponse(
                request=request,
                url=str(payload.get("url", request.url)),
                final_url=str(payload.get("final_url", request.url)),
                status_code=int(payload["status_code"]),
                headers=dict(payload.get("headers", {})),
                body=body,
                fetched_at=str(payload.get("fetched_at", "")),
                from_cache=True,
            )
        except Exception:
            return None

    def save(self, source_id: str, request: FetchRequest, headers: dict[str, str], response: FetchResponse) -> None:
        path = self._entry_path(source_id=source_id, request=request, headers=headers)
        if path is None:
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "source_id": source_id,
            "method": request.method.upper(),
            "url": request.url,
            "final_url": response.final_url,
            "status_code": response.status_code,
            "headers": response.headers,
            "fetched_at": response.fetched_at,
            "body_base64": base64.b64encode(response.body).decode("ascii"),
        }
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def _entry_path(self, source_id: str, request: FetchRequest, headers: dict[str, str]) -> Path | None:
        if self.root_dir is None:
            return None
        fingerprint_payload = {
            "method": request.method.upper(),
            "url": request.url,
            "headers": self._normalize_headers(headers),
            "body_base64": base64.b64encode(request.body).decode("ascii") if request.body else None,
        }
        fingerprint = hashlib.sha256(
            json.dumps(fingerprint_payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
        ).hexdigest()
        return self.root_dir / source_id / f"{fingerprint}.json"

    def _normalize_headers(self, headers: dict[str, str]) -> dict[str, str]:
        return {
            key.lower(): value
            for key, value in sorted(headers.items())
            if key.lower() not in {"if-none-match", "if-modified-since"}
        }