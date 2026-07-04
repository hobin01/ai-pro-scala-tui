from __future__ import annotations

import json
from typing import Final

from scala_backend.models import JsonObject

ES_NETWORK_INDEX: Final = "scala-perf-es-network"
ES_ENDPOINT_INDEX: Final = "scala-perf-es-endpoint"
SPLUNK_WEB_INDEX: Final = "scala_perf_web"
SPLUNK_AUTH_INDEX: Final = "scala_perf_auth"


def elasticsearch_performance_batches(count: int) -> dict[str, list[JsonObject]]:
    """Elasticsearch 평가 문서를 network/endpoint index로 나눈다."""
    first, second = _split_count(count)
    return {
        ES_NETWORK_INDEX: [_es_network_doc(index) for index in range(1, first + 1)],
        ES_ENDPOINT_INDEX: [_es_endpoint_doc(index) for index in range(1, second + 1)],
    }


def splunk_performance_batches(count: int) -> dict[str, list[JsonObject]]:
    """Splunk 평가 문서를 web/auth index로 나눈다."""
    first, second = _split_count(count)
    return {
        SPLUNK_WEB_INDEX: [_splunk_web_doc(index) for index in range(1, first + 1)],
        SPLUNK_AUTH_INDEX: [_splunk_auth_doc(index) for index in range(1, second + 1)],
    }


def _es_network_doc(index: int) -> JsonObject:
    """네트워크 장비형 Elasticsearch 평가 문서 한 건을 만든다."""
    return {
        "source_doc_id": f"perf-es-network-{index}",
        "@timestamp": f"2026-07-02T08:{index % 60:02d}:00Z",
        "src_ip": f"10.50.{index % 20}.{index % 250 + 1}",
        "source_port": 40000 + index,
        "dst_ip": f"172.20.{index % 30}.{index % 250 + 1}",
        "dst_port": 443 if index % 2 else 8443,
        "protocol": "tcp" if index % 3 else "udp",
        "bytes_in": 1000 + index * 13,
        "bytes_out": 3000 + index * 29,
        "username": None if index % 7 == 0 else f"net.user{index % 5}",
        "vendor_weird_flag": f"net-extra-{index % 4}",
    }


def _es_endpoint_doc(index: int) -> JsonObject:
    """엔드포인트 보안형 Elasticsearch 평가 문서 한 건을 만든다."""
    return {
        "source_doc_id": f"perf-es-endpoint-{index}",
        "time": f"2026-07-02T09:{index % 60:02d}:30Z",
        "client_ip": f"192.168.{index % 40}.{index % 250 + 1}",
        "remote_addr": f"203.0.113.{index % 250 + 1}",
        "destination_port": "5985" if index % 4 == 0 else "443",
        "process_name": "powershell.exe" if index % 4 == 0 else "chrome.exe",
        "process_pid": 5000 + index,
        "process_command_line": "powershell.exe -NoProfile"
        if index % 4 == 0
        else "chrome.exe --type=renderer",
        "endpoint_hostname": f"perf-endpoint-{index % 8}.corp.local",
        "typooedEDRField": None if index % 5 == 0 else f"edr-note-{index}",
    }


def _splunk_web_doc(index: int) -> JsonObject:
    """웹 접근형 Splunk 평가 이벤트 한 건을 만든다."""
    return {
        "source_doc_id": f"perf-splunk-web-{index}",
        "_time": f"2026-07-02T10:{index % 60:02d}:00Z",
        "clientip": f"198.51.100.{index % 250 + 1}",
        "dest_ip": f"10.80.{index % 20}.{index % 250 + 1}",
        "dest_port": "8443" if index % 2 else "443",
        "method": "POST" if index % 2 else "GET",
        "http_status": 403 if index % 6 == 0 else 200,
        "user_agent": "Mozilla/5.0 Chrome/126" if index % 5 else "curl/8.5",
        "wafMysteryColumn": f"waf-note-{index % 3}",
    }


def _splunk_auth_doc(index: int) -> JsonObject:
    """인증형 Splunk 평가 이벤트 한 건을 만든다."""
    raw_payload = {
        "source_ip": f"10.90.{index % 25}.{index % 250 + 1}",
        "dest_port": "636" if index % 3 else "445",
        "user": None if index % 6 == 0 else f"svc_perf_{index % 7}",
        "user_id": f"S-1-5-21-2000-{index}",
        "auth_protocol": "kerberos" if index % 2 else "ldap",
        "auth_method": "password+mfa" if index % 5 else "password",
    }
    return {
        "source_doc_id": f"perf-splunk-auth-{index}",
        "_time": f"2026-07-02T11:{index % 60:02d}:15Z",
        "_raw": json.dumps(raw_payload, sort_keys=True),
        "DestinationPort": str(1024 + index % 200),
        "identity_provider": "active-directory",
    }


def _split_count(count: int) -> tuple[int, int]:
    """전체 건수를 두 index에 최대한 균등하게 나눈다."""
    first = count // 2
    return first, count - first
