from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, cast

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
    ProviderError,
)
from scala_backend.models import (
    JsonObject,
    JsonValue,
    LineageLookupParams,
    MonitoringQueryParams,
    PipelineRunParams,
    SamplesFetchParams,
    SettingsSetParams,
    UsageRecord,
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
    """TUI JSON-RPC 요청을 설정, 샘플, 실행, 조회 핸들러로 라우팅한다."""

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
        """BackendApp이 사용할 설정, 저장소, 캐시, provider를 묶는다."""
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
        """메서드 이름을 검증된 백엔드 핸들러 호출로 분기한다."""
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
        """TUI에 표시할 설정과 OpenAI key 설정 여부를 반환한다."""
        return settings_to_display(
            self.store.get_settings(),
            mask_secret(self.config.openai_api_key),
        )

    def settings_set(self, params: SettingsSetParams) -> JsonObject:
        """Settings 화면에서 저장한 값을 scala_settings 저장소에 반영한다."""
        self.store.set_setting(params.key, params.value)
        return {"key": params.key, "value": params.value, "applied": "hot-reload"}

    async def samples_fetch(
        self, params: SamplesFetchParams, peer: object
    ) -> JsonObject:
        """선택된 source의 필드 샘플을 읽고 progress 알림을 보낸다."""
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
        """저장된 agent usage와 OpenAI 비용 스냅샷을 합산한다."""
        usage = self.store.list_usage()
        if params.scope == "session":
            usage = [row for row in usage if row.created_at >= self.started_at]
        result = aggregate_usage(usage, params.scope)
        cost = self._openai_cost(params, usage)
        total = result.get("total")
        if isinstance(total, dict) and cost is not None:
            total["cost"] = float(cost)
            total["cost_source"] = "openai_costs_api"
        return result

    async def lineage_lookup(
        self, params: LineageLookupParams, peer: object
    ) -> JsonObject:
        """OpenSearch _id로 PG 메타, 원본 raw, 정규화 문서를 묶어 반환한다."""
        await notify(
            peer, "progress", {"stage": "metadata", "status": "fetching", "target": ""}
        )
        record = self.store.get_lineage(params.opensearch_id)
        if record is None:
            return {"found": False}
        self.refresh_connectors()
        self.refresh_opensearch()
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
        """실행 전 설정과 provider를 검증한 뒤 파이프라인을 시작한다."""
        self._validate_pipeline_settings(params)
        self.refresh_connectors()
        self.refresh_opensearch()
        run_id = await self.pipeline.start(
            params,
            peer,
            self.connectors,
            self.opensearch,
        )
        return {"run_id": str(run_id)}

    def _validate_pipeline_settings(self, params: PipelineRunParams) -> None:
        """run 생성 전에 source, output, agent model, OpenAI provider를 확인한다."""
        if len(params.sources) < 2:
            raise ConfigurationError("at least two sources must be selected")
        settings = self.store.get_settings()
        if not isinstance(settings.get("output.opensearch.url"), str):
            raise ConfigurationError("OpenSearch URL is not configured")
        if not isinstance(settings.get("output.opensearch.index"), str):
            raise ConfigurationError("OpenSearch index is not configured")
        for agent in ("orchestrator", "schema_profiler", "normalization", "validator"):
            if not isinstance(settings.get(f"agent.{agent}.model"), str):
                raise ConfigurationError(f"{agent} model is not configured")
        provider = self.llm_provider
        if provider is None:
            raise ProviderError("OpenAI API key is not configured")
        normalization_model = settings.get("agent.normalization.model")
        assert isinstance(normalization_model, str)
        provider.validate(normalization_model)
        for source in params.sources:
            if not isinstance(settings.get(f"source.{source.solution}.url"), str):
                raise ConfigurationError(f"{source.solution} URL is not configured")
            indices = settings.get(f"source.{source.solution}.indices")
            if not isinstance(indices, list) or source.index not in indices:
                raise ConfigurationError(
                    f"{source.solution}.{source.index} is not configured"
                )

    def refresh_connectors(self) -> None:
        """현재 settings와 .env auth로 SIEM connector 구성을 다시 만든다."""
        self.connectors = connectors_from_settings(
            self.store.get_settings(),
            self.config,
        )

    def refresh_opensearch(self) -> None:
        """현재 settings가 가리키는 OpenSearch loader를 다시 연결한다."""
        settings = self.store.get_settings()
        url = settings.get("output.opensearch.url")
        if not isinstance(url, str) or url.startswith("memory://"):
            self.opensearch = None
            return
        self.opensearch = OpenSearchLoader(
            url,
            username=self.config.opensearch_username,
            password=self.config.opensearch_password,
        )

    def set_pipeline(self) -> None:
        """최신 connector/cache/loader/provider로 PipelineRunner를 재조립한다."""
        self.pipeline = PipelineRunner(
            self.store,
            self.connectors,
            self.cache,
            self.opensearch,
            self.ocsf_index,
            self.llm_provider,
        )

    def _openai_cost(
        self,
        params: MonitoringQueryParams,
        usage: list[UsageRecord],
    ) -> Decimal | None:
        """monitoring scope에 맞는 기간으로 OpenAI Costs API 금액을 조회한다."""
        provider = self.llm_provider
        if provider is None or not hasattr(provider, "organization_cost_usd"):
            return None
        cost_method = cast(
            Callable[[datetime, datetime], Decimal],
            cast(Any, provider).organization_cost_usd,
        )
        end_time = datetime.now(UTC)
        if params.scope == "session":
            start_time = self.started_at
        elif params.scope == "today":
            start_time = end_time.replace(hour=0, minute=0, second=0, microsecond=0)
        else:
            created_at = [row.created_at for row in usage]
            start_time = min(created_at, default=self.started_at)
        try:
            return cost_method(start_time, end_time)
        except ProviderError:
            return None
