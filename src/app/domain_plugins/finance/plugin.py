from app.domain_plugins.base import DomainPlugin

plugin = DomainPlugin(
    name="finance",
    allowed_topics={
        "market_quote",
        "company_announcement",
        "financial_report",
        "fund_holding",
        "investment_news",
    },
)
