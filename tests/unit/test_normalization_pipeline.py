from decimal import Decimal
from uuid import uuid4

import pytest

from scala_backend.cache import InMemoryMappingCache, cache_key
from scala_backend.connectors import default_connectors
from scala_backend.errors import ProviderError
from scala_backend.mapping import MappingDecider
from scala_backend.models import FieldSample, JsonObject, SourceSelection
from scala_backend.normalization import apply_mapping, recommend_mapping
from scala_backend.providers import LlmResponse, ProviderUsage
from scala_backend.store import InMemoryStore, seed_dev_settings


class ApprovingPeer:
    """human feedback 요청마다 approve 응답을 돌려주는 peer다."""

    async def request(self, method: str, params: JsonObject) -> JsonObject:
        """feedback.request를 승인 응답으로 처리한다."""
        del method, params
        return {"decision": "approve"}


class CommentThenApprovePeer:
    """첫 feedback에는 comment, 다음 feedback에는 approve를 돌려주는 peer다."""

    def __init__(self) -> None:
        """feedback 요청 기록을 저장할 list를 준비한다."""
        self.requests: list[JsonObject] = []

    async def request(self, method: str, params: JsonObject) -> JsonObject:
        """첫 요청은 comment, 두 번째 요청은 approve로 응답한다."""
        assert method == "feedback.request"
        self.requests.append(params)
        if len(self.requests) == 1:
            return {
                "decision": "comment",
                "comment": "please keep_raw; this is a vendor-specific proxy client IP",
            }
        return {"decision": "approve"}


class InvalidJsonProvider:
    """잘못된 LLM JSON 응답을 만들어 fallback 경로를 고정한다."""

    def validate(self, model: str) -> None:
        """invalid JSON provider에서는 모든 model 검증을 통과시킨다."""
        del model

    def complete(
        self,
        prompt: str,
        model: str,
        price: dict[str, float] | None,
    ) -> LlmResponse:
        """mapping JSON 파싱 실패를 유도하는 응답을 반환한다."""
        del prompt, model, price
        return LlmResponse(
            text="not-json",
            usage=ProviderUsage(1, 1, 2, Decimal("0")),
        )


def test_mapping_casts_string_port_and_preserves_custom_fields() -> None:
    """문자열 port를 int로 변환하고 raw field를 보존하는지 확인한다."""
    fields = [
        FieldSample(name="clientip", type="string", samples=["10.0.0.5"]),
        FieldSample(name="port", type="string", samples=["443"]),
        FieldSample(name="_time", type="string", samples=["now"]),
    ]
    decisions = [recommend_mapping(field) for field in fields]

    normalized = apply_mapping(
        {"clientip": "10.0.0.5", "port": "443", "_time": "now"},
        decisions,
    )

    assert normalized["src_endpoint.ip"] == "10.0.0.5"
    assert normalized["dst_endpoint.port"] == 443
    assert normalized["time"] == "now"


def test_mapping_expands_json_raw_before_applying_decisions() -> None:
    """JSON _raw 내부 field를 펼친 뒤 OCSF mapping을 적용하는지 확인한다."""
    fields = [
        FieldSample(name="_raw", type="string", samples=[]),
        FieldSample(name="clientip", type="string", samples=[]),
        FieldSample(name="port", type="string", samples=[]),
    ]
    decisions = [recommend_mapping(field) for field in fields]

    normalized = apply_mapping(
        {"_raw": '{"clientip": "10.0.0.5", "port": "443"}'},
        decisions,
    )

    assert normalized["raw_data"] == '{"clientip": "10.0.0.5", "port": "443"}'
    assert normalized["src_endpoint.ip"] == "10.0.0.5"
    assert normalized["dst_endpoint.port"] == 443


def test_cache_key_uses_source_url_index_field_and_type() -> None:
    """cache key가 source URL 차이를 구분하는지 확인한다."""
    cache = InMemoryMappingCache()
    decision = recommend_mapping(
        FieldSample(name="clientip", type="string", samples=[])
    )
    key = cache_key("https://splunk-a:8089", "main", "clientip", "string")

    cache.set(key, decision)

    assert cache.get(key) == decision
    assert (
        cache.get(cache_key("https://splunk-b:8089", "main", "clientip", "string"))
        is None
    )


@pytest.mark.anyio
async def test_mapping_decider_defers_cache_writes_to_caching_agent() -> None:
    """MappingDecider가 cache 저장을 Caching agent 단계로 넘기는지 확인한다."""
    store = InMemoryStore()
    seed_dev_settings(store)
    cache = InMemoryMappingCache()
    decider = MappingDecider(store, default_connectors(), cache)
    settings = store.get_settings()
    source_url = settings["source.splunk.url"]
    assert isinstance(source_url, str)

    result = await decider.decide(
        uuid4(),
        [SourceSelection(solution="splunk", index="main")],
        ApprovingPeer(),
    )

    key = cache_key(source_url, "main", "clientip", "string")
    assert cache.get(key) is None
    assert any(write.key == key for write in result.cache_writes)
    assert result.cache_hit_count == 0
    assert result.cache_miss_count == len(result.decisions)


@pytest.mark.anyio
async def test_mapping_decider_rejects_invalid_agent_json_without_fallback() -> None:
    """fallback 없는 invalid LLM JSON을 ProviderError로 거부하는지 확인한다."""
    store = InMemoryStore()
    seed_dev_settings(store)
    decider = MappingDecider(
        store,
        default_connectors(),
        InMemoryMappingCache(),
        llm_provider=InvalidJsonProvider(),
    )

    with pytest.raises(ProviderError, match="invalid mapping JSON"):
        await decider.decide(
            uuid4(),
            [SourceSelection(solution="splunk", index="main")],
            ApprovingPeer(),
        )


@pytest.mark.anyio
async def test_mapping_decider_rerequests_feedback_after_comment() -> None:
    """사용자 comment 후 recommendation을 보정해 feedback을 재요청하는지 확인한다."""
    store = InMemoryStore()
    seed_dev_settings(store)
    cache = InMemoryMappingCache()
    decider = MappingDecider(store, default_connectors(), cache)
    peer = CommentThenApprovePeer()

    result = await decider.decide(
        uuid4(),
        [SourceSelection(solution="splunk", index="main")],
        peer,
    )

    clientip_decision = next(
        decision for decision in result.decisions if decision.source_field == "clientip"
    )
    assert len(peer.requests) == 2
    why = str(peer.requests[1]["recommendation"]["why"])
    assert "(updated)" in why
    assert "keep_raw" in why
    assert "vendor-specific proxy client IP" in why
    assert peer.requests[1]["recommendation"]["action"] == "keep_raw"
    assert peer.requests[1]["recommendation"]["ocsf_field"] is None
    assert clientip_decision.action == "keep_raw"
