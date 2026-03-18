from __future__ import annotations

from typing import Protocol

from app.models.records import NormalizedRecord, RunArtifacts


class Writer(Protocol):
    def write(self, run_summary: dict, records: list[NormalizedRecord], artifacts: RunArtifacts) -> None:
        ...
