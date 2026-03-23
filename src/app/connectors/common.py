from __future__ import annotations

from typing import Any

from app.models.source_profile import SourceProfile
from app.models.task_spec import TaskSpec


_COMPANY_INTEL_TOPIC_HINTS = {
    'company_profile': (
        '报告',
        '研究',
        '市场',
        '排名',
        '领跑',
        '第一',
        '推荐',
        'gartner',
        'idc',
        '赛迪',
        'marketglance',
        'quadrant',
    ),
    'product_update': (
        '升级公告',
        '产品公告',
        '更新通告',
        '补丁',
        '发布',
        '发布会',
        '上线',
        '推出',
    ),
    'tech_blog': (
        '指南',
        '方案',
        '平台',
        '技术',
        '生态',
        '智能体',
        '实践',
        'openclaw',
        'safeskill',
        'ngsoc',
    ),
}


def build_request_context(profile: SourceProfile, task: TaskSpec, page: int = 1) -> dict[str, str]:
    targets = [str(target.get('value', '')).strip() for target in task.targets if str(target.get('value', '')).strip()]
    topics = [str(topic).strip() for topic in task.topic_scope if str(topic).strip()]
    topic_keywords = resolve_topic_terms(profile, task)
    return {
        'domain': task.domain,
        'source_id': profile.source_id,
        'target': targets[0] if targets else '',
        'targets': ' '.join(targets),
        'topics': ','.join(topics),
        'topic_keywords': ' '.join(topic_keywords),
        'start_date': task.time_range.start[:10],
        'end_date': task.time_range.end[:10],
        'start_datetime': task.time_range.start,
        'end_datetime': task.time_range.end,
        'page': str(page),
    }


def format_template(template: str, context: dict[str, str]) -> str:
    return template.format(**context).strip()


def resolve_topic_terms(profile: SourceProfile, task: TaskSpec) -> list[str]:
    terms: list[str] = []
    for topic in task.topic_scope:
        terms.extend(_resolve_topic_terms_for_topic(profile, str(topic)))
    return _dedupe_preserve_order(terms)


def matches_relevance(profile: SourceProfile, payload: dict[str, Any], task: TaskSpec, scoped_entity: bool = False) -> bool:
    if task.relevance_policy.require_target_match and not scoped_entity and not matches_targets(profile, payload, task):
        return False
    if task.relevance_policy.require_topic_match and not matches_topics(profile, payload, task):
        return False
    return True


def matches_targets(profile: SourceProfile, payload: dict[str, Any], task: TaskSpec) -> bool:
    haystack = build_haystack(profile, payload)
    targets = [str(target.get('value', '')).strip().lower() for target in task.targets if str(target.get('value', '')).strip()]
    return any(target in haystack for target in targets)


def matches_topics(profile: SourceProfile, payload: dict[str, Any], task: TaskSpec) -> bool:
    if not task.topic_scope:
        return True
    return bool(matched_topics(profile, payload, task))


def matched_topics(profile: SourceProfile, payload: dict[str, Any], task: TaskSpec) -> list[str]:
    existing = payload.get('matched_topics')
    if existing is not None:
        return _coerce_topics(existing)

    haystack = build_haystack(profile, payload)
    matched: list[str] = []
    for topic in task.topic_scope:
        topic_name = str(topic).strip()
        if not topic_name:
            continue
        topic_terms = [term.lower() for term in _resolve_topic_terms_for_topic(profile, topic_name)]
        if topic_terms and any(term in haystack for term in topic_terms):
            matched.append(topic_name)
    matched.extend(_domain_specific_topics(profile, payload, task, haystack))
    return _dedupe_preserve_order(matched)


def build_haystack(profile: SourceProfile, payload: dict[str, Any]) -> str:
    fields = profile.text_match_fields or list(payload.keys())
    values = []
    for field in fields:
        value = payload.get(field)
        if value is None:
            continue
        values.append(str(value))
    return ' '.join(values).lower()


def _domain_specific_topics(profile: SourceProfile, payload: dict[str, Any], task: TaskSpec, haystack: str) -> list[str]:
    if task.domain != 'company_intel':
        return []

    allowed = {str(topic).strip() for topic in task.topic_scope if str(topic).strip()}
    source_type = str(profile.source_type or '').strip().lower()
    source_tag = str(payload.get('tag', payload.get('category', '')) or '').strip().lower()
    title = str(payload.get('title', '') or '').strip().lower()
    summary = str(payload.get('summary', '') or '').strip().lower()
    combined = ' '.join(part for part in (haystack, source_tag, source_type, title, summary) if part)
    matched: list[str] = []

    if 'company_profile' in allowed and (
        source_type == 'official_company_report'
        or any(hint in combined for hint in _COMPANY_INTEL_TOPIC_HINTS['company_profile'])
    ):
        matched.append('company_profile')

    if 'product_update' in allowed and (
        source_type == 'official_company_update'
        or any(hint in combined for hint in _COMPANY_INTEL_TOPIC_HINTS['product_update'])
    ):
        matched.append('product_update')

    if 'tech_blog' in allowed and (
        source_type == 'official_company_news'
        or any(hint in combined for hint in _COMPANY_INTEL_TOPIC_HINTS['tech_blog'])
    ):
        matched.append('tech_blog')

    return matched


def _dedupe_preserve_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        key = value.lower()
        if key in seen:
            continue
        seen.add(key)
        result.append(value)
    return result


def _resolve_topic_terms_for_topic(profile: SourceProfile, topic: str) -> list[str]:
    mapped_terms = profile.topic_terms.get(topic)
    if mapped_terms:
        return [str(term).strip() for term in mapped_terms if str(term).strip()]
    fallback = str(topic).replace('_', ' ').strip()
    return [fallback] if fallback else []


def _coerce_topics(value: Any) -> list[str]:
    if isinstance(value, str):
        values = [value]
    elif isinstance(value, (list, tuple, set)):
        values = [str(item) for item in value]
    else:
        return []
    return _dedupe_preserve_order([item.strip() for item in values if item and str(item).strip()])