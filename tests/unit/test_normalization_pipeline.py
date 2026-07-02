from scala_backend.cache import InMemoryMappingCache, cache_key
from scala_backend.models import FieldSample
from scala_backend.normalization import apply_mapping, recommend_mapping


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


def test_mapping_expands_nested_splunk_raw_field() -> None:
    """Splunk spath가 만든 raw JSON 문자열을 한 번 더 펼치는지 확인한다."""
    fields = [
        FieldSample(name="source_ip", type="string", samples=[]),
        FieldSample(name="auth_method", type="string", samples=[]),
    ]
    decisions = [recommend_mapping(field) for field in fields]

    normalized = apply_mapping(
        {
            "_raw": (
                '{"raw": "{\\"source_ip\\": \\"10.0.0.5\\", '
                '\\"auth_method\\": \\"password\\"}"}'
            )
        },
        decisions,
    )

    assert normalized["src_endpoint.ip"] == "10.0.0.5"
    assert normalized["auth_type"] == "password"


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
