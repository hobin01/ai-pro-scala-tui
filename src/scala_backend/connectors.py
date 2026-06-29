from __future__ import annotations

import importlib
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Protocol
from urllib.parse import urlparse

from scala_backend.config import BackendConfig
from scala_backend.connector_fixtures import (
    FixtureConnector,
)
from scala_backend.connector_fixtures import (
    default_connectors as fixture_default_connectors,
)
from scala_backend.errors import SourceUnavailableError
from scala_backend.models import FieldSample, JsonObject, JsonValue, RawDocument

ELASTICSEARCH_PAGE_SIZE = 1000


class SiemConnector(Protocol):
    def fetch_schema_samples(self, index: str, limit: int = 5) -> list[FieldSample]: ...

    def iter_documents(self, index: str) -> Iterable[RawDocument]: ...

    def fetch_raw_document(self, index: str, doc_id: str) -> RawDocument | None: ...


@dataclass(frozen=True)
class ServiceUrl:
    scheme: str
    host: str
    port: int


def default_connectors() -> dict[str, SiemConnector]:
    return dict[str, SiemConnector](fixture_default_connectors())


class ElasticsearchConnector:
    def __init__(self, url: str, username: str | None, password: str | None) -> None:
        module = importlib.import_module("elasticsearch")
        client_cls = module.Elasticsearch
        self.url = parse_service_url(url, default_port=9200)
        auth = (username, password) if username and password else None
        self._client = client_cls(url, basic_auth=auth)
        self.solution = "elasticsearch"

    def fetch_schema_samples(self, index: str, limit: int = 5) -> list[FieldSample]:
        response = self._client.search(index=index, size=limit)
        docs = [
            RawDocument(
                source_solution="elasticsearch",
                source_index=index,
                source_doc_id=str(hit["_id"]),
                body=hit["_source"],
            )
            for hit in response["hits"]["hits"]
        ]
        return FixtureConnector("elasticsearch", docs).fetch_schema_samples(
            index, limit
        )

    def iter_documents(self, index: str) -> Iterable[RawDocument]:
        helpers = importlib.import_module("elasticsearch.helpers")
        for hit in helpers.scan(
            self._client,
            index=index,
            query={"query": {"match_all": {}}},
            size=ELASTICSEARCH_PAGE_SIZE,
        ):
            yield RawDocument(
                source_solution="elasticsearch",
                source_index=index,
                source_doc_id=str(hit["_id"]),
                body=hit["_source"],
            )

    def fetch_raw_document(self, index: str, doc_id: str) -> RawDocument | None:
        try:
            response = self._client.get(index=index, id=doc_id)
        except (KeyError, ValueError) as exc:
            raise SourceUnavailableError(str(exc)) from exc
        if not response.get("found", True):
            return None
        return RawDocument("elasticsearch", index, doc_id, response["_source"])


class SplunkConnector:
    def __init__(self, url: str, username: str | None, password: str | None) -> None:
        splunk_client = importlib.import_module("splunklib.client")
        parsed = parse_service_url(url, default_port=8089)
        self._service = splunk_client.connect(
            host=parsed.host,
            port=parsed.port,
            scheme=parsed.scheme,
            username=username,
            password=password,
            verify=False,
        )
        self.url = parsed
        self.solution = "splunk"

    def fetch_schema_samples(self, index: str, limit: int = 5) -> list[FieldSample]:
        return FixtureConnector(
            "splunk", list(self.iter_documents(index))
        ).fetch_schema_samples(
            index,
            limit,
        )

    def iter_documents(self, index: str) -> Iterable[RawDocument]:
        results = importlib.import_module("splunklib.results")
        stream = self._service.jobs.export(
            f"search index={index} | spath",
            output_mode="json",
        )
        for row in results.JSONResultsReader(stream):
            if not isinstance(row, dict):
                continue
            body: JsonObject = {
                str(key): _coerce_json(value) for key, value in row.items()
            }
            doc_id = splunk_source_doc_id(body)
            yield RawDocument("splunk", index, doc_id, body)

    def fetch_raw_document(self, index: str, doc_id: str) -> RawDocument | None:
        return next(
            (doc for doc in self.iter_documents(index) if doc.source_doc_id == doc_id),
            None,
        )


def connectors_from_settings(
    settings: dict[str, JsonValue],
    config: BackendConfig,
) -> dict[str, SiemConnector]:
    elasticsearch_url = _setting_url(
        settings,
        "source.elasticsearch.url",
        config.elasticsearch_url,
    )
    splunk_url = _setting_url(settings, "source.splunk.url", config.splunk_url)
    if elasticsearch_url.startswith("memory://") or splunk_url.startswith("memory://"):
        return default_connectors()
    return {
        "elasticsearch": ElasticsearchConnector(
            elasticsearch_url,
            config.elasticsearch_username,
            config.elasticsearch_password,
        ),
        "splunk": SplunkConnector(
            splunk_url,
            config.splunk_username,
            config.splunk_password,
        ),
    }


def parse_service_url(url: str, default_port: int = 443) -> ServiceUrl:
    value = url if "://" in url else f"//{url}"
    parsed = urlparse(value, scheme="https")
    scheme = parsed.scheme if "://" in url else "https"
    host = parsed.hostname or parsed.path
    port = parsed.port or default_port
    return ServiceUrl(scheme=scheme, host=host, port=port)


def _setting_url(
    settings: dict[str, JsonValue],
    key: str,
    fallback: str,
) -> str:
    value = settings.get(key)
    return value if isinstance(value, str) else fallback


def splunk_source_doc_id(body: JsonObject) -> str:
    bucket = str(body.get("_bkt", ""))
    offset = str(body.get("_cd", ""))
    if bucket or offset:
        return f"{bucket}:{offset}"
    if "source_doc_id" in body:
        return str(body["source_doc_id"])
    return str(body.get("_serial", body.get("_raw", body.get("_time", ""))))


def _coerce_json(value: object) -> JsonValue:
    if value is None or isinstance(value, str | int | float | bool):
        return value
    if isinstance(value, list):
        return [_coerce_json(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _coerce_json(item) for key, item in value.items()}
    return str(value)
