from __future__ import annotations

import os
from pathlib import Path
from typing import Final

from dotenv import dotenv_values
from pydantic import BaseModel, ConfigDict, Field

DEFAULT_OPENAI_MODEL: Final = "gpt-5.4-mini"


class BackendConfig(BaseModel):
    """SCALA backend가 환경변수와 .env에서 읽는 실행 설정이다."""

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
    openai_admin_api_key: str | None = None
    openai_cost_api_key_id: str | None = None
    openai_cost_project_id: str | None = None
    openai_model: str = DEFAULT_OPENAI_MODEL
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
    "SCALA_OPENAI_ADMIN_API_KEY": "openai_admin_api_key",
    "OPENAI_ADMIN_API_KEY": "openai_admin_api_key",
    "SCALA_OPENAI_COST_API_KEY_ID": "openai_cost_api_key_id",
    "SCALA_OPENAI_COST_PROJECT_ID": "openai_cost_project_id",
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

SECRET_FILE_ENV_KEYS = ("SCALA_OPENAI_API_KEY_FILE", "OPENAI_API_KEY_FILE")


def load_config(env_file: Path | None = None) -> BackendConfig:
    """load config 데이터를 로드한다."""
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
    file_secret = _read_first_secret_file(values)
    if file_secret and not _has_secret(settings.get("openai_api_key")):
        settings["openai_api_key"] = file_secret
    return BackendConfig.model_validate(settings)


def mask_secret(secret: str | None) -> str:
    """환경변수 설정 입력을 mask secret 결과 형태로 변환한다."""
    if not secret or secret in {"YOUR_OPENAI_API_KEY", "changeme"}:
        return "(not set)"
    return "set"


def _read_first_secret_file(values: dict[str, str]) -> str | None:
    """환경변수 설정의 read first secret file 보조 경로를 분리한다."""
    for key in SECRET_FILE_ENV_KEYS:
        path = values.get(key)
        if not path:
            continue
        secret_path = Path(path)
        if not secret_path.exists():
            continue
        secret = secret_path.read_text(encoding="utf-8").strip()
        if _has_secret(secret):
            return secret
    return None


def _has_secret(value: object) -> bool:
    """환경변수 설정의 has secret 보조 경로를 분리한다."""
    return isinstance(value, str) and value not in {
        "",
        "YOUR_OPENAI_API_KEY",
        "changeme",
    }
