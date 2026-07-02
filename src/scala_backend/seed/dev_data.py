from __future__ import annotations

import json

type SeedDocument = dict[str, object]


def es_seed_batches(count: int) -> dict[str, list[SeedDocument]]:
    """Elasticsearch seed 문서를 network/endpoint 인덱스로 나눈다."""
    first, second = _split_count(count)
    return {
        "scala-es-network": [_es_network_doc(index) for index in range(1, first + 1)],
        "scala-es-endpoint": [
            _es_endpoint_doc(index) for index in range(1, second + 1)
        ],
    }


def splunk_seed_batches(count: int) -> dict[str, list[SeedDocument]]:
    """Splunk seed 이벤트를 웹 접근/인증 인덱스로 나눈다."""
    first, second = _split_count(count)
    return {
        "main": [_splunk_web_doc(index) for index in range(1, first + 1)],
        "security": [_splunk_auth_doc(index) for index in range(1, second + 1)],
    }


def _split_count(count: int) -> tuple[int, int]:
    """전체 seed 개수를 두 인덱스에 최대한 균등하게 나눈다."""
    first = count // 2
    return first, count - first


def _es_network_doc(index: int) -> SeedDocument:
    """방화벽/프록시 네트워크 흐름형 Elasticsearch 문서 한 건을 만든다."""
    blocked = index % 5 == 0
    return {
        "source_doc_id": f"es-network-seed-{index}",
        "@timestamp": f"2026-06-28T08:{index % 60:02d}:00Z",
        "event.action": "blocked" if blocked else "allowed",
        "event.outcome": "failure" if blocked else "success",
        "severity": "high" if blocked else "informational",
        "src_ip": f"10.10.{index % 20}.{index % 250 + 1}",
        "source_ip": f"10.20.{index % 15}.{index % 250 + 1}",
        "source_port": 49152 + index % 12000,
        "dst_ip": f"172.16.{index % 30}.{index % 250 + 1}",
        "dest_ip": f"172.17.{index % 30}.{index % 250 + 1}",
        "dst_port": 443 if index % 2 else 8443,
        "dest_port": str(443 if index % 2 else 8443),
        "protocol": "tcp" if index % 7 else "udp",
        "application": "okta" if index % 3 else "m365",
        "bytes_in": 1200 + index * 17,
        "bytes_out": 3200 + index * 31,
        "username": None if index % 13 == 0 else f"corp.user{index % 9}",
        "device_hostname": f"fw-edge-{index % 6}.corp.local",
        "url": f"https://portal.example.com/sso/{index % 11}",
        "user_agent": "Mozilla/5.0 Chrome/126" if index % 4 else "curl/8.5",
        "tls_version": "TLSv1.3",
        "tls_cipher": "TLS_AES_256_GCM_SHA384",
        "rule_name": f"egress-policy-{index % 6}",
        "vendor_event_id": f"PAN-{index:06d}",
    }


def _es_endpoint_doc(index: int) -> SeedDocument:
    """EDR 프로세스/파일 활동형 Elasticsearch 문서 한 건을 만든다."""
    powershell = index % 4 == 0
    process = "powershell.exe" if powershell else "chrome.exe"
    return {
        "source_doc_id": f"es-endpoint-seed-{index}",
        "time": f"2026-06-28T09:{index % 60:02d}:30Z",
        "action": "process_start" if not powershell else "script_block",
        "status": "success" if index % 6 else "failure",
        "severity": "medium" if powershell else "informational",
        "client_ip": f"192.168.{index % 40}.{index % 250 + 1}",
        "remote_addr": f"203.0.113.{index % 250 + 1}",
        "dst_ip": f"203.0.113.{index % 250 + 1}",
        "dst_port": 443 if not powershell else 5985,
        "protocol": "tcp",
        "process_name": process,
        "process_pid": 2000 + index,
        "process_command_line": (
            "powershell.exe -NoProfile -EncodedCommand SQBFAFgA"
            if powershell
            else "chrome.exe --type=renderer --site-per-process"
        ),
        "parent_process_name": "cmd.exe" if powershell else "explorer.exe",
        "file_name": "invoice.js" if powershell else "chrome.dll",
        "file_path": f"C:/Users/user{index % 9}/Downloads/scala-{index}.bin",
        "file_hash_sha256": f"{index:064x}"[-64:],
        "endpoint_hostname": f"endpoint-{index % 18}.corp.local",
        "user_name": None if index % 10 == 0 else f"corp.user{index % 9}",
        "os_type": "windows" if index % 3 == 0 else "linux",
        "vendor_detection_id": f"EDR-{index:06d}",
    }


