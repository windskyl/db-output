from __future__ import annotations

from dataclasses import dataclass

from app.models.task_spec import TaskSpec, TaskValidationError


@dataclass(slots=True)
class DomainPlugin:
    name: str
    allowed_topics: set[str]
    requires_topic_scope: bool = True
    requires_targets: bool = True

    def validate_task(self, task: TaskSpec) -> None:
        if task.domain != self.name:
            raise TaskValidationError(f"task domain '{task.domain}' does not match plugin '{self.name}'")
        if self.requires_targets and not task.targets:
            raise TaskValidationError(f"{self.name} requires at least one target")
        if self.requires_topic_scope and not task.topic_scope:
            raise TaskValidationError(f"{self.name} requires at least one topic")
        invalid_topics = [topic for topic in task.topic_scope if topic not in self.allowed_topics]
        if invalid_topics:
            raise TaskValidationError(f"unsupported topics for {self.name}: {', '.join(invalid_topics)}")
