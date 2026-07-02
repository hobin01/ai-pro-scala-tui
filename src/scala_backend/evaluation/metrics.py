from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from scala_backend.models import JsonObject

from .types import EvaluationReport, LineageTruth, MappingTruth, PerformanceDatasetError


def evaluate_performance_dataset(root: Path) -> EvaluationReport:
    """정답지가 있는 평가 dataset에서 PRD의 세 지표를 계산한다."""
    truth = _load_answer_key(root)
    actual = _load_actual_results(root)
    mapping_truth = _mapping_truth_rows(truth, "answer_key.json")
    mapping_actual = _mapping_truth_rows(actual, "actual_results.json")
    lineage_truth = _lineage_truth_rows(truth, "answer_key.json")
    lineage_actual = _lineage_truth_rows(actual, "actual_results.json")
    precision, recall, true_positive, predicted_count, expected_count = (
        _field_mapping_scores(mapping_truth, mapping_actual)
    )
    traceable = _traceable_lineage_count(lineage_truth, lineage_actual)
    total_lineage = len(lineage_truth)
    report = EvaluationReport(
        field_mapping_precision=precision,
        field_mapping_recall=recall,
        lineage_traceability=_ratio(traceable, total_lineage),
        true_positive_mappings=true_positive,
        predicted_mappings=predicted_count,
        expected_mappings=expected_count,
        traceable_lineage=traceable,
        total_source_documents=total_lineage,
    )
    _write_metrics(root / "metrics.json", report)
    return report


def _load_answer_key(root: Path) -> JsonObject:
    """평가 dataset의 answer_key.json을 JSON 객체로 읽는다."""
    return _load_json_object(root / "answer_key.json", "answer key")


def _load_actual_results(root: Path) -> JsonObject:
    """평가 dataset의 actual_results.json을 JSON 객체로 읽는다."""
    return _load_json_object(root / "actual_results.json", "actual results")


def _load_json_object(path: Path, label: str) -> JsonObject:
    """평가 입력 JSON 파일을 객체 형태로 읽고 검증한다."""
    if not path.exists():
        raise PerformanceDatasetError(f"missing {label}: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise PerformanceDatasetError(f"invalid {label}: {path}")
    return payload


def _mapping_truth_rows(payload: JsonObject, label: str) -> list[MappingTruth]:
    """answer key의 field_mappings 항목을 MappingTruth 목록으로 변환한다."""
    raw_rows = payload.get("field_mappings")
    if not isinstance(raw_rows, list):
        raise PerformanceDatasetError(f"{label} missing field_mappings")
    rows: list[MappingTruth] = []
    for row in raw_rows:
        if not isinstance(row, dict):
            raise PerformanceDatasetError(f"{label} has invalid mapping row")
        rows.append(
            MappingTruth(
                solution=str(row.get("solution", "")),
                index=str(row.get("index", "")),
                source_field=str(row.get("source_field", "")),
                source_type=str(row.get("source_type", "")),
                action=str(row.get("action", "")),
                ocsf_field=_optional_str(row.get("ocsf_field")),
                ocsf_type=_optional_str(row.get("ocsf_type")),
            )
        )
    return rows


def _lineage_truth_rows(payload: JsonObject, label: str) -> list[LineageTruth]:
    """answer key의 lineage 항목을 LineageTruth 목록으로 변환한다."""
    raw_rows = payload.get("lineage")
    if not isinstance(raw_rows, list):
        raise PerformanceDatasetError(f"{label} missing lineage")
    rows: list[LineageTruth] = []
    for row in raw_rows:
        if not isinstance(row, dict):
            raise PerformanceDatasetError(f"{label} has invalid lineage row")
        rows.append(
            LineageTruth(
                source_solution=str(row.get("source_solution", "")),
                source_index=str(row.get("source_index", "")),
                source_doc_id=str(row.get("source_doc_id", "")),
                opensearch_index=str(row.get("opensearch_index", "")),
                opensearch_id=str(row.get("opensearch_id", "")),
            )
        )
    return rows


def _field_mapping_scores(
    truth_rows: list[MappingTruth],
    actual_rows: list[MappingTruth],
) -> tuple[float, float, int, int, int]:
    """정답 mapping과 actual mapping의 precision/recall 계산값을 만든다."""
    expected = {
        _mapping_key(row)
        for row in truth_rows
        if row.action == "map" and row.ocsf_field is not None
    }
    predicted = {
        _mapping_key(row)
        for row in actual_rows
        if row.action == "map" and row.ocsf_field is not None
    }
    true_positive = len(expected & predicted)
    return (
        _ratio(true_positive, len(predicted)),
        _ratio(true_positive, len(expected)),
        true_positive,
        len(predicted),
        len(expected),
    )


def _traceable_lineage_count(
    truth_rows: list[LineageTruth],
    actual_rows: list[LineageTruth],
) -> int:
    """정답 lineage와 actual lineage가 완전히 일치한 row 수를 계산한다."""
    expected = {_lineage_key(row) for row in truth_rows}
    actual = {_lineage_key(row) for row in actual_rows}
    return len(expected & actual)


def _mapping_key(row: MappingTruth) -> tuple[str, str, str, str, str]:
    """mapping 비교에 필요한 source와 canonical field key를 만든다."""
    return (
        row.solution,
        row.index,
        row.source_field,
        row.source_type,
        row.ocsf_field or "",
    )


def _lineage_key(row: LineageTruth) -> tuple[str, str, str, str, str]:
    """lineage 비교에 필요한 source와 OpenSearch id key를 만든다."""
    return (
        row.source_solution,
        row.source_index,
        row.source_doc_id,
        row.opensearch_index,
        row.opensearch_id,
    )


def _optional_str(value: object) -> str | None:
    """JSON null과 문자열 값을 optional string으로 정리한다."""
    return value if isinstance(value, str) else None


def _ratio(numerator: int, denominator: int) -> float:
    """분모가 0인 지표를 1.0으로 처리해 빈 집합 평가를 안정화한다."""
    if denominator == 0:
        return 1.0
    return numerator / denominator


def _write_metrics(path: Path, report: EvaluationReport) -> None:
    """계산한 평가 지표를 metrics.json으로 저장한다."""
    path.write_text(
        json.dumps(asdict(report), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
