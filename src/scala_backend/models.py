from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

type JsonValue = Any
type JsonObject = dict[str, Any]
type JsonId = str | int | None


class AgentName(StrEnum):
    """pipeline stage와 monitoring usage에서 쓰는 agent key를 제한한다."""

    ORCHESTRATOR = "orchestrator"
    SCHEMA_PROFILER = "schema_profiler"
    NORMALIZATION = "normalization"
    VALIDATOR = "validator"
    LOAD = "load"
    CACHING = "caching"
    LINEAGE = "lineage"


LLM_AGENTS = (
    AgentName.ORCHESTRATOR,
    AgentName.SCHEMA_PROFILER,
    AgentName.NORMALIZATION,
    AgentName.VALIDATOR,
)

ALL_AGENTS = (
    AgentName.ORCHESTRATOR,
    AgentName.SCHEMA_PROFILER,
    AgentName.NORMALIZATION,
    AgentName.VALIDATOR,
    AgentName.LOAD,
    AgentName.CACHING,
    AgentName.LINEAGE,
)


class SourceSelection(BaseModel):
    """pipeline.run과 samples.fetch가 받을 source solution/index 쌍이다."""

    model_config = ConfigDict(frozen=True)

    solution: Literal["elasticsearch", "splunk"]
    index: str = Field(min_length=1)


class FieldSample(BaseModel):
    """schema profiling에서 수집한 field 이름, 타입, 예시 값이다."""

    model_config = ConfigDict(frozen=True)

    name: str
    type: str
    samples: list[JsonValue] = Field(default_factory=list, max_length=5)


class SettingsSetParams(BaseModel):
    """settings.set이 수정할 설정 key와 JSON 값을 검증한다."""

    model_config = ConfigDict(frozen=True)

    key: str = Field(pattern=r"^(agent|model|source|output|console)\.")
    value: JsonValue


class SamplesFetchParams(BaseModel):
    """samples.fetch가 조회할 여러 source를 담는다."""

    model_config = ConfigDict(frozen=True)

    sources: list[SourceSelection]


class PipelineRunParams(BaseModel):
    """pipeline.run이 정규화할 source 목록을 담는다."""

    model_config = ConfigDict(frozen=True)

    sources: list[SourceSelection]


class LineageLookupParams(BaseModel):
    """lineage.lookup의 OpenSearch document id를 검증한다."""

    model_config = ConfigDict(frozen=True)

    opensearch_id: str = Field(min_length=1)


class MonitoringQueryParams(BaseModel):
    """monitoring.query가 조회할 시간 scope를 제한한다."""

    model_config = ConfigDict(frozen=True)

    scope: Literal["session", "today", "all_time"]


class UsageRecord(BaseModel):
    """agent별 token usage와 model 정보를 저장한다."""

    model_config = ConfigDict(frozen=True)

    run_id: UUID
    agent: AgentName
    model: str | None = None
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    cost_usd: Decimal = Decimal("0")
    last_activity: str = ""
    created_at: datetime


class RunRecord(BaseModel):
    """pipeline run의 상태, 선택 source, 처리 건수를 저장한다."""

    model_config = ConfigDict(frozen=True)

    run_id: UUID
    status: Literal["running", "completed", "failed"]
    selected_sources: list[SourceSelection]
    doc_count: int | None = None
    started_at: datetime
    finished_at: datetime | None = None


class LineageRecord(BaseModel):
    """원본 문서와 OpenSearch 정규화 문서를 연결해 저장한다."""

    model_config = ConfigDict(frozen=True)

    run_id: UUID
    source_solution: str
    source_index: str
    source_doc_id: str
    opensearch_index: str
    opensearch_id: str
    raw_document: JsonObject
    normalized_document: JsonObject
    created_at: datetime


@dataclass(frozen=True)
class RawDocument:
    """connector가 읽어 온 원본 문서 body와 source 식별자다."""

    source_solution: str
    source_index: str
    source_doc_id: str
    body: JsonObject
