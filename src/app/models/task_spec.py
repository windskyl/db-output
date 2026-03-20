from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


class TaskValidationError(ValueError):
    """Raised when a task spec fails validation."""


@dataclass(slots=True)
class TimeRange:
    start: str
    end: str
    timezone: str = "UTC"

    def validate(self) -> None:
        start_dt = datetime.fromisoformat(self.start)
        end_dt = datetime.fromisoformat(self.end)
        if start_dt > end_dt:
            raise TaskValidationError("time_range.start must be earlier than or equal to time_range.end")


@dataclass(slots=True)
class SourcePolicy:
    whitelist: list[str] = field(default_factory=list)
    blacklist: list[str] = field(default_factory=list)
    selection_mode: str = 'auto'
    prefer_official: bool = False
    allow_rss: bool = True
    allow_api: bool = True
    allow_html: bool = True
    max_sources: int = 10

    def validate(self) -> None:
        if self.selection_mode not in {'auto', 'explicit'}:
            raise TaskValidationError('source_policy.selection_mode must be auto or explicit')
        if self.max_sources < 1:
            raise TaskValidationError('source_policy.max_sources must be >= 1')
        if self.selection_mode == 'explicit' and not self.whitelist:
            raise TaskValidationError('source_policy.whitelist is required when selection_mode=explicit')


@dataclass(slots=True)
class RelevancePolicy:
    require_target_match: bool = True
    require_topic_match: bool = True
    require_cooccurrence: bool = False
    min_relevance_score: float = 0.5

    def validate(self) -> None:
        if not 0 <= self.min_relevance_score <= 1:
            raise TaskValidationError("relevance_policy.min_relevance_score must be within [0, 1]")


@dataclass(slots=True)
class QualityPolicy:
    required_fields: list[str] = field(default_factory=list)
    dedupe_mode: str = "strict"
    max_missing_ratio: float = 0.2

    def validate(self) -> None:
        if self.dedupe_mode not in {"strict", "none"}:
            raise TaskValidationError("quality_policy.dedupe_mode must be strict or none")
        if not 0 <= self.max_missing_ratio <= 1:
            raise TaskValidationError("quality_policy.max_missing_ratio must be within [0, 1]")


@dataclass(slots=True)
class OutputPolicy:
    writer: str = "sqlite"
    keep_raw: bool = True
    keep_normalized: bool = True
    max_output_records: int = 1000
    update_mode: str = "replace"


@dataclass(slots=True)
class RunPolicy:
    max_concurrency: int = 4
    timeout_seconds: int = 20
    retry_times: int = 3
    enable_cache: bool = True
    allow_browser: bool = False

    def validate(self) -> None:
        if self.max_concurrency < 1:
            raise TaskValidationError("run_policy.max_concurrency must be >= 1")
        if self.timeout_seconds < 1:
            raise TaskValidationError("run_policy.timeout_seconds must be >= 1")
        if self.retry_times < 0:
            raise TaskValidationError("run_policy.retry_times must be >= 0")


@dataclass(slots=True)
class TaskSpec:
    task_id: str
    domain: str
    targets: list[dict[str, Any]]
    topic_scope: list[str]
    time_range: TimeRange
    scenario_template: str | None = None
    geo_scope: dict[str, Any] | None = None
    source_policy: SourcePolicy = field(default_factory=SourcePolicy)
    relevance_policy: RelevancePolicy = field(default_factory=RelevancePolicy)
    quality_policy: QualityPolicy = field(default_factory=QualityPolicy)
    output_policy: OutputPolicy = field(default_factory=OutputPolicy)
    run_policy: RunPolicy = field(default_factory=RunPolicy)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "TaskSpec":
        required = ["task_id", "domain", "targets", "topic_scope", "time_range"]
        missing = [key for key in required if key not in payload]
        if missing:
            raise TaskValidationError(f"missing required fields: {', '.join(missing)}")
        task = cls(
            task_id=str(payload["task_id"]),
            scenario_template=payload.get("scenario_template"),
            domain=str(payload["domain"]),
            targets=list(payload["targets"]),
            topic_scope=list(payload["topic_scope"]),
            time_range=TimeRange(**payload["time_range"]),
            geo_scope=payload.get("geo_scope"),
            source_policy=SourcePolicy(**payload.get("source_policy", {})),
            relevance_policy=RelevancePolicy(**payload.get("relevance_policy", {})),
            quality_policy=QualityPolicy(**payload.get("quality_policy", {})),
            output_policy=OutputPolicy(**payload.get("output_policy", {})),
            run_policy=RunPolicy(**payload.get("run_policy", {})),
        )
        task.validate()
        return task

    def validate(self) -> None:
        if not self.task_id.strip():
            raise TaskValidationError("task_id must not be empty")
        if not self.domain.strip():
            raise TaskValidationError("domain must not be empty")
        if not self.targets:
            raise TaskValidationError("targets must not be empty")
        if not self.topic_scope:
            raise TaskValidationError("topic_scope must not be empty")
        self.time_range.validate()
        self.source_policy.validate()
        self.relevance_policy.validate()
        self.quality_policy.validate()
        self.run_policy.validate()

    def to_summary(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "domain": self.domain,
            "scenario_template": self.scenario_template,
            "target_count": len(self.targets),
            "topic_scope": self.topic_scope,
            "time_range": {
                "start": self.time_range.start,
                "end": self.time_range.end,
                "timezone": self.time_range.timezone,
            },
            "selection_mode": self.source_policy.selection_mode,
        }