def _splunk_web_doc(index: int) -> SeedDocument:
    """Nginx/웹 프록시 접근형 Splunk 이벤트 한 건을 만든다."""
    post = index % 2 == 0
    status = 403 if index % 7 == 0 else 200
    return {
        "source_doc_id": f"splunk-main-seed-{index}",
        "_time": f"2026-06-28T10:{index % 60:02d}:00Z",
        "clientip": f"198.51.100.{index % 250 + 1}",
        "src_ip": f"10.30.{index % 20}.{index % 250 + 1}",
        "dest_ip": f"10.60.{index % 20}.{index % 250 + 1}",
        "dest": f"app-{index % 10}.internal",
        "dest_port": "443" if not post else "8443",
        "port": "443" if not post else "8443",
        "method": "POST" if post else "GET",
        "http_method": "POST" if post else "GET",
        "http_status": status,
        "status": "blocked" if status >= 400 else "allowed",
        "url": f"https://service.example.com/api/v1/session/{index % 17}",
        "uri_path": f"/api/v1/session/{index % 17}",
        "user_agent": "Mozilla/5.0 Chrome/126" if index % 9 else "python-requests/2",
        "referer": "https://service.example.com/login",
        "bytes_in": 300 + index * 11,
        "bytes_out": 1400 + index * 29,
        "user": None if index % 12 == 0 else f"web.user{index % 8}",
        "host": f"web-{index % 6}.prod.internal",
        "request_id": f"req-{index:08d}",
        "session_id": f"splunk-session-{index % 50}",
        "waf_rule_id": f"waf-{index % 5}",
    }


def _splunk_auth_doc(index: int) -> SeedDocument:
    """인증 서버/Windows 보안 로그형 Splunk 이벤트 한 건을 만든다."""
    failed = index % 4 == 0
    raw_payload = {
        "src_ip": f"10.40.{index % 25}.{index % 250 + 1}",
        "source_ip": f"10.41.{index % 25}.{index % 250 + 1}",
        "dest_ip": f"10.70.{index % 25}.{index % 250 + 1}",
        "dest_port": "445" if index % 3 == 0 else "636",
        "user": None if index % 12 == 0 else f"svc_{index % 8}",
        "user_id": f"S-1-5-21-1000-{index}",
        "auth_protocol": "kerberos" if index % 2 else "ldap",
        "auth_method": "password+mfa" if index % 5 else "password",
        "mfa_result": "denied" if failed else "approved",
        "device_hostname": f"dc-{index % 4}.corp.local",
        "process_name": "lsass.exe",
        "process_pid": 700 + index,
        "action": "failed_logon" if failed else "successful_logon",
        "severity": "high" if failed else "medium",
    }
    return {
        "source_doc_id": f"splunk-security-seed-{index}",
        "_time": f"2026-06-28T11:{index % 60:02d}:15Z",
        "_raw": json.dumps(raw_payload, sort_keys=True),
        "EventCode": 4625 if failed else 4624,
        "signature": "Failed Logon" if failed else "Successful Logon",
        "src": f"security-host-{index % 16}",
        "sourceAddress": raw_payload["source_ip"],
        "DestinationPort": str(1024 + index % 200),
        "user": raw_payload["user"],
        "status": "failure" if failed else "success",
        "identity_provider": "active-directory",
        "tenant_id": f"tenant-{index % 3}",
    }
