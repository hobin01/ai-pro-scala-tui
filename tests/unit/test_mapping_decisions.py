from __future__ import annotations

from scala_backend.mapping_decisions import deterministic_mapping_decision
from scala_backend.models import FieldSample, SourceSelection


def test_deterministic_mapping_decision_maps_known_security_field() -> None:
    """일반 보안 field는 LLM 전에 canonical mapping으로 확정한다."""
    decision = deterministic_mapping_decision(
        SourceSelection(solution="elasticsearch", index="network"),
        FieldSample(name="src_ip", type="string", samples=["10.0.0.1"]),
    )

    assert decision is not None
    assert decision.action == "map"
    assert decision.ocsf_field == "src_endpoint.ip"


def test_deterministic_mapping_decision_keeps_splunk_metadata_raw() -> None:
    """Splunk runtime metadata는 source 추적용 raw field로 보존한다."""
    decision = deterministic_mapping_decision(
        SourceSelection(solution="splunk", index="web"),
        FieldSample(name="_bkt", type="string", samples=["bucket"]),
    )

    assert decision is not None
    assert decision.action == "keep_raw"
    assert decision.ocsf_field is None


def test_deterministic_mapping_decision_sends_custom_field_to_llm() -> None:
    """Custom 이름만으로는 keep_raw 결정을 강제하지 않는다."""
    decision = deterministic_mapping_decision(
        SourceSelection(solution="elasticsearch", index="network"),
        FieldSample(name="vendor_custom", type="string", samples=["note"]),
    )

    assert decision is None
