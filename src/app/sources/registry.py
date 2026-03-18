from __future__ import annotations

from pathlib import Path

from app.models.source_profile import SourceProfile
from app.models.task_spec import TaskSpec


class SourceRegistry:
    def __init__(self, config_root: Path) -> None:
        self.config_root = config_root
        self._profiles = self._load_profiles()

    def _load_profiles(self) -> dict[str, SourceProfile]:
        profiles: dict[str, SourceProfile] = {}
        if not self.config_root.exists():
            return profiles
        for path in sorted(self.config_root.rglob('*.json')):
            profile = SourceProfile.from_file(path)
            profiles[profile.source_id] = profile
        return profiles

    def get(self, source_id: str) -> SourceProfile:
        return self._profiles[source_id]

    def list_for_task(self, task: TaskSpec) -> list[SourceProfile]:
        candidates = [profile for profile in self._profiles.values() if profile.domain == task.domain]
        whitelist = set(task.source_policy.whitelist)
        blacklist = set(task.source_policy.blacklist)
        if whitelist:
            candidates = [profile for profile in candidates if profile.source_id in whitelist]
        if blacklist:
            candidates = [profile for profile in candidates if profile.source_id not in blacklist]
        candidates.sort(key=lambda profile: profile.source_id)
        return candidates[: task.source_policy.max_sources]
