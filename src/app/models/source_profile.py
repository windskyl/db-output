from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class SourceProfile:
    source_id: str
    domain: str
    connector_kind: str
    source_type: str
    source_label: str
    base_url: str
    first_page_url: str
    paged_url_template: str | None = None
    max_pages: int = 1
    item_pattern: str = ""
    item_pattern_flags: list[str] = field(default_factory=list)
    field_patterns: dict[str, str] = field(default_factory=dict)
    field_pattern_flags: list[str] = field(default_factory=list)
    clean_fields: list[str] = field(default_factory=list)
    entity_scope: list[str] = field(default_factory=list)
    text_match_fields: list[str] = field(default_factory=list)
    pagination_pattern: str | None = None
    stop_on_older_items: bool = True
    decode_html_entities: bool = True

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "SourceProfile":
        return cls(**payload)

    @classmethod
    def from_file(cls, path: Path) -> "SourceProfile":
        import json
        payload = json.loads(path.read_text(encoding='utf-8-sig'))
        return cls.from_dict(payload)
