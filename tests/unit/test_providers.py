from decimal import Decimal

from scala_backend.providers import FakeProvider, calculate_usage


def test_usage_records_tokens_without_local_cost_estimate() -> None:
    usage = calculate_usage(
        prompt_tokens=1000,
        completion_tokens=500,
        price={"prompt_per_1k": 0.15, "completion_per_1k": 0.60},
    )

    assert usage.total_tokens == 1500
    assert usage.cost_usd == Decimal("0")


def test_fake_provider_is_deterministic() -> None:
    provider = FakeProvider()

    response = provider.complete("map clientip", "gpt-5-mini", None)
    vectors = provider.embed(["clientip"], "text-embedding-3-small")

    assert response.text == "gpt-5-mini: approved"
    assert response.usage.total_tokens > 0
    assert vectors == [[1.0, 2.0, 1.0]]
