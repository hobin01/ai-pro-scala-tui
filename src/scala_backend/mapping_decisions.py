from __future__ import annotations

from typing import Final

from scala_backend.cache import MappingDecision
from scala_backend.models import FieldSample, SourceSelection
from scala_backend.normalization import recommend_mapping

SPLUNK_RUNTIME_METADATA_FIELDS: Final[frozenset[str]] = frozenset(
    {
        "_bkt",
        "_cd",
        "_indextime",
        "_serial",
        "_si",
        "_sourcetype",
        "host",
        "index",
        "linecount",
        "source",
        "source_doc_id",
        "sourcetype",
        "splunk_server",
    }
)
RAW_LINEAGE_FIELDS: Final[frozenset[str]] = frozenset(
    {
        "identity_provider",
        "raw",
        "source_doc_id",
    }
)


def deterministic_mapping_decision(
    source: SourceSelection,
    field: FieldSample,
) -> MappingDecision | None:
    """LLM 없이 확정 가능한 보존/매핑 결정을 반환한다."""
    if source.solution == "splunk" and field.name in SPLUNK_RUNTIME_METADATA_FIELDS:
        return _keep_raw(field)
    if field.name.lower() in RAW_LINEAGE_FIELDS:
        return _keep_raw(field)
    decision = recommend_mapping(field)
    return decision if decision.action == "map" else None


def _keep_raw(field: FieldSample) -> MappingDecision:
    """정규화 대상이 아닌 원천 field를 원문 보존 결정으로 만든다."""
    return MappingDecision(
        field.name,
        field.type,
        "keep_raw",
        None,
        None,
    )
