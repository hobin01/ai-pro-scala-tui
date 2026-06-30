from __future__ import annotations

import importlib
import json
from pathlib import Path
from typing import Annotated

import anyio
import typer

from scala_backend.app import BackendApp
from scala_backend.app_factory import create_app
from scala_backend.config import BackendConfig, load_config
from scala_backend.connectors import parse_service_url
from scala_backend.ocsf import ingest_official_ocsf, load_official_ocsf_fields
from scala_backend.postgres import migrate_postgres, seed_postgres
from scala_backend.providers import OpenAiProvider
from scala_backend.seed.external import seed_elasticsearch_documents, seed_splunk_events
from scala_backend.server import serve as serve_backend
from scala_backend.store import agent_model_settings, seed_dev_settings
from scala_backend.vector.ocsf_chroma import ChromaOcsfIndex

app = typer.Typer(no_args_is_help=True)
ES_SEED_INDICES = ("scala-es-network", "scala-es-endpoint")
SPLUNK_SEED_INDICES = ("main", "security")


@app.command()
def serve(
    host: Annotated[str | None, typer.Option(help="TCP listen host.")] = None,
    port: Annotated[int | None, typer.Option(help="TCP listen port.")] = None,
    env_file: Annotated[Path | None, typer.Option(help="Optional env file.")] = None,
) -> None:
    """설정 파일을 읽고 TCP JSON-RPC backend server를 실행한다."""
    config = load_config(env_file)
    if host is not None:
        config = config.model_copy(update={"backend_host": host})
    if port is not None:
        config = config.model_copy(update={"backend_port": port})
    backend = create_app(config)
    typer.echo(
        f"scala-backend listening on {config.backend_host}:{config.backend_port}"
    )
    anyio.run(_serve_async, config, backend)


@app.command()
def migrate(env_file: Annotated[Path | None, typer.Option()] = None) -> None:
    """DATABASE_URL이 가리키는 PostgreSQL schema migration을 실행한다."""
    config = load_config(env_file)
    if config.database_url == "memory://":
        typer.echo("memory store selected; SQL migration skipped")
        return
    migrate_postgres(config.database_url)
    typer.echo("PostgreSQL migrations applied")


@app.command("seed-dev-settings")
def seed_settings(env_file: Annotated[Path | None, typer.Option()] = None) -> None:
    """scala-backend CLI의 seed settings 변경을 저장 계층에 반영한다."""
    config = load_config(env_file)
    if config.database_url == "memory://":
        backend = create_app(config)
        seed_dev_settings(backend.store, settings_overrides(config))
    else:
        seed_postgres(config.database_url, settings_overrides(config))
    typer.echo("dev settings seeded")


@app.command("ingest-ocsf")
def ingest_ocsf(
    env_file: Annotated[Path | None, typer.Option()] = None,
) -> None:
    """공식 OCSF 필드를 Chroma collection에 적재한다."""
    config = load_config(env_file)
    target = config.chroma_path / f"{config.ocsf_collection}-{config.ocsf_version}.json"
    count = ingest_official_ocsf(config.ocsf_version, target)
    if config.openai_api_key and config.openai_api_key != "YOUR_OPENAI_API_KEY":
        provider = OpenAiProvider(config.openai_api_key)
        index = ChromaOcsfIndex(
            embedding_provider=provider,
            model=config.openai_embedding_model,
            collection_name=config.ocsf_collection,
            host=config.chroma_host,
            port=config.chroma_port,
        )
        count = index.upsert(load_official_ocsf_fields(config.ocsf_version))
    typer.echo(f"ingested OCSF {config.ocsf_version}: {count} fields")


@app.command("seed-dev-data")
def seed_data(
    env_file: Annotated[Path | None, typer.Option()] = None,
    count: Annotated[int, typer.Option(min=1, max=5000)] = 20,
) -> None:
    """scala-backend CLI의 seed data 변경을 저장 계층에 반영한다."""
    config = load_config(env_file)
    elasticsearch = importlib.import_module("elasticsearch")
    splunk_client = importlib.import_module("splunklib.client")
    es = elasticsearch.Elasticsearch(config.elasticsearch_url)
    splunk_url = parse_service_url(config.splunk_url, default_port=8089)
    splunk = splunk_client.connect(
        host=splunk_url.host,
        port=splunk_url.port,
        scheme=splunk_url.scheme,
        username=config.splunk_username,
        password=config.splunk_password,
        verify=False,
    )
    es_ids: list[str] = []
    for index, docs in es_seed_batches(count).items():
        es_ids.extend(seed_elasticsearch_documents(es, index, docs))
    splunk_ids: list[str] = []
    for index, docs in splunk_seed_batches(count).items():
        splunk_ids.extend(seed_splunk_events(splunk, index, docs))
    typer.echo(f"seeded elasticsearch={len(es_ids)} splunk={len(splunk_ids)} documents")


async def _serve_async(config: BackendConfig, backend: BackendApp) -> None:
    """scala-backend CLI의 serve async 보조 경로를 분리한다."""
    await serve_backend(config, backend)


def settings_overrides(config: BackendConfig) -> dict[str, object]:
    """scala-backend CLI의 settings overrides 보조 경로를 분리한다."""
    return {
        **agent_model_settings(config.openai_model),
        "source.elasticsearch.url": config.elasticsearch_url,
        "source.elasticsearch.indices": list(ES_SEED_INDICES),
        "source.splunk.url": config.splunk_url,
        "source.splunk.indices": list(SPLUNK_SEED_INDICES),
        "output.opensearch.url": config.opensearch_url,
        "output.opensearch.index": "scala-normalized",
        "console.kibana.url": "http://127.0.0.1:5601",
        "console.splunk.url": "http://127.0.0.1:8000",
        "console.opensearch.url": "http://127.0.0.1:5602",
        f"model.{config.openai_model}.input_cost_per_1m": (
            config.openai_input_cost_per_1m
        ),
        f"model.{config.openai_model}.output_cost_per_1m": (
            config.openai_output_cost_per_1m
        ),
    }


