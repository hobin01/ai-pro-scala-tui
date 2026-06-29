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
from scala_backend.seed.external import seed_elasticsearch_documents, seed_splunk_events
from scala_backend.server import serve as serve_backend
from scala_backend.store import seed_dev_settings
from scala_backend.vector.ocsf_chroma import ChromaOcsfIndex

app = typer.Typer(no_args_is_help=True)


@app.command()
def serve(
    host: Annotated[str | None, typer.Option(help="TCP listen host.")] = None,
    port: Annotated[int | None, typer.Option(help="TCP listen port.")] = None,
    env_file: Annotated[Path | None, typer.Option(help="Optional env file.")] = None,
) -> None:
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
    config = load_config(env_file)
    if config.database_url == "memory://":
        typer.echo("memory store selected; SQL migration skipped")
        return
    migrate_postgres(config.database_url)
    typer.echo("PostgreSQL migrations applied")


@app.command("seed-dev-settings")
def seed_settings(env_file: Annotated[Path | None, typer.Option()] = None) -> None:
    config = load_config(env_file)
    if config.database_url == "memory://":
        backend = create_app(config)
        seed_dev_settings(backend.store, _settings_overrides(config))
    else:
        seed_postgres(config.database_url, _settings_overrides(config))
    typer.echo("dev settings seeded")


@app.command("ingest-ocsf")
def ingest_ocsf(
    env_file: Annotated[Path | None, typer.Option()] = None,
) -> None:
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
    es_ids = seed_elasticsearch_documents(es, "scala-es-logs", _es_docs(count))
    splunk_ids = seed_splunk_events(splunk, "main", _splunk_docs(count))
    typer.echo(f"seeded elasticsearch={len(es_ids)} splunk={len(splunk_ids)} documents")


async def _serve_async(config: BackendConfig, backend: BackendApp) -> None:
    await serve_backend(config, backend)


def _settings_overrides(config: BackendConfig) -> dict[str, object]:
    return {
        "source.elasticsearch.url": config.elasticsearch_url,
        "source.elasticsearch.indices": ["scala-es-logs"],
        "source.splunk.url": config.splunk_url,
        "source.splunk.indices": ["main"],
        "output.opensearch.url": config.opensearch_url,
        "output.opensearch.index": "scala-normalized",
        "console.kibana.url": "http://127.0.0.1:5601",
        "console.splunk.url": "http://127.0.0.1:8000",
        "console.opensearch.url": "http://127.0.0.1:5602",
    }


def _es_docs(count: int) -> list[dict[str, object]]:
    return [
        {
            "source_doc_id": f"es-seed-{index}",
            "src_ip": f"10.10.0.{index % 250 + 1}",
            "dest_port": "443" if index % 2 == 0 else "8443",
            "action": "allow" if index % 3 else "blocked",
            "empty": "",
            "nullable": None,
            "vendor_custom": f"es-extra-{index}",
        }
        for index in range(1, count + 1)
    ]


def _splunk_docs(count: int) -> list[dict[str, object]]:
    return [
        {
            "source_doc_id": f"splunk-seed-{index}",
            "clientip": f"192.168.1.{index % 250 + 1}",
            "port": "443" if index % 2 else "8443",
            "status": "allow" if index % 3 else "blocked",
            "_time": "2026-06-28T08:00:00Z",
            "nullable": None,
            "splunk_custom": f"sp-extra-{index}",
        }
        for index in range(1, count + 1)
    ]


def main() -> None:
    app()


if __name__ == "__main__":
    main()
