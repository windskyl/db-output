from __future__ import annotations

import json
import re
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any


ALLOWED_DOCUMENT_EXTENSIONS = {".json", ".md", ".txt"}
MAX_DOCUMENT_BYTES = 300_000
MAX_PREVIEW_CHARS = 4000


class WebInputError(ValueError):
    pass


DEFAULT_SCENARIO_BY_DOMAIN = {
    "jobs": "job_hunt_engineering_basic",
    "company_intel": "company_due_diligence",
    "finance": "investment_market_quote_basic",
    "public_sentiment": "company_sentiment_tracking_basic",
}

DEFAULT_TOPIC_BY_DOMAIN = {
    "jobs": ["backend"],
    "company_intel": ["company_profile"],
    "finance": ["market_quote"],
    "public_sentiment": ["tech_stack_engineering"],
}

DEFAULT_TARGET_TYPE_BY_DOMAIN = {
    "jobs": "keyword",
    "company_intel": "company",
    "finance": "ticker",
    "public_sentiment": "company",
}

DOMAIN_KEYWORDS = {
    "jobs": ["job", "jobs", "hiring", "recruit", "position", "招聘", "岗位", "求职", "职位"],
    "company_intel": ["company", "profile", "update", "report", "company intel", "企业", "公司", "画像", "产品更新", "技术博客"],
    "finance": ["finance", "ticker", "quote", "earnings", "market", "sec", "stock", "财报", "行情", "股票", "基金"],
    "public_sentiment": ["sentiment", "discussion", "forum", "reputation", "舆情", "评价", "讨论", "论坛", "情绪"],
}

TOPIC_KEYWORDS = {
    "jobs": {
        "backend": ["backend", "back end", "api", "server", "python", "后端", "服务端"],
        "frontend": ["frontend", "front end", "react", "ui", "前端"],
        "algorithm": ["algorithm", "leetcode", "算法"],
        "testing": ["testing", "qa", "test automation", "测试"],
        "devops": ["devops", "docker", "kubernetes", "terraform", "运维"],
        "data_engineering": ["data", "etl", "warehouse", "pipeline", "数据工程"],
        "client": ["client", "mobile", "desktop", "客户端"],
    },
    "company_intel": {
        "company_profile": ["profile", "ranking", "report", "画像", "排名", "市场"],
        "product_update": ["update", "release", "launch", "升级", "发布", "更新"],
        "tech_blog": ["tech", "blog", "guide", "platform", "技术", "方案", "博客"],
        "open_source_activity": ["open source", "github", "开源"],
        "funding_event": ["funding", "ipo", "融资", "上市"],
        "career_page": ["career", "jobs", "招聘", "校招"],
    },
    "finance": {
        "market_quote": ["quote", "price", "market", "行情", "价格", "股价"],
        "company_announcement": ["announcement", "sec", "press release", "公告"],
        "financial_report": ["earnings", "financial report", "财报", "业绩"],
        "fund_holding": ["fund", "holding", "持仓", "基金"],
        "investment_news": ["investment", "news", "投融资", "新闻"],
    },
    "public_sentiment": {
        "interview_experience": ["interview", "offer", "candidate", "面试", "候选人"],
        "salary_benefits": ["salary", "compensation", "equity", "薪资", "福利"],
        "workload_overtime": ["overtime", "burnout", "workload", "加班", "强度"],
        "management_culture": ["management", "leadership", "culture", "管理", "文化"],
        "tech_stack_engineering": ["api", "sdk", "engineering", "model", "agent", "技术", "工程", "模型"],
        "layoff_hiring_freeze": ["layoff", "headcount", "裁员", "冻结招聘"],
        "remote_office_policy": ["remote", "hybrid", "office", "远程", "到岗"],
    },
}

EXPLICIT_FIELD_PATTERNS = {
    "domain": re.compile(r"(?im)^(?:domain|领域)\s*[:：]\s*(?P<value>.+?)\s*$"),
    "target": re.compile(r"(?im)^(?:target|targets|目标|公司|关键词|ticker|股票|实体)\s*[:：]\s*(?P<value>.+?)\s*$"),
    "topics": re.compile(r"(?im)^(?:topic|topics|topic_scope|主题|话题)\s*[:：]\s*(?P<value>.+?)\s*$"),
    "start": re.compile(r"(?im)^(?:start|开始|from)\s*[:：]\s*(?P<value>\d{4}-\d{2}-\d{2})\s*$"),
    "end": re.compile(r"(?im)^(?:end|结束|to)\s*[:：]\s*(?P<value>\d{4}-\d{2}-\d{2})\s*$"),
    "scenario": re.compile(r"(?im)^(?:scenario|scenario_template|场景)\s*[:：]\s*(?P<value>.+?)\s*$"),
}