def es_seed_batches(count: int) -> dict[str, list[dict[str, object]]]:
    first, second = _split_count(count)
    return {
        "scala-es-network": _es_network_docs(first),
        "scala-es-endpoint": _es_endpoint_docs(second),
    }


def splunk_seed_batches(count: int) -> dict[str, list[dict[str, object]]]:
    first, second = _split_count(count)
    return {
        "main": _splunk_main_docs(first),
        "security": _splunk_security_docs(second),
    }


def _split_count(count: int) -> tuple[int, int]:
    first = count // 2
    return first, count - first


def _es_network_docs(count: int) -> list[dict[str, object]]:
    return [_es_network_doc(index) for index in range(1, count + 1)]


def _es_endpoint_docs(count: int) -> list[dict[str, object]]:
    return [_es_endpoint_doc(index) for index in range(1, count + 1)]


def _splunk_main_docs(count: int) -> list[dict[str, object]]:
    return [_splunk_main_doc(index) for index in range(1, count + 1)]


def _splunk_security_docs(count: int) -> list[dict[str, object]]:
    return [_splunk_security_doc(index) for index in range(1, count + 1)]


def _es_network_doc(index: int) -> dict[str, object]:
    return {
        "source_doc_id": f"es-network-seed-{index}",
        "@timestamp": f"2026-06-28T08:{index % 60:02d}:00Z",
        "src_ip": f"10.10.{index % 20}.{index % 250 + 1}",
        "source_ip": f"10.20.{index % 15}.{index % 250 + 1}",
        "dst_ip": f"172.16.{index % 30}.{index % 250 + 1}",
        "dest_port": "443" if index % 2 == 0 else "8443",
        "dst_port": 53 if index % 7 == 0 else 80,
        "action": "allow" if index % 3 else "blocked",
        "event_type": "network_activity",
        "severity": "high" if index % 11 == 0 else "informational",
        "protocol": "tcp" if index % 5 else "udp",
        "bytes_in": index * 17,
        "bytes_out": index * 31,
        "user_name": None if index % 13 == 0 else f"user{index % 9}",
        "host_name": f"es-net-{index % 12}",
        "rule_name": f"egress-policy-{index % 6}",
        "vendor_custom": f"es-network-extra-{index}",
        "empty_note": "" if index % 4 == 0 else "observed",
    }


def _es_endpoint_doc(index: int) -> dict[str, object]:
    return {
        "source_doc_id": f"es-endpoint-seed-{index}",
        "time": f"2026-06-28T09:{index % 60:02d}:30Z",
        "client_ip": f"192.168.{index % 40}.{index % 250 + 1}",
        "remote_addr": f"203.0.113.{index % 250 + 1}",
        "destination_port": "22" if index % 5 == 0 else "3389",
        "status": "success" if index % 4 else "failed",
        "process_name": "powershell.exe" if index % 6 == 0 else "ssh",
        "process_pid": 2000 + index,
        "parent_process": "cmd.exe" if index % 6 == 0 else None,
        "file_hash_sha256": f"{index:064x}"[-64:],
        "file_path": f"/opt/scala/events/scala-{index}.bin",
        "endpoint_hostname": f"endpoint-{index % 18}",
        "os_type": "windows" if index % 3 == 0 else "linux",
        "es_only_endpoint_flag": index % 2 == 0,
        "nullable": None,
    }


def _splunk_main_doc(index: int) -> dict[str, object]:
    return {
        "source_doc_id": f"splunk-main-seed-{index}",
        "_time": f"2026-06-28T10:{index % 60:02d}:00Z",
        "clientip": f"198.51.100.{index % 250 + 1}",
        "src_ip": f"10.30.{index % 20}.{index % 250 + 1}",
        "dest": f"app-{index % 10}.internal",
        "port": "443" if index % 2 else "8080",
        "status": "allowed" if index % 3 else "blocked",
        "http_method": "GET" if index % 2 else "POST",
        "url": f"https://service.example/login/{index % 7}",
        "user_agent": "curl/8.5" if index % 9 == 0 else "Mozilla/5.0",
        "bytes": index * 41,
        "session_id": f"splunk-session-{index % 50}",
        "splunk_custom": f"sp-main-extra-{index}",
        "maybe_missing": None if index % 10 == 0 else "present",
    }


def _splunk_security_doc(index: int) -> dict[str, object]:
    raw_payload = {
        "source_ip": f"10.40.{index % 25}.{index % 250 + 1}",
        "dest_port": "445" if index % 4 == 0 else "389",
        "action": "allow" if index % 5 else "deny",
        "user": None if index % 12 == 0 else f"svc_{index % 8}",
    }
    return {
        "source_doc_id": f"splunk-security-seed-{index}",
        "_time": f"2026-06-28T11:{index % 60:02d}:15Z",
        "_raw": json.dumps(raw_payload, sort_keys=True),
        "EventCode": 4624 if index % 3 else 4625,
        "src": f"security-host-{index % 16}",
        "source_ip": raw_payload["source_ip"],
        "sourceAddress": f"10.41.{index % 25}.{index % 250 + 1}",
        "DestinationPort": str(1024 + index % 200),
        "signature": "Successful Logon" if index % 3 else "Failed Logon",
        "severity": "medium" if index % 3 else "high",
        "splunk_only_security_flag": True,
    }


def main() -> None:
    """환경변수를 읽어 BackendApp JSON-RPC 서버를 실행한다."""
    app()


if __name__ == "__main__":
    main()
