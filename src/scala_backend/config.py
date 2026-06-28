from __future__ import annotations

import os
from pathlib import Path

from dotenv import dotenv_values
from pydantic import BaseModel, ConfigDict, Field


class BackendConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    backend_host: str = "127.0.0.1"
    backend_port: int = Field(default=8765, ge=1, le=65535)
    database_url: str = "memory://"
    redis_url: str = "memory://"
    chroma_path: Path = Path(".scala-data/chroma")
    chroma_host: str = "127.0.0.1"
    chroma_port: int = Field(default=8001, ge=1, le=65535)
    chroma_ssl: bool = False
    ocsf_version: str = "1.8.0"
    ocsf_collection: str = "ocsf-schema"
    openai_api_key: str | None = None
    openai_model: str = "gpt-5-mini"
    openai_embedding_model: str = "text-embedding-3-small"
    opensearch_url: str = "memory://opensearch"
    opensearch_username: str | None = None
    opensearch_password: str | None = None
    elasticsearch_url: str = "memory://elasticsearch"
    elasticsearch_username: str | None = None
    elasticsearch_password: str | None = None
    splunk_url: str = "memory://splunk"
    splunk_username: str | None = None
    splunk_password: str | None = None


ENV_KEY_MAP = {
    "SCALA_BACKEND_HOST": "backend_host",
    "SCALA_BACKEND_PORT": "backend_port",
    "SCALA_DATABASE_URL": "database_url",
    "DATABASE_URL": "database_url",
    "SCALA_REDIS_URL": "redis_url",
    "REDIS_URL": "redis_url",
    "SCALA_CHROMA_PATH": "chroma_path",
    "SCALA_CHROMA_HOST": "chroma_host",
    "SCALA_CHROMA_PORT": "chroma_port",
    "SCALA_CHROMA_SSL": "chroma_ssl",
    "SCALA_OCSF_VERSION": "ocsf_version",
    "SCALA_OCSF_COLLECTION": "ocsf_collection",
    "SCALA_OPENAI_API_KEY": "openai_api_key",
    "OPENAI_API_KEY": "openai_api_key",
    "SCALA_OPENAI_MODEL": "openai_model",
    "SCALA_OPENAI_EMBEDDING_MODEL": "openai_embedding_model",
    "SCALA_OPENSEARCH_URL": "opensearch_url",
    "SCALA_OPENSEARCH_USERNAME": "opensearch_username",
    "SCALA_OPENSEARCH_PASSWORD": "opensearch_password",
    "SCALA_ELASTICSEARCH_URL": "elasticsearch_url",
    "SCALA_ELASTICSEARCH_USERNAME": "elasticsearch_username",
    "SCALA_ELASTICSEARCH_PASSWORD": "elasticsearch_password",
    "SCALA_SPLUNK_URL": "splunk_url",
    "SCALA_SPLUNK_USERNAME": "splunk_username",
    "SCALA_SPLUNK_PASSWORD": "splunk_password",
}


def load_config(env_file: Path | None = None) -> BackendConfig:
    values: dict[str, str] = {}
    dotenv_path = env_file if env_file is not None else Path(".env")
    if dotenv_path.exists():
        values.update(
            {
                key: value
                for key, value in dotenv_values(dotenv_path).items()
                if value is not None
            },
        )
    values.update(dict(os.environ.items()))
    settings = {
        field_name: values[env_key]
        for env_key, field_name in ENV_KEY_MAP.items()
        if env_key in values
    }
    return BackendConfig.model_validate(settings)


def mask_secret(secret: str | None) -> str:
    if not secret or secret in {"YOUR_OPENAI_API_KEY", "changeme"}:
        return "(not set)"
    if len(secret) <= 8:
        return "set"
    return f"set...{secret[-4:]}"
