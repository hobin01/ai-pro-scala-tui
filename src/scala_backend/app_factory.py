from __future__ import annotations

from scala_backend.app import BackendApp
from scala_backend.cache import InMemoryMappingCache, MappingCache, RedisMappingCache
from scala_backend.config import BackendConfig
from scala_backend.output.opensearch import OpenSearchLoader
from scala_backend.providers import EmbeddingProvider, OpenAiProvider
from scala_backend.store import (
    BackendStore,
    InMemoryStore,
    PostgresStore,
    seed_dev_settings,
)
from scala_backend.vector.ocsf_chroma import ChromaOcsfIndex


def create_app(config: BackendConfig) -> BackendApp:
    store = _store(config)
    if config.database_url == "memory://":
        seed_dev_settings(store)
    provider = None if config.database_url == "memory://" else _provider(config)
    app = BackendApp(
        config,
        store=store,
        cache=_cache(config),
        opensearch=_opensearch(config),
        ocsf_index=_ocsf_index(config, provider),
        llm_provider=provider,
    )
    app.refresh_connectors()
    app.set_pipeline()
    return app


def _store(config: BackendConfig) -> BackendStore:
    if config.database_url == "memory://":
        return InMemoryStore()
    return PostgresStore(config.database_url)


def _cache(config: BackendConfig) -> MappingCache:
    if config.redis_url == "memory://":
        return InMemoryMappingCache()
    return RedisMappingCache(redis_url=config.redis_url)


def _opensearch(config: BackendConfig) -> OpenSearchLoader | None:
    if config.opensearch_url.startswith("memory://"):
        return None
    return OpenSearchLoader(
        config.opensearch_url,
        username=config.opensearch_username,
        password=config.opensearch_password,
    )


def _provider(config: BackendConfig) -> OpenAiProvider | None:
    if not config.openai_api_key or config.openai_api_key == "YOUR_OPENAI_API_KEY":
        return None
    return OpenAiProvider(config.openai_api_key)


def _ocsf_index(
    config: BackendConfig,
    provider: EmbeddingProvider | None,
) -> ChromaOcsfIndex | None:
    if provider is None:
        return None
    return ChromaOcsfIndex(
        embedding_provider=provider,
        model=config.openai_embedding_model,
        collection_name=config.ocsf_collection,
        host=config.chroma_host,
        port=config.chroma_port,
    )
