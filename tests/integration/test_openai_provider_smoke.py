import os

import pytest
from dotenv import load_dotenv
from openai import OpenAI

from scala_backend.providers import OpenAiProvider


@pytest.mark.skipif(
    os.environ.get("SCALA_OPENAI_SMOKE") != "1",
    reason="set SCALA_OPENAI_SMOKE=1 to run real OpenAI smoke",
)
def test_openai_provider_real_responses_smoke() -> None:
    load_dotenv()
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        pytest.skip("OPENAI_API_KEY is not configured")
    model = _select_model(api_key)
    provider = OpenAiProvider(api_key)

    response = provider.complete("Reply with one word: OK", model, None)

    assert response.text.strip()


def _select_model(api_key: str) -> str:
    configured = os.environ.get("SCALA_OPENAI_MODEL")
    if configured:
        return configured
    client = OpenAI(api_key=api_key)
    available = {model.id for model in client.models.list().data}
    for candidate in ("gpt-5.4-mini", "gpt-4.1-mini", "gpt-4o-mini"):
        if candidate in available:
            return candidate
    pytest.skip("no preferred small OpenAI model is available")
