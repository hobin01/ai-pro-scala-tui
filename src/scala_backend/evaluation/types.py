from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class PerformanceDatasetError(Exception):
    """성능 평가 dataset 입력이 유효하지 않을 때 발생하는 오류다."""

    message: str

    def __str__(self) -> str:
        """CLI와 테스트에서 읽기 쉬운 오류 메시지를 반환한다."""
        return self.message


@dataclass(frozen=True, slots=True)
class DatasetPaths:
    """생성된 성능 평가 dataset의 파일 경로와 문서 수를 보관한다."""

    root: Path
    truth_path: Path
    actual_results_path: Path
    manifest_path: Path
    metrics_path: Path
    elasticsearch_count: int
    splunk_count: int


@dataclass(frozen=True, slots=True)
class MappingTruth:
    """source field 하나의 정답 mapping 결정을 보관한다."""

    solution: str
    index: str
    source_field: str
    source_type: str
    action: str
    ocsf_field: str | None
    ocsf_type: str | None


@dataclass(frozen=True, slots=True)
class LineageTruth:
    """source 문서와 기대 OpenSearch 문서 id의 정답 연결을 보관한다."""

    source_solution: str
    source_index: str
    source_doc_id: str
    opensearch_index: str
    opensearch_id: str


@dataclass(frozen=True, slots=True)
class EvaluationReport:
    """PRD 평가 지표 세 가지와 계산 근거 수량을 보관한다."""

    field_mapping_precision: float
    field_mapping_recall: float
    lineage_traceability: float
    true_positive_mappings: int
    predicted_mappings: int
    expected_mappings: int
    traceable_lineage: int
    total_source_documents: int
