from __future__ import annotations

from scala_backend.app import BackendApp
from scala_backend.cache import InMemoryMappingCache, MappingCache, RedisMappingCache
from scala_backend.config import BackendConfig
from scala_backend.ocsf import load_official_ocsf_fields
from scala_backend.providers import EmbeddingProvider, OpenAiProvider
from scala_backend.store import (
    BackendStore,
    InMemoryStore,
    PostgresStore,
    agent_model_settings,
    seed_dev_settings,
)
from scala_backend.vector.ocsf_chroma import ChromaOcsfIndex


def create_app(config: BackendConfig) -> BackendApp:
    """create app 동작을 처리한다."""
    store = _store(config)
    if config.database_url == "memory://":
        seed_dev_settings(store, agent_model_settings(config.openai_model))
    provider = None if config.database_url == "memory://" else _provider(config)
    app = BackendApp(
        config,
        store=store,
        cache=_cache(config),
        ocsf_index=create_ocsf_index(config, provider),
        llm_provider=provider,
    )
    app.refresh_connectors()
    app.refresh_opensearch()
    app.set_pipeline()
    return app


def _store(config: BackendConfig) -> BackendStore:
    """store 내부 처리를 수행한다."""
    if config.database_url == "memory://":
        return InMemoryStore()
    return PostgresStore(config.database_url)


def _cache(config: BackendConfig) -> MappingCache:
    """cache 내부 처리를 수행한다."""
    if config.redis_url == "memory://":
        return InMemoryMappingCache()
    return RedisMappingCache(redis_url=config.redis_url)


def _provider(config: BackendConfig) -> OpenAiProvider | None:
    """provider 내부 처리를 수행한다."""
    if not config.openai_api_key or config.openai_api_key == "YOUR_OPENAI_API_KEY":
        return None
    return OpenAiProvider(
        config.openai_api_key,
        admin_api_key=config.openai_admin_api_key,
        cost_api_key_id=config.openai_cost_api_key_id,
        cost_project_id=config.openai_cost_project_id,
    )


def create_ocsf_index(
    config: BackendConfig,
    provider: EmbeddingProvider | None,
) -> ChromaOcsfIndex | None:
    """create ocsf index 동작을 처리한다."""
    if provider is None:
        return None
    index = ChromaOcsfIndex(
        embedding_provider=provider,
        model=config.openai_embedding_model,
        collection_name=config.ocsf_collection,
        host=config.chroma_host,
        port=config.chroma_port,
    )
    if index.count() == 0:
        index.upsert(load_official_ocsf_fields(config.ocsf_version))
    return index
