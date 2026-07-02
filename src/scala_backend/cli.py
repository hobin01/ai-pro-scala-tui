from __future__ import annotations

import importlib
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
from scala_backend.seed.dev_data import es_seed_batches, splunk_seed_batches
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


def main() -> None:
    """환경변수를 읽어 BackendApp JSON-RPC 서버를 실행한다."""
    app()


if __name__ == "__main__":
    main()
