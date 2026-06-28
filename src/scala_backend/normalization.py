from __future__ import annotations

from scala_backend.cache import MappingDecision
from scala_backend.models import FieldSample, JsonObject, JsonValue


def recommend_mapping(field: FieldSample) -> MappingDecision:
    lowered = field.name.lower()
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
    normalized: JsonObject = {}
    custom_attr: dict[str, JsonValue] = {}
    decision_by_field = {decision.source_field: decision for decision in decisions}
    for field, value in document.items():
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


def _cast_value(value: JsonValue, ocsf_type: str | None) -> JsonValue:
    if ocsf_type == "integer" and isinstance(value, str) and value.isdigit():
        return int(value)
    return value
