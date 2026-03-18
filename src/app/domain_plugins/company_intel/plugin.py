from app.domain_plugins.base import DomainPlugin

plugin = DomainPlugin(
    name="company_intel",
    allowed_topics={
        "company_profile",
        "product_update",
        "tech_blog",
        "open_source_activity",
        "funding_event",
        "career_page",
    },
)
