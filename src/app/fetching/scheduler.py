from __future__ import annotations

from collections.abc import Iterable

from app.fetching.client import FetchClient
from app.fetching.models import FetchRequest, FetchResponse
from app.models.source_profile import SourceProfile
from app.models.task_spec import TaskSpec


class Scheduler:
    def __init__(self, fetch_client: FetchClient) -> None:
        self.fetch_client = fetch_client

    def fetch(self, request: FetchRequest, profile: SourceProfile, task: TaskSpec) -> FetchResponse:
        return self.fetch_client.fetch(request=request, profile=profile, task=task)

    def fetch_all(self, requests: Iterable[FetchRequest], profile: SourceProfile, task: TaskSpec) -> list[FetchResponse]:
        return [self.fetch(request=request, profile=profile, task=task) for request in requests]
