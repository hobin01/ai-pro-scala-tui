from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from uuid import UUID, uuid4

import anyio

from scala_backend.agent_graph import run_agent_graph
from scala_backend.cache import MappingCache
from scala_backend.connectors import SiemConnector
from scala_backend.errors import RunInProgressError
from scala_backend.mapping import CacheWrite, MappingDecider, MappingResult
from scala_backend.models import (
    AgentName,
    LineageRecord,
    PipelineRunParams,
    RawDocument,
    RunRecord,
    SourceSelection,
)
from scala_backend.normalization import apply_mapping
from scala_backend.output.opensearch import OpenSearchLoader
from scala_backend.providers import LlmProvider
from scala_backend.runtime import notify, start_soon
from scala_backend.store import BackendStore, make_usage
from scala_backend.vector.ocsf_chroma import ChromaOcsfIndex


class PipelineRunner:
    def __init__(
        self,
        store: BackendStore,
        connectors: dict[str, SiemConnector],
        cache: MappingCache,
        opensearch: OpenSearchLoader | None = None,
        ocsf_index: ChromaOcsfIndex | None = None,
        llm_provider: LlmProvider | None = None,
    ) -> None:
        self._store = store
        self._connectors = connectors
        self._cache = cache
        self._opensearch = opensearch
        self._ocsf_index = ocsf_index
        self._llm_provider = llm_provider
        self._decider = MappingDecider(
            store,
            connectors,
            cache,
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
        loaded = 0
        lineage_refs: list[dict[str, str]] = []
        try:
            await notify(
                peer, "run.status", {"run_id": str(run_id), "status": "running"}
            )
            docs = self._collect_documents(sources)
            mapping_result = await self._decider.decide(run_id, sources, peer)
            decisions = mapping_result.decisions
            cache_hits = mapping_result.cache_hit_count
            cache_misses = mapping_result.cache_miss_count
            run_agent_graph(
                str(run_id),
                cache_hit=cache_hits > 0,
                cache_miss=cache_misses > 0,
                needs_feedback=mapping_result.feedback_requested,
            )
            await notify(
                peer,
                "progress",
                {
                    "run_id": str(run_id),
                    "agent": "schema_profiler",
                    "message": (
                        f"profiled {len(decisions)} fields "
                        f"(cache {cache_hits} hit · {cache_misses} miss)"
                    ),
                },
            )
            settings = self._store.get_settings()
            opensearch_index = _opensearch_index(settings)
            for doc in docs:
                normalized = apply_mapping(doc.body, decisions)
                opensearch_id = _stable_opensearch_id(doc)
                if self._opensearch is not None:
                    opensearch_id = self._opensearch.index_normalized(
                        opensearch_index,
                        opensearch_id,
                        normalized,
                    )
                self._store.add_lineage(
                    LineageRecord(
                        run_id=run_id,
                        source_solution=doc.source_solution,
                        source_index=doc.source_index,
                        source_doc_id=doc.source_doc_id,
                        opensearch_index=opensearch_index,
                        opensearch_id=opensearch_id,
                        raw_document=doc.body,
                        normalized_document=normalized,
                        created_at=datetime.now(UTC),
                    ),
                )
                lineage_refs.append(
                    {
                        "source_solution": doc.source_solution,
                        "source_index": doc.source_index,
                        "source_doc_id": doc.source_doc_id,
                        "opensearch_id": opensearch_id,
                    }
                )
                loaded += 1
            cached = self._write_cache(mapping_result.cache_writes)
            mapped = sum(1 for decision in decisions if decision.action == "map")
            kept_raw = sum(1 for decision in decisions if decision.action == "keep_raw")
            self._record_usage(run_id, loaded, cached, mapping_result)
            self._store.update_run(run_id, "completed", loaded)
            await notify(
                peer,
                "output.chunk",
                {"run_id": str(run_id), "text": f"loaded {loaded} normalized docs"},
            )
            await self._send_completed(
                run_id, mapped, kept_raw, loaded, cached, lineage_refs, peer
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
        self._connectors = connectors
        self._opensearch = opensearch
        self._decider = MappingDecider(
            self._store,
            connectors,
            self._cache,
            self._ocsf_index,
            self._llm_provider,
        )

    def _collect_documents(self, sources: list[SourceSelection]) -> list[RawDocument]:
        docs: list[RawDocument] = []
        for source in sources:
            docs.extend(
                list(self._connectors[source.solution].iter_documents(source.index)),
            )
        return docs

    def _write_cache(self, writes: list[CacheWrite]) -> int:
        for write in writes:
            self._cache.set(write.key, write.decision)
        return len(writes)

    def _record_usage(
        self,
        run_id: UUID,
        loaded: int,
        cached: int,
        mapping_result: MappingResult,
    ) -> None:
        self._store.add_usage(
            make_usage(run_id, AgentName.ORCHESTRATOR, "showed final result"),
        )
        self._store.add_usage(
            make_usage(
                run_id,
                AgentName.SCHEMA_PROFILER,
                (
                    f"profiled {len(mapping_result.decisions)} fields "
                    f"({mapping_result.cache_hit_count} cache hits)"
                ),
            ),
        )
        if not any(
            row.run_id == run_id and row.agent == AgentName.NORMALIZATION
            for row in self._store.list_usage()
        ):
            self._store.add_usage(
                make_usage(run_id, AgentName.NORMALIZATION, "generated mappings"),
            )
        self._store.add_usage(
            make_usage(run_id, AgentName.VALIDATOR, "validated mappings"),
        )
        for agent, activity in (
            (AgentName.LOAD, f"loaded {loaded} docs"),
            (AgentName.CACHING, f"cached {cached} mappings"),
            (AgentName.LINEAGE, f"recorded {loaded} lineage rows"),
        ):
            self._store.add_usage(make_usage(run_id, agent, activity))

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
    value = settings.get("output.opensearch.index")
    return value if isinstance(value, str) else "scala-normalized"


def _opensearch_link(settings: dict[str, object]) -> str:
    url = settings.get("console.opensearch.url")
    base = url if isinstance(url, str) else "http://localhost:5602"
    index = _opensearch_index(settings)
    return f"{base.rstrip('/')}/app/discover#/?_a=(index:'{index}')"


def _stable_opensearch_id(doc: RawDocument) -> str:
    source_key = "\x00".join(
        [doc.source_solution, doc.source_index, doc.source_doc_id],
    )
    digest = hashlib.sha256(source_key.encode("utf-8")).hexdigest()[:24]
    return f"scala-{digest}"
