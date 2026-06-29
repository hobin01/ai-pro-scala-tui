from __future__ import annotations

import json

from scala_backend.cache import MappingDecision
from scala_backend.models import FieldSample, JsonObject, JsonValue


def recommend_mapping(field: FieldSample) -> MappingDecision:
    """recommend mapping 동작을 처리한다."""
    lowered = field.name.lower()
    if lowered == "_raw":
        return MappingDecision(field.name, field.type, "map", "raw_data", "string")
    if lowered in {"@timestamp", "_time", "time", "timestamp"}:
        return MappingDecision(field.name, field.type, "map", "time", "string")
    if lowered in {"src_ip", "source_ip", "clientip", "client_ip"}:
        return MappingDecision(field.name, field.type, "map", "src_endpoint.ip", "ip")
    if lowered in {"dest_port", "dst_port", "port"}:
        return MappingDecision(
            field.name, field.type, "map", "dst_endpoint.port", "integer"
        )
    if lowered in {"action", "status"}:
        return MappingDecision(field.name, field.type, "map", "activity_name", "string")
    return MappingDecision(field.name, field.type, "keep_raw", None, None)


def apply_mapping(document: JsonObject, decisions: list[MappingDecision]) -> JsonObject:
    """apply mapping 결과를 모델에 반영한다."""
    normalized: JsonObject = {}
    custom_attr: dict[str, JsonValue] = {}
    decision_by_field = {decision.source_field: decision for decision in decisions}
    for field, value in expand_raw_json(document).items():
        decision = decision_by_field.get(field)
        if (
            decision is None
            or decision.action == "keep_raw"
            or decision.ocsf_field is None
        ):
            custom_attr[field] = value
            continue
        normalized[decision.ocsf_field] = _cast_value(value, decision.ocsf_type)
    if custom_attr:
        normalized["custom_attr"] = custom_attr
    return normalized


def expand_raw_json(document: JsonObject) -> JsonObject:
    """expand raw json 동작을 처리한다."""
    expanded = dict(document)
    raw = document.get("_raw")
    if not isinstance(raw, str):
        return expanded
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return expanded
    if not isinstance(parsed, dict):
        return expanded
    for key, value in parsed.items():
        if isinstance(key, str) and key not in expanded:
            expanded[key] = value
    return expanded


def _cast_value(value: JsonValue, ocsf_type: str | None) -> JsonValue:
    """cast value 내부 처리를 수행한다."""
    if ocsf_type == "integer" and isinstance(value, str) and value.isdigit():
        return int(value)
    return value
