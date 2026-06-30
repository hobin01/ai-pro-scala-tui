from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

import anyio

from scala_backend.agent_workflow import AgentWorkflowRunner
from scala_backend.cache import MappingCache
from scala_backend.connectors import SiemConnector
from scala_backend.errors import RunInProgressError
from scala_backend.ids import stable_opensearch_id as _stable_opensearch_id
from scala_backend.models import (
    PipelineRunParams,
    RawDocument,
    RunRecord,
    SourceSelection,
)
from scala_backend.output.opensearch import OpenSearchLoader
from scala_backend.providers import LlmProvider
from scala_backend.runtime import notify, start_soon
from scala_backend.store import BackendStore
from scala_backend.vector.ocsf_chroma import ChromaOcsfIndex


class PipelineRunner:
    """선택 source의 원본 문서를 정규화해 OpenSearch와 lineage store에 적재한다."""

    def __init__(
        self,
        store: BackendStore,
        connectors: dict[str, SiemConnector],
        cache: MappingCache,
        opensearch: OpenSearchLoader | None = None,
        ocsf_index: ChromaOcsfIndex | None = None,
        llm_provider: LlmProvider | None = None,
    ) -> None:
        """정규화 실행에 필요한 connector, mapping, loader, store를 연결한다."""
        self._store = store
        self._connectors = connectors
        self._cache = cache
        self._opensearch = opensearch
        self._ocsf_index = ocsf_index
        self._llm_provider = llm_provider
        self._workflow = AgentWorkflowRunner(
            store,
            connectors,
            cache,
            opensearch,
            ocsf_index,
            llm_provider,
        )
        self._lock = anyio.Lock()
        self._active_run: UUID | None = None

    async def start(
        self,
        params: PipelineRunParams,
        peer: object,
        connectors: dict[str, SiemConnector] | None = None,
        opensearch: OpenSearchLoader | None = None,
    ) -> str:
        """단일 실행 lock을 잡고 run record 생성 후 execute를 background로 넘긴다."""
        async with self._lock:
            if self._active_run is not None:
                raise RunInProgressError(str(self._active_run))
            if connectors is not None:
                self._replace_runtime(connectors, opensearch)
            run_id = uuid4()
            self._active_run = run_id
        self._store.create_run(
            RunRecord(
                run_id=run_id,
                status="running",
                selected_sources=params.sources,
                started_at=datetime.now(UTC),
            ),
        )
        start_soon(peer, self.execute, run_id, params.sources, peer)
        return str(run_id)

    async def execute(
        self,
        run_id: UUID,
        sources: list[SourceSelection],
        peer: object,
    ) -> None:
        """정규화 파이프라인의 execute 변경을 저장 계층에 반영한다."""
        loaded = 0
        try:
            await notify(
                peer, "run.status", {"run_id": str(run_id), "status": "running"}
            )
            result = await self._workflow.run(run_id, sources, peer)
            loaded = result.loaded
            await notify(
                peer,
                "progress",
                {
                    "run_id": str(run_id),
                    "agent": "schema_profiler",
                    "message": (
                        f"profiled {len(result.decisions)} fields "
                        f"(cache {result.cache_hit_count} hit · "
                        f"{result.cache_miss_count} miss)"
                    ),
                },
            )
            self._store.update_run(run_id, "completed", loaded)
            await notify(
                peer,
                "output.chunk",
                {"run_id": str(run_id), "text": f"loaded {loaded} normalized docs"},
            )
            await self._send_completed(
                run_id,
                result.mapped,
                result.kept_raw,
                loaded,
                result.cached,
                result.lineage_refs,
                peer,
            )
        except Exception as exc:
            self._store.update_run(run_id, "failed", loaded)
            await notify(
                peer,
                "run.status",
                {"run_id": str(run_id), "status": "failed", "error": str(exc)},
            )
            raise
        finally:
            async with self._lock:
                self._active_run = None

    def _replace_runtime(
        self,
        connectors: dict[str, SiemConnector],
        opensearch: OpenSearchLoader | None,
    ) -> None:
        """정규화 파이프라인의 replace runtime 보조 경로를 분리한다."""
        self._connectors = connectors
        self._opensearch = opensearch
        self._workflow = AgentWorkflowRunner(
            self._store,
            connectors,
            self._cache,
            opensearch,
            self._ocsf_index,
            self._llm_provider,
        )

    def _collect_documents(self, sources: list[SourceSelection]) -> list[RawDocument]:
        """정규화 파이프라인의 collect documents 보조 경로를 분리한다."""
        docs: list[RawDocument] = []
        for source in sources:
            docs.extend(
                list(self._connectors[source.solution].iter_documents(source.index)),
            )
        return docs

    async def _send_completed(
        self,
        run_id: UUID,
        mapped: int,
        kept_raw: int,
        loaded: int,
        cached: int,
        lineage_refs: list[dict[str, str]],
        peer: object,
    ) -> None:
        """정규화 파이프라인의 send completed 보조 경로를 분리한다."""
        await notify(
            peer,
            "run.status",
            {
                "run_id": str(run_id),
                "status": "completed",
                "summary": {
                    "mapped": mapped,
                    "kept_raw": kept_raw,
                    "loaded": loaded,
                    "lineage": loaded,
                    "cached": cached,
                },
                "lineage_refs": lineage_refs,
                "opensearch_link": _opensearch_link(self._store.get_settings()),
            },
        )


def _opensearch_index(settings: dict[str, object]) -> str:
    """정규화 파이프라인의 opensearch index 보조 경로를 분리한다."""
    value = settings.get("output.opensearch.index")
    return value if isinstance(value, str) else "scala-normalized"


def _opensearch_link(settings: dict[str, object]) -> str:
    """정규화 파이프라인의 opensearch link 보조 경로를 분리한다."""
    url = settings.get("console.opensearch.url")
    base = url if isinstance(url, str) else "http://localhost:5602"
    index = _opensearch_index(settings)
    return f"{base.rstrip('/')}/app/discover#/?_a=(index:'{index}')"


def stable_opensearch_id(doc: RawDocument) -> str:
    """원본 문서 식별자로 재실행 가능한 OpenSearch id를 만든다."""
    return _stable_opensearch_id(doc)
