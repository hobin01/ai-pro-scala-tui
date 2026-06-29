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
    """백엔드 요청/응답 모델에서 함께 이동해야 하는 상태를 묶는다."""

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
    """백엔드 요청/응답 모델에서 함께 이동해야 하는 상태를 묶는다."""

    model_config = ConfigDict(frozen=True)

    solution: Literal["elasticsearch", "splunk"]
    index: str = Field(min_length=1)


class FieldSample(BaseModel):
    """백엔드 요청/응답 모델에서 함께 이동해야 하는 상태를 묶는다."""

    model_config = ConfigDict(frozen=True)

    name: str
    type: str
    samples: list[JsonValue] = Field(default_factory=list, max_length=5)


class IndexSamples(BaseModel):
    """백엔드 요청/응답 모델에서 함께 이동해야 하는 상태를 묶는다."""

    model_config = ConfigDict(frozen=True)

    solution: str
    index: str
    fields: list[FieldSample]


class SettingsSetParams(BaseModel):
    """백엔드 요청/응답 모델에서 함께 이동해야 하는 상태를 묶는다."""

    model_config = ConfigDict(frozen=True)

    key: str = Field(pattern=r"^(agent|model|source|output|console)\.")
    value: JsonValue


class SamplesFetchParams(BaseModel):
    """백엔드 요청/응답 모델에서 함께 이동해야 하는 상태를 묶는다."""

    model_config = ConfigDict(frozen=True)

    sources: list[SourceSelection]


class PipelineRunParams(BaseModel):
    """백엔드 요청/응답 모델에서 함께 이동해야 하는 상태를 묶는다."""

    model_config = ConfigDict(frozen=True)

    sources: list[SourceSelection]


class LineageLookupParams(BaseModel):
    """백엔드 요청/응답 모델에서 함께 이동해야 하는 상태를 묶는다."""

    model_config = ConfigDict(frozen=True)

    opensearch_id: str = Field(min_length=1)


class MonitoringQueryParams(BaseModel):
    """백엔드 요청/응답 모델에서 함께 이동해야 하는 상태를 묶는다."""

    model_config = ConfigDict(frozen=True)

    scope: Literal["session", "today", "all_time"]


class UsageRecord(BaseModel):
    """백엔드 요청/응답 모델에서 함께 이동해야 하는 상태를 묶는다."""

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
    """백엔드 요청/응답 모델에서 함께 이동해야 하는 상태를 묶는다."""

    model_config = ConfigDict(frozen=True)

    run_id: UUID
    status: Literal["running", "completed", "failed"]
    selected_sources: list[SourceSelection]
    doc_count: int | None = None
    started_at: datetime
    finished_at: datetime | None = None


class LineageRecord(BaseModel):
    """백엔드 요청/응답 모델에서 함께 이동해야 하는 상태를 묶는다."""

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
    """백엔드 요청/응답 모델에서 함께 이동해야 하는 상태를 묶는다."""

    source_solution: str
    source_index: str
    source_doc_id: str
    body: JsonObject