FENCED_JSON_PATTERN = re.compile(r"```json\s*(?P<payload>\{.*?\})\s*```", re.IGNORECASE | re.DOTALL)
DATE_PATTERN = re.compile(r"\d{4}-\d{2}-\d{2}")
COMMON_TARGET_HINTS = [
    "OpenAI",
    "ChatGPT",
    "Claude",
    "Python",
    "IBM",
    "奇安信",
    "阿里巴巴",
    "腾讯",
    "字节跳动",
]


def validate_uploaded_text(filename: str, content: str) -> dict[str, Any]:
    safe_name = Path(str(filename or "uploaded.txt")).name
    extension = Path(safe_name).suffix.lower()
    if extension not in ALLOWED_DOCUMENT_EXTENSIONS:
        raise WebInputError(f"unsupported file type: {extension or '(none)'}")
    if not isinstance(content, str):
        raise WebInputError("document content must be text")
    if "\x00" in content:
        raise WebInputError("binary content is not allowed")
    size_bytes = len(content.encode("utf-8"))
    if size_bytes > MAX_DOCUMENT_BYTES:
        raise WebInputError(f"document is too large: {size_bytes} bytes")
    return {
        "filename": safe_name,
        "extension": extension,
        "size_bytes": size_bytes,
        "line_count": len(content.splitlines()),
        "preview": content[:MAX_PREVIEW_CHARS],
    }


def build_task_payload_from_form(form: dict[str, Any], now: datetime | None = None) -> dict[str, Any]:
    now = now or datetime.now(UTC)
    domain = str(form.get("domain", "")).strip()
    if not domain:
        raise WebInputError("domain is required")

    target_value = str(form.get("target_value", "")).strip()
    if not target_value:
        raise WebInputError("target_value is required")
    target_type = str(form.get("target_type", "") or DEFAULT_TARGET_TYPE_BY_DOMAIN.get(domain, "keyword")).strip()
    topic_scope = _coerce_string_list(form.get("topic_scope"))
    if not topic_scope:
        topic_scope = list(DEFAULT_TOPIC_BY_DOMAIN.get(domain, []))
    if not topic_scope:
        raise WebInputError("topic_scope is required")

    time_range = _build_time_range(
        start_value=str(form.get("start", "") or "").strip(),
        end_value=str(form.get("end", "") or "").strip(),
        timezone=str(form.get("timezone", "UTC") or "UTC").strip(),
        now=now,
    )

    whitelist = _coerce_string_list(form.get("whitelist"))
    selection_mode = str(form.get("selection_mode", "") or ("explicit" if whitelist else "auto")).strip() or "auto"
    allow_html = _coerce_bool(form.get("allow_html"), True)
    allow_rss = _coerce_bool(form.get("allow_rss"), True)
    allow_api = _coerce_bool(form.get("allow_api"), True)

    payload = {
        "task_id": str(form.get("task_id", "")).strip() or _generate_task_id(domain, target_value, now),
        "scenario_template": str(form.get("scenario_template", "") or DEFAULT_SCENARIO_BY_DOMAIN.get(domain, "")).strip() or None,
        "domain": domain,
        "targets": [
            {
                "type": target_type,
                "value": target_value,
            }
        ],
        "topic_scope": topic_scope,
        "time_range": time_range,
        "source_policy": {
            "selection_mode": selection_mode,
            "whitelist": whitelist,
            "blacklist": [],
            "prefer_official": _coerce_bool(form.get("prefer_official"), False),
            "allow_html": allow_html,
            "allow_rss": allow_rss,
            "allow_api": allow_api,
            "max_sources": _coerce_int(form.get("max_sources"), 3),
        },
        "relevance_policy": {
            "require_target_match": True,
            "require_topic_match": domain in {"finance", "public_sentiment"},
            "require_cooccurrence": False,
            "min_relevance_score": _coerce_float(form.get("min_relevance_score"), 0.6),
        },
        "quality_policy": {
            "required_fields": ["title", "source_url", "published_at"],
            "dedupe_mode": "strict",
            "max_missing_ratio": 0.2,
        },
        "output_policy": {
            "writer": "sqlite",
            "keep_raw": True,
            "keep_normalized": True,
            "max_output_records": _coerce_int(form.get("max_output_records"), 1000),
            "update_mode": "replace",
        },
        "run_policy": {
            "max_concurrency": _coerce_int(form.get("max_concurrency"), 4),
            "timeout_seconds": _coerce_int(form.get("timeout_seconds"), 20),
            "retry_times": _coerce_int(form.get("retry_times"), 2),
            "enable_cache": _coerce_bool(form.get("enable_cache"), False),
            "allow_browser": False,
        },
    }
    return payload


