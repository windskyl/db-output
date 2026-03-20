from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class TaskPaths:
    base_dir: Path
    domain: str
    task_id: str

    @property
    def raw_dir(self) -> Path:
        return self.base_dir / "raw" / self.domain / self.task_id

    @property
    def normalized_dir(self) -> Path:
        return self.base_dir / "normalized" / self.domain / self.task_id

    @property
    def artifacts_dir(self) -> Path:
        return self.base_dir / "artifacts" / self.domain / self.task_id

    @property
    def cache_dir(self) -> Path:
        return self.base_dir / "cache" / self.domain / self.task_id

    @property
    def raw_file(self) -> Path:
        return self.raw_dir / "source_local.jsonl.gz"

    @property
    def normalized_file(self) -> Path:
        return self.normalized_dir / "normalized.jsonl.gz"

    @property
    def sqlite_file(self) -> Path:
        return self.artifacts_dir / "result.sqlite"

    @property
    def quality_report_file(self) -> Path:
        return self.artifacts_dir / "quality_report.json"

    @property
    def run_report_file(self) -> Path:
        return self.artifacts_dir / "run_report.json"

    def ensure(self) -> None:
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        self.normalized_dir.mkdir(parents=True, exist_ok=True)
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)