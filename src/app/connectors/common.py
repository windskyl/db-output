from __future__ import annotations

from typing import Any

from app.models.source_profile import SourceProfile
from app.models.task_spec import TaskSpec


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
        mapped_terms = profile.topic_terms.get(topic)
        if mapped_terms:
            terms.extend(str(term).strip() for term in mapped_terms if str(term).strip())
        else:
            fallback = str(topic).replace('_', ' ').strip()
            if fallback:
                terms.append(fallback)
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
    haystack = build_haystack(profile, payload)
    topic_terms = [term.lower() for term in resolve_topic_terms(profile, task)]
    if not topic_terms:
        return True
    return any(term in haystack for term in topic_terms)


def build_haystack(profile: SourceProfile, payload: dict[str, Any]) -> str:
    fields = profile.text_match_fields or list(payload.keys())
    values = []
    for field in fields:
        value = payload.get(field)
        if value is None:
            continue
        values.append(str(value))
    return ' '.join(values).lower()


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