def extract_task_payload_from_document(filename: str, content: str, now: datetime | None = None) -> dict[str, Any]:
    now = now or datetime.now(UTC)
    document_meta = validate_uploaded_text(filename, content)
    warnings: list[str] = []

    json_payload = _try_parse_task_json(content)
    if json_payload is not None:
        return {
            "mode": "json",
            "warnings": warnings,
            "document": document_meta,
            "task_payload": json_payload,
        }

    json_block_payload = _extract_fenced_json_payload(content)
    if json_block_payload is not None:
        warnings.append("Imported the first fenced JSON task block from the document.")
        return {
            "mode": "json_block",
            "warnings": warnings,
            "document": document_meta,
            "task_payload": json_block_payload,
        }

    heuristic_payload, heuristic_warnings = _build_task_payload_from_text(content, now=now)
    warnings.extend(heuristic_warnings)
    return {
        "mode": "heuristic",
        "warnings": warnings,
        "document": document_meta,
        "task_payload": heuristic_payload,
    }


def summarize_example_tasks(example_dir: Path) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    if not example_dir.exists():
        return items
    for path in sorted(example_dir.glob("*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8-sig"))
            items.append(
                {
                    "name": path.name,
                    "task_id": payload.get("task_id"),
                    "domain": payload.get("domain"),
                    "scenario_template": payload.get("scenario_template"),
                    "topic_scope": payload.get("topic_scope", []),
                }
            )
        except Exception:
            items.append({"name": path.name})
    return items


def load_example_task(example_dir: Path, name: str) -> dict[str, Any]:
    path = example_dir / Path(name).name
    if not path.exists() or path.suffix.lower() != ".json":
        raise FileNotFoundError(f"example task not found: {name}")
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _try_parse_task_json(content: str) -> dict[str, Any] | None:
    stripped = content.strip()
    if not stripped:
        return None
    if not (stripped.startswith("{") and stripped.endswith("}")):
        return None
    payload = json.loads(stripped)
    if isinstance(payload, dict) and payload.get("task") and isinstance(payload["task"], dict):
        return dict(payload["task"])
    if not isinstance(payload, dict):
        raise WebInputError("JSON task document must contain an object payload")
    return payload


def _extract_fenced_json_payload(content: str) -> dict[str, Any] | None:
    match = FENCED_JSON_PATTERN.search(content)
    if not match:
        return None
    return json.loads(match.group("payload"))


def _build_task_payload_from_text(content: str, now: datetime) -> tuple[dict[str, Any], list[str]]:
    warnings = [
        "This draft was inferred from plain text. Review the generated JSON before validation or running.",
    ]
    explicit = {name: _extract_explicit_field(pattern, content) for name, pattern in EXPLICIT_FIELD_PATTERNS.items()}
    domain = _normalize_domain(explicit.get("domain") or _infer_domain(content))
    if not domain:
        domain = "jobs"
        warnings.append("Domain could not be inferred reliably. Defaulted to jobs.")

    target_value = explicit.get("target") or _infer_target_value(content, domain)
    if not target_value:
        target_value = "OpenAI" if domain == "public_sentiment" else "Python"
        warnings.append("Target could not be inferred reliably. A placeholder target was used.")

    topics = _coerce_string_list(explicit.get("topics"))
    if not topics:
        topics = _infer_topics(content, domain)
    if not topics:
        topics = list(DEFAULT_TOPIC_BY_DOMAIN.get(domain, []))
        warnings.append("Topics could not be inferred reliably. Default topics were used.")

    start_value = explicit.get("start") or ""
    end_value = explicit.get("end") or ""
    if not start_value and not end_value:
        date_matches = DATE_PATTERN.findall(content)
        if len(date_matches) >= 2:
            start_value, end_value = date_matches[0], date_matches[1]
        elif len(date_matches) == 1:
            start_value = end_value = date_matches[0]
    payload = build_task_payload_from_form(
        {
            "domain": domain,
            "scenario_template": explicit.get("scenario") or DEFAULT_SCENARIO_BY_DOMAIN.get(domain, ""),
            "target_type": DEFAULT_TARGET_TYPE_BY_DOMAIN.get(domain, "keyword"),
            "target_value": target_value,
            "topic_scope": topics,
            "start": start_value,
            "end": end_value,
            "timezone": "UTC",
            "selection_mode": "auto",
            "allow_html": True,
            "allow_rss": True,
            "allow_api": True,
            "enable_cache": False,
        },
        now=now,
    )
    return payload, warnings


