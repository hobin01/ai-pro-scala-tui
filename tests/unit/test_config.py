from pathlib import Path

from scala_backend.config import load_config, mask_secret


def test_config_loads_from_temp_env_file(tmp_path: Path) -> None:
    """테스트 목적: .env와 secret file 설정 로딩."""
    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(
            [
                "SCALA_BACKEND_HOST=127.0.0.1",
                "SCALA_BACKEND_PORT=9900",
                "SCALA_DATABASE_URL=postgresql://scala:scala@localhost:5432/scala",
                "OPENAI_API_KEY=sk-test-12345678",
            ],
        ),
    )

    config = load_config(env_file)

    assert config.backend_host == "127.0.0.1"
    assert config.backend_port == 9900
    assert config.database_url.startswith("postgresql://")
    assert config.openai_api_key == "sk-test-12345678"


def test_config_loads_openai_key_from_secret_file(tmp_path: Path) -> None:
    """테스트 목적: .env와 secret file 설정 로딩."""
    secret = tmp_path / "openai_api_key"
    secret.write_text("sk-secret-file-1234\n", encoding="utf-8")
    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(
            [
                "OPENAI_API_KEY=YOUR_OPENAI_API_KEY",
                f"SCALA_OPENAI_API_KEY_FILE={secret}",
            ],
        ),
    )

    config = load_config(env_file)

    assert config.openai_api_key == "sk-secret-file-1234"


def test_mask_secret_never_returns_original_value() -> None:
    """테스트 목적: .env와 secret file 설정 로딩."""
    assert mask_secret("sk-test-12345678") == "set"
    assert mask_secret("YOUR_OPENAI_API_KEY") == "(not set)"
    assert "12345678" not in mask_secret("sk-test-12345678")
