from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


class SourceProfileValidationError(ValueError):
    """Raised when a source profile is invalid."""


@dataclass(slots=True)
class SourceProfile:
    source_id: str
    domain: str
    connector_kind: str
    source_type: str
    source_label: str
    base_url: str
    first_page_url: str
    source_channel: str = 'html'
    paged_url_template: str | None = None
    max_pages: int = 1
    max_items_per_fetch: int = 100
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
    rss_item_fields: dict[str, str] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "SourceProfile":
        profile = cls(**payload)
        profile.validate()
        return profile

    @classmethod
    def from_file(cls, path: Path) -> "SourceProfile":
        import json
        payload = json.loads(path.read_text(encoding='utf-8-sig'))
        return cls.from_dict(payload)

    def validate(self) -> None:
        if not self.source_id:
            raise SourceProfileValidationError('source_id must not be empty')
        if self.connector_kind not in {'regex_html_list', 'rss_feed'}:
            raise SourceProfileValidationError(f'unsupported connector_kind: {self.connector_kind}')
        if self.source_channel not in {'html', 'rss', 'api'}:
            raise SourceProfileValidationError(f'unsupported source_channel: {self.source_channel}')
        if not self.first_page_url:
            raise SourceProfileValidationError('first_page_url must not be empty')
        if self.max_pages < 1:
            raise SourceProfileValidationError('max_pages must be >= 1')
        if self.max_items_per_fetch < 1:
            raise SourceProfileValidationError('max_items_per_fetch must be >= 1')
        if self.connector_kind == 'regex_html_list' and not self.item_pattern:
            raise SourceProfileValidationError('regex_html_list profiles require item_pattern')
        if self.connector_kind == 'rss_feed' and self.source_channel != 'rss':
            raise SourceProfileValidationError('rss_feed profiles must use source_channel=rss')

    def to_summary(self) -> dict[str, Any]:
        return {
            'source_id': self.source_id,
            'domain': self.domain,
            'connector_kind': self.connector_kind,
            'source_channel': self.source_channel,
            'source_type': self.source_type,
            'source_label': self.source_label,
            'base_url': self.base_url,
            'first_page_url': self.first_page_url,
            'max_pages': self.max_pages,
            'max_items_per_fetch': self.max_items_per_fetch,
        }