def _extract_explicit_field(pattern: re.Pattern[str], content: str) -> str | None:
    match = pattern.search(content)
    if not match:
        return None
    return str(match.group("value")).strip()


def _infer_domain(content: str) -> str | None:
    lowered = content.lower()
    scores: dict[str, int] = {domain: 0 for domain in DOMAIN_KEYWORDS}
    for domain, keywords in DOMAIN_KEYWORDS.items():
        for keyword in keywords:
            if keyword.lower() in lowered:
                scores[domain] += 1
    best_domain = max(scores, key=scores.get)
    return best_domain if scores[best_domain] > 0 else None


def _infer_target_value(content: str, domain: str) -> str | None:
    for hint in COMMON_TARGET_HINTS:
        if hint.lower() in content.lower():
            return hint
    if domain == "finance":
        ticker_match = re.search(r"\b[A-Z]{1,5}\b", content)
        if ticker_match:
            return ticker_match.group(0)
    quoted_match = re.search(r'["“](.{2,40})["”]', content)
    if quoted_match:
        return quoted_match.group(1).strip()
    line_match = re.search(r"(?im)^(?:for|about)\s+([A-Za-z][A-Za-z0-9_. -]{2,40})\s*$", content)
    if line_match:
        return line_match.group(1).strip()
    return None


def _infer_topics(content: str, domain: str) -> list[str]:
    lowered = content.lower()
    matches = []
    for topic, keywords in TOPIC_KEYWORDS.get(domain, {}).items():
        if any(keyword.lower() in lowered for keyword in keywords):
            matches.append(topic)
    return matches


def _coerce_string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        candidates = re.split(r"[,\n;|]", value)
    elif isinstance(value, (list, tuple, set)):
        candidates = [str(item) for item in value]
    else:
        candidates = [str(value)]
    result = []
    seen: set[str] = set()
    for candidate in candidates:
        item = str(candidate).strip()
        if not item:
            continue
        if item in seen:
            continue
        seen.add(item)
        result.append(item)
    return result


def _build_time_range(start_value: str, end_value: str, timezone: str, now: datetime) -> dict[str, str]:
    end_dt = now.astimezone(UTC)
    start_dt = end_dt - timedelta(days=30)
    if start_value:
        start_iso = f"{start_value}T00:00:00"
    else:
        start_iso = start_dt.strftime("%Y-%m-%dT00:00:00")
    if end_value:
        end_iso = f"{end_value}T23:59:59"
    else:
        end_iso = end_dt.strftime("%Y-%m-%dT23:59:59")
    return {
        "start": start_iso,
        "end": end_iso,
        "timezone": timezone or "UTC",
    }


def _generate_task_id(domain: str, target_value: str, now: datetime) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", target_value.lower()).strip("-") or "task"
    return f"web-{domain}-{slug[:24]}-{now.strftime('%Y%m%d%H%M%S')}"


def _coerce_bool(value: Any, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    lowered = str(value).strip().lower()
    if lowered in {"1", "true", "yes", "on"}:
        return True
    if lowered in {"0", "false", "no", "off"}:
        return False
    return default


def _coerce_int(value: Any, default: int) -> int:
    if value in {None, ""}:
        return default
    try:
        return int(value)
    except Exception:
        return default


def _coerce_float(value: Any, default: float) -> float:
    if value in {None, ""}:
        return default
    try:
        return float(value)
    except Exception:
        return default


def _normalize_domain(value: str | None) -> str | None:
    if not value:
        return None
    lowered = str(value).strip().lower()
    aliases = {
        "jobs": "jobs",
        "job": "jobs",
        "finance": "finance",
        "company_intel": "company_intel",
        "company": "company_intel",
        "public_sentiment": "public_sentiment",
        "sentiment": "public_sentiment",
        "舆情": "public_sentiment",
        "公司": "company_intel",
        "金融": "finance",
        "招聘": "jobs",
    }
    return aliases.get(lowered, lowered if lowered in DEFAULT_SCENARIO_BY_DOMAIN else None)