from app.domain_plugins.base import DomainPlugin
from app.domain_plugins.company_intel.plugin import plugin as company_intel_plugin
from app.domain_plugins.finance.plugin import plugin as finance_plugin
from app.domain_plugins.jobs.plugin import plugin as jobs_plugin
from app.domain_plugins.public_sentiment.plugin import plugin as public_sentiment_plugin
from app.models.task_spec import TaskValidationError


class DomainRegistry:
    def __init__(self) -> None:
        self._plugins: dict[str, DomainPlugin] = {
            finance_plugin.name: finance_plugin,
            jobs_plugin.name: jobs_plugin,
            company_intel_plugin.name: company_intel_plugin,
            public_sentiment_plugin.name: public_sentiment_plugin,
        }

    def get(self, name: str) -> DomainPlugin:
        try:
            return self._plugins[name]
        except KeyError as exc:
            raise TaskValidationError(f"unsupported domain: {name}") from exc

    def names(self) -> list[str]:
        return sorted(self._plugins)
