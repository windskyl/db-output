from __future__ import annotations

from pathlib import Path

from app.models.source_profile import SourceProfile, SourceProfileValidationError
from app.models.task_spec import TaskSpec, TaskValidationError


class SourceRegistry:
    def __init__(self, config_root: Path) -> None:
        self.config_root = config_root
        self._profiles = self._load_profiles()

    def _load_profiles(self) -> dict[str, SourceProfile]:
        profiles: dict[str, SourceProfile] = {}
        if not self.config_root.exists():
            return profiles
        for path in sorted(self.config_root.rglob('*.json')):
            try:
                profile = SourceProfile.from_file(path)
            except SourceProfileValidationError as exc:
                raise SourceProfileValidationError(f'{path.name}: {exc}') from exc
            profiles[profile.source_id] = profile
        return profiles

    def get(self, source_id: str) -> SourceProfile:
        return self._profiles[source_id]

    def list_profiles(self, domain: str | None = None, channel: str | None = None) -> list[SourceProfile]:
        profiles = list(self._profiles.values())
        if domain:
            profiles = [profile for profile in profiles if profile.domain == domain]
        if channel:
            profiles = [profile for profile in profiles if profile.source_channel == channel]
        profiles.sort(key=lambda profile: (profile.domain, profile.source_id))
        return profiles

    def list_for_task(self, task: TaskSpec) -> list[SourceProfile]:
        candidates = self.list_profiles(domain=task.domain)
        blacklist = set(task.source_policy.blacklist)
        if blacklist:
            candidates = [profile for profile in candidates if profile.source_id not in blacklist]
        candidates = [profile for profile in candidates if self._channel_allowed(profile, task)]

        if task.source_policy.selection_mode == 'explicit':
            whitelist = set(task.source_policy.whitelist)
            candidates = [profile for profile in candidates if profile.source_id in whitelist]
            missing = whitelist - {profile.source_id for profile in candidates}
            if missing:
                raise TaskValidationError(f'explicit sources unavailable for task: {", ".join(sorted(missing))}')
            candidates.sort(key=lambda profile: profile.source_id)
            return candidates[: task.source_policy.max_sources]

        candidates.sort(key=lambda profile: self._sort_key(profile, task))
        return candidates[: task.source_policy.max_sources]

    def _channel_allowed(self, profile: SourceProfile, task: TaskSpec) -> bool:
        return (
            (profile.source_channel != 'html' or task.source_policy.allow_html)
            and (profile.source_channel != 'rss' or task.source_policy.allow_rss)
            and (profile.source_channel != 'api' or task.source_policy.allow_api)
        )

    def _sort_key(self, profile: SourceProfile, task: TaskSpec) -> tuple[int, str]:
        official_priority = 0 if task.source_policy.prefer_official and profile.source_type.startswith('official_') else 1
        return (official_priority, profile.source_id)
