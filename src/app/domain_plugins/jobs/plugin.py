from app.domain_plugins.base import DomainPlugin

plugin = DomainPlugin(
    name="jobs",
    allowed_topics={
        "backend",
        "frontend",
        "algorithm",
        "testing",
        "devops",
        "data_engineering",
        "client",
    },
)
