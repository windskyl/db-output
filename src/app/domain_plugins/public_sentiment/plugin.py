from app.domain_plugins.base import DomainPlugin
from app.models.task_spec import TaskSpec, TaskValidationError


class PublicSentimentPlugin(DomainPlugin):
    def validate_task(self, task: TaskSpec) -> None:
        super().validate_task(task)
        if task.relevance_policy.min_relevance_score < 0.5:
            raise TaskValidationError(
                "public_sentiment requires relevance_policy.min_relevance_score >= 0.5"
            )


plugin = PublicSentimentPlugin(
    name="public_sentiment",
    allowed_topics={
        "interview_experience",
        "salary_benefits",
        "workload_overtime",
        "management_culture",
        "tech_stack_engineering",
        "layoff_hiring_freeze",
        "remote_office_policy",
    },
)
