from __future__ import annotations

import gzip
import json
from pathlib import Path
from typing import Iterable

from app.models.records import RawRecord


class RawStore:
    def write(self, path: Path, records: Iterable[RawRecord]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with gzip.open(path, "wt", encoding="utf-8") as handle:
            for record in records:
                handle.write(json.dumps(record.to_dict(), ensure_ascii=False) + "\n")
