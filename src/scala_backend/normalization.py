from __future__ import annotations

import json
from typing import Final

from scala_backend.cache import MappingDecision
from scala_backend.models import FieldSample, JsonObject, JsonValue

FIELD_MAPPINGS: Final[dict[str, tuple[str, str]]] = {
    "_raw": ("raw_data", "string"),
    "@timestamp": ("time", "string"),
    "_time": ("time", "string"),
    "time": ("time", "string"),
    "timestamp": ("time", "string"),
    "src_ip": ("src_endpoint.ip", "ip"),
    "source_ip": ("src_endpoint.ip", "ip"),
    "clientip": ("src_endpoint.ip", "ip"),
    "client_ip": ("src_endpoint.ip", "ip"),
    "source_port": ("src_endpoint.port", "integer"),
    "dst_ip": ("dst_endpoint.ip", "ip"),
    "dest_ip": ("dst_endpoint.ip", "ip"),
    "remote_addr": ("dst_endpoint.ip", "ip"),
    "dest_port": ("dst_endpoint.port", "integer"),
    "dst_port": ("dst_endpoint.port", "integer"),
    "port": ("dst_endpoint.port", "integer"),
    "destination_port": ("dst_endpoint.port", "integer"),
    "destinationport": ("dst_endpoint.port", "integer"),
    "protocol": ("network.protocol_name", "string"),
    "bytes_in": ("traffic.bytes_in", "integer"),
    "bytes_out": ("traffic.bytes_out", "integer"),
    "method": ("http_request.http_method", "string"),
    "http_method": ("http_request.http_method", "string"),
    "user_agent": ("http_request.user_agent", "string"),
    "http_status": ("http_response.code", "integer"),
    "action": ("activity_name", "string"),
    "status": ("activity_name", "string"),
    "severity": ("severity", "string"),
    "username": ("actor.user.name", "string"),
    "user": ("actor.user.name", "string"),
    "user_name": ("actor.user.name", "string"),
    "user_id": ("actor.user.uid", "string"),
    "device_hostname": ("device.hostname", "string"),
    "endpoint_hostname": ("device.hostname", "string"),
    "host": ("device.hostname", "string"),
    "process_name": ("process.name", "string"),
    "process_pid": ("process.pid", "integer"),
    "process_command_line": ("process.cmd_line", "string"),
    "parent_process_name": ("parent_process.name", "string"),
    "file_name": ("file.name", "string"),
    "file_path": ("file.path", "string"),
    "file_hash_sha256": ("file.hash.sha256", "string"),
    "url": ("url.url", "string"),
    "uri_path": ("url.url", "string"),
    "auth_protocol": ("auth_protocol", "string"),
    "auth_method": ("auth_type", "string"),
}


def recommend_mapping(field: FieldSample) -> MappingDecision:
    """알려진 source field 이름을 기본 OCSF mapping 후보로 분류한다."""
    lowered = field.name.lower()
    mapping = FIELD_MAPPINGS.get(lowered)
    if mapping is not None:
        ocsf_field, ocsf_type = mapping
        return MappingDecision(field.name, field.type, "map", ocsf_field, ocsf_type)
    return MappingDecision(field.name, field.type, "keep_raw", None, None)


def apply_mapping(document: JsonObject, decisions: list[MappingDecision]) -> JsonObject:
    """OCSF 정규화 입력을 apply mapping 결과 형태로 변환한다."""
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
    """Splunk _raw JSON 문자열의 내부 필드를 mapping 입력에 합친다."""
    expanded = dict(document)
    _merge_json_string_field(expanded, "_raw")
    _merge_json_string_field(expanded, "raw")
    return expanded


def _merge_json_string_field(expanded: JsonObject, field: str) -> None:
    """JSON 문자열 field의 내부 key를 아직 없는 mapping 입력으로 합친다."""
    raw = expanded.get(field)
    if not isinstance(raw, str):
        return
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return
    if not isinstance(parsed, dict):
        return
    for key, value in parsed.items():
        if isinstance(key, str) and key not in expanded:
            expanded[key] = value


def _cast_value(value: JsonValue, ocsf_type: str | None) -> JsonValue:
    """OCSF 정규화의 cast value 보조 경로를 분리한다."""
    if ocsf_type == "integer" and isinstance(value, str) and value.isdigit():
        return int(value)
    return value
