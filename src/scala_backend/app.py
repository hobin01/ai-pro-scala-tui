from __future__ import annotations

from datetime import UTC, datetime

from pydantic import ValidationError

from scala_backend.cache import InMemoryMappingCache, MappingCache
from scala_backend.config import BackendConfig, mask_secret
from scala_backend.connectors import (
    SiemConnector,
    connectors_from_settings,
    default_connectors,
)
from scala_backend.errors import (
    ConfigurationError,
    InvalidParamsError,
    MethodNotFoundError,
)
from scala_backend.models import (
    JsonObject,
    JsonValue,
    LineageLookupParams,
    MonitoringQueryParams,
    PipelineRunParams,
    SamplesFetchParams,
    SettingsSetParams,
)
from scala_backend.output.opensearch import OpenSearchLoader
from scala_backend.pipeline import PipelineRunner
from scala_backend.providers import LlmProvider
from scala_backend.runtime import notify
from scala_backend.store import (
    BackendStore,
    InMemoryStore,
    aggregate_usage,
    settings_to_display,
)
from scala_backend.vector.ocsf_chroma import ChromaOcsfIndex


class BackendApp:
    def __init__(
        self,
        config: BackendConfig,
        store: BackendStore | None = None,
        connectors: dict[str, SiemConnector] | None = None,
        cache: MappingCache | None = None,
        opensearch: OpenSearchLoader | None = None,
        ocsf_index: ChromaOcsfIndex | None = None,
        llm_provider: LlmProvider | None = None,
    ) -> None:
        self.config = config
        self.store = store or InMemoryStore()
        self.connectors = connectors or default_connectors()
        self.cache = cache or InMemoryMappingCache()
        self.opensearch = opensearch
        self.ocsf_index = ocsf_index
        self.llm_provider = llm_provider
        self.started_at = datetime.now(UTC)
        self.set_pipeline()

    async def handle(self, method: str, params: JsonObject, peer: object) -> JsonObject:
        try:
            match method:
                case "settings.get":
                    return self.settings_get()
                case "settings.set":
                    return self.settings_set(SettingsSetParams.model_validate(params))
                case "samples.fetch":
                    return await self.samples_fetch(
                        SamplesFetchParams.model_validate(params), peer
                    )
                case "monitoring.query":
                    monitoring_params = MonitoringQueryParams.model_validate(params)
                    return self.monitoring_query(monitoring_params)
                case "lineage.lookup":
                    lineage_params = LineageLookupParams.model_validate(params)
                    return await self.lineage_lookup(lineage_params, peer)
                case "pipeline.run":
                    request = PipelineRunParams.model_validate(params)
                    return await self.pipeline_run(request, peer)
                case _:
                    raise MethodNotFoundError(method)
        except ValidationError as exc:
            raise InvalidParamsError(str(exc)) from exc

    def settings_get(self) -> JsonObject:
        return settings_to_display(
            self.store.get_settings(),
            mask_secret(self.config.openai_api_key),
        )

    def settings_set(self, params: SettingsSetParams) -> JsonObject:
        self.store.set_setting(params.key, params.value)
        return {"key": params.key, "value": params.value, "applied": "hot-reload"}

    async def samples_fetch(
        self, params: SamplesFetchParams, peer: object
    ) -> JsonObject:
        self.refresh_connectors()
        indices: list[JsonValue] = []
        for source in params.sources:
            await notify(
                peer,
                "progress",
                {"target": source.model_dump(), "status": "fetching", "message": ""},
            )
            fields = self.connectors[source.solution].fetch_schema_samples(source.index)
            indices.append(
                {
                    "solution": source.solution,
                    "index": source.index,
                    "fields": [field.model_dump() for field in fields],
                },
            )
            await notify(
                peer,
                "progress",
                {"target": source.model_dump(), "status": "done", "message": ""},
            )
        return {"indices": indices}

    def monitoring_query(self, params: MonitoringQueryParams) -> JsonObject:
        usage = self.store.list_usage()
        if params.scope == "session":
            usage = [row for row in usage if row.created_at >= self.started_at]
        return aggregate_usage(usage, params.scope)

    async def lineage_lookup(
        self, params: LineageLookupParams, peer: object
    ) -> JsonObject:
        await notify(
            peer, "progress", {"stage": "metadata", "status": "fetching", "target": ""}
        )
        record = self.store.get_lineage(params.opensearch_id)
        if record is None:
            return {"found": False}
        self.refresh_connectors()
        raw_document = record.raw_document
        raw = self.connectors[record.source_solution].fetch_raw_document(
            record.source_index,
            record.source_doc_id,
        )
        if raw is not None:
            raw_document = raw.body
        await notify(
            peer,
            "progress",
            {
                "stage": "raw",
                "status": "done",
                "target": f"{record.source_solution}.{record.source_index}",
            },
        )
        normalized_document = record.normalized_document
        if self.opensearch is not None:
            loaded = self.opensearch.fetch_by_id(
                record.opensearch_index,
                record.opensearch_id,
            )
            if loaded is not None:
                normalized_document = loaded
        await notify(
            peer, "progress", {"stage": "normalized", "status": "done", "target": ""}
        )
        return {
            "found": True,
            "metadata": record.model_dump(
                exclude={"raw_document", "normalized_document", "created_at"},
                mode="json",
            ),
            "raw_document": raw_document,
            "normalized_document": normalized_document,
        }

    async def pipeline_run(self, params: PipelineRunParams, peer: object) -> JsonObject:
        self._validate_pipeline_settings(params)
        self.refresh_connectors()
        run_id = await self.pipeline.start(params, peer, self.connectors)
        return {"run_id": str(run_id)}

    def _validate_pipeline_settings(self, params: PipelineRunParams) -> None:
        if not params.sources:
            raise ConfigurationError("at least one source must be selected")
        settings = self.store.get_settings()
        if not isinstance(settings.get("output.opensearch.url"), str):
            raise ConfigurationError("OpenSearch URL is not configured")
        if not isinstance(settings.get("output.opensearch.index"), str):
            raise ConfigurationError("OpenSearch index is not configured")
        for source in params.sources:
            if not isinstance(settings.get(f"source.{source.solution}.url"), str):
                raise ConfigurationError(f"{source.solution} URL is not configured")
            indices = settings.get(f"source.{source.solution}.indices")
            if not isinstance(indices, list) or source.index not in indices:
                raise ConfigurationError(
                    f"{source.solution}.{source.index} is not configured"
                )

    def refresh_connectors(self) -> None:
        self.connectors = connectors_from_settings(
            self.store.get_settings(),
            self.config,
        )

    def set_pipeline(self) -> None:
        self.pipeline = PipelineRunner(
            self.store,
            self.connectors,
            self.cache,
            self.opensearch,
            self.ocsf_index,
            self.llm_provider,
        )
