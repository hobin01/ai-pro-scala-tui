#!/usr/bin/env python3
# /// script
# requires-python = ">=3.13"
# ///

from __future__ import annotations

import argparse
import json
import socket
from pathlib import Path
from typing import Any


def main() -> None:
    """환경변수를 읽어 BackendApp JSON-RPC 서버를 실행한다."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--addr", default="127.0.0.1:8765")
    parser.add_argument("--evidence", required=True)
    parser.add_argument("--timeout", type=float, default=300.0)
    args = parser.parse_args()
    host, port_raw = args.addr.split(":", maxsplit=1)
    evidence = Path(args.evidence)
    evidence.parent.mkdir(parents=True, exist_ok=True)
    transcript: list[dict[str, Any]] = []
    with socket.create_connection((host, int(port_raw)), timeout=10) as sock:
        sock.settimeout(args.timeout)
        file = sock.makefile("rwb")
        _call(file, transcript, 1, "settings.get", {})
        _call(
            file,
            transcript,
            2,
            "samples.fetch",
            {
                "sources": [
                    {"solution": "elasticsearch", "index": "scala-es-logs"},
                    {"solution": "splunk", "index": "main"},
                ]
            },
        )
        _run_pipeline(file, transcript, 3)
        _call(file, transcript, 4, "monitoring.query", {"scope": "session"})
        es_opensearch_id = _completed_opensearch_id(transcript, "elasticsearch")
        splunk_opensearch_id = _completed_opensearch_id(transcript, "splunk")
        _call(
            file,
            transcript,
            5,
            "lineage.lookup",
            {"opensearch_id": es_opensearch_id},
        )
        _call(
            file,
            transcript,
            6,
            "lineage.lookup",
            {"opensearch_id": splunk_opensearch_id},
        )
    evidence.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in transcript)
    )


def _call(
    file: Any,
    transcript: list[dict[str, Any]],
    request_id: int,
    method: str,
    params: dict[str, Any],
) -> dict[str, Any]:
    """백엔드 JSON-RPC QA 시나리오의 call 보조 경로를 분리한다."""
    request = {"jsonrpc": "2.0", "id": request_id, "method": method, "params": params}
    _write(file, transcript, "send", request)
    while True:
        message = _read(file, transcript)
        if message.get("id") == request_id:
            _raise_for_error(message)
            return message


def _run_pipeline(
    file: Any,
    transcript: list[dict[str, Any]],
    request_id: int,
) -> None:
    """백엔드 JSON-RPC QA 시나리오의 run pipeline 보조 경로를 분리한다."""
    _write(
        file,
        transcript,
        "send",
        {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": "pipeline.run",
            "params": {
                "sources": [
                    {"solution": "elasticsearch", "index": "scala-es-logs"},
                    {"solution": "splunk", "index": "main"},
                ]
            },
        },
    )
    while True:
        message = _read(file, transcript)
        if message.get("method") == "feedback.request":
            _write(
                file,
                transcript,
                "send",
                {
                    "jsonrpc": "2.0",
                    "id": message["id"],
                    "result": {"decision": "approve"},
                },
            )
            continue
        if message.get("id") == request_id:
            _raise_for_error(message)
        if message.get("method") == "run.status":
            params = message.get("params", {})
            if params.get("status") == "failed":
                raise RuntimeError(json.dumps(params, ensure_ascii=False))
            if params.get("status") == "completed":
                return


def _completed_opensearch_id(transcript: list[dict[str, Any]], solution: str) -> str:
    """백엔드 JSON-RPC QA 시나리오의 completed opensearch id 보조 경로를 분리한다."""
    for row in transcript:
        message = row["message"]
        if message.get("method") == "run.status":
            params = message.get("params", {})
            if params.get("status") == "completed":
                for item in params.get("lineage_refs", []):
                    if item.get("source_solution") == solution:
                        return str(item["opensearch_id"])
    raise RuntimeError(f"completed run did not include {solution} lineage ref")


def _raise_for_error(message: dict[str, Any]) -> None:
    """백엔드 JSON-RPC QA 시나리오의 raise for error 보조 경로를 분리한다."""
    if "error" in message:
        raise RuntimeError(json.dumps(message["error"], ensure_ascii=False))


def _write(
    file: Any, transcript: list[dict[str, Any]], direction: str, message: dict[str, Any]
) -> None:
    """백엔드 JSON-RPC QA 시나리오의 write 보조 경로를 분리한다."""
    transcript.append({"direction": direction, "message": message})
    file.write((json.dumps(message, separators=(",", ":")) + "\n").encode("utf-8"))
    file.flush()


def _read(file: Any, transcript: list[dict[str, Any]]) -> dict[str, Any]:
    """백엔드 JSON-RPC QA 시나리오의 read 보조 경로를 분리한다."""
    line = file.readline()
    if not line:
        raise RuntimeError("backend closed the connection")
    decoded = json.loads(line.decode("utf-8"))
    if not isinstance(decoded, dict):
        raise RuntimeError("backend returned a non-object JSON-RPC message")
    message: dict[str, Any] = decoded
    transcript.append({"direction": "recv", "message": message})
    return message


if __name__ == "__main__":
    main()
