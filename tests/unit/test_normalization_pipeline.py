from scala_backend.cache import InMemoryMappingCache, cache_key
from scala_backend.models import FieldSample
from scala_backend.normalization import apply_mapping, recommend_mapping


def test_mapping_casts_string_port_and_preserves_custom_fields() -> None:
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
    assert normalized["custom_attr"] == {"_time": "now"}


def test_cache_key_uses_source_url_index_field_and_type() -> None:
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
