from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any


@dataclass(slots=True)
class RawRecord:
    task_id: str
    domain: str
    source_id: str
    source_type: str
    source_label: str
    fetched_at: str
    request_url: str
    http_status: int
    content_hash: str
    raw_payload: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class NormalizedRecord:
    task_id: str
    domain: str
    record_id: str
    dedupe_key: str
    source_id: str
    source_type: str
    source_label: str
    source_tag: str
    source_url: str
    published_at: str
    collected_at: str
    primary_entity: str
    entity_tags: list[str] = field(default_factory=list)
    topic_tags: list[str] = field(default_factory=list)
    title: str = ""
    content_text: str = ""
    relevance_score: float = 0.0
    quality_flags: list[str] = field(default_factory=list)
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class RunArtifacts:
    task_id: str
    domain: str
    raw_file: str
    normalized_file: str
    sqlite_file: str
    quality_report_file: str
    run_report_file: str
    cache_dir: str | None = None
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())