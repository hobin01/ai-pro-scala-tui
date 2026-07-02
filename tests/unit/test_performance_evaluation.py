from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from scala_backend.cli import app
from scala_backend.evaluation.performance import (
    elasticsearch_performance_batches,
    evaluate_performance_dataset,
    generate_performance_dataset,
    performance_mapping_truth,
    splunk_performance_batches,
)
from scala_backend.models import FieldSample
from scala_backend.normalization import expand_raw_json, recommend_mapping


def test_performance_dataset_scores_perfect_generated_truth(tmp_path: Path) -> None:
    """생성 actual 결과와 정답지 기준으로 세 평가 지표가 모두 1.0인지 확인한다."""
    dataset = generate_performance_dataset(tmp_path, count=12)
    assert not dataset.actual_results_path.exists()
    _copy_answer_key_to_actual_results(dataset.root)

    report = evaluate_performance_dataset(dataset.root)

    assert dataset.truth_path.exists()
    assert dataset.actual_results_path.exists()
    assert dataset.elasticsearch_count == 12
    assert dataset.splunk_count == 12
    assert report.field_mapping_precision == 1.0
    assert report.field_mapping_recall == 1.0
    assert report.lineage_traceability == 1.0
    assert report.total_source_documents == 24


def test_performance_evaluation_fails_without_required_files(tmp_path: Path) -> None:
    """답안지나 actual 결과가 빠진 dataset은 실패해야 한다."""
    generate_performance_dataset(tmp_path, count=2)

    runner = CliRunner()
    missing_actual = runner.invoke(
        app,
        ["evaluate-performance-dataset", "--dataset-dir", str(tmp_path)],
    )
    _copy_answer_key_to_actual_results(tmp_path)
    (tmp_path / "answer_key.json").unlink()
    missing_answer_key = runner.invoke(
        app,
        ["evaluate-performance-dataset", "--dataset-dir", str(tmp_path)],
    )
    generate_performance_dataset(tmp_path, count=2)

    assert missing_actual.exit_code != 0
    assert "actual_results.json" in missing_actual.output
    assert missing_answer_key.exit_code != 0
    assert "answer_key.json" in missing_answer_key.output


def test_performance_metrics_drop_when_actual_results_are_wrong(
    tmp_path: Path,
) -> None:
    """actual 결과가 틀리면 성공 지표가 내려가는지 확인한다."""
    generate_performance_dataset(tmp_path, count=2)
    _copy_answer_key_to_actual_results(tmp_path)
    path = tmp_path / "actual_results.json"
    actual = json.loads(path.read_text(encoding="utf-8"))
    actual["field_mappings"][0]["ocsf_field"] = "wrong.field"
    actual["lineage"][0]["opensearch_id"] = "wrong-id"
    path.write_text(json.dumps(actual), encoding="utf-8")

    report = evaluate_performance_dataset(tmp_path)

    assert report.field_mapping_precision < 1.0
    assert report.field_mapping_recall < 1.0
    assert report.lineage_traceability < 1.0


def test_performance_truth_covers_generated_mappable_fields() -> None:
    """생성 dataset의 매핑 가능 field가 정답지에서 빠지지 않는지 확인한다."""
    truth_keys = {
        (row.solution, row.index, row.source_field)
        for row in performance_mapping_truth()
        if row.action == "map"
    }
    missing: set[tuple[str, str, str]] = set()
    for solution, batches in (
        ("elasticsearch", elasticsearch_performance_batches(12)),
        ("splunk", splunk_performance_batches(12)),
    ):
        for index, docs in batches.items():
            for doc in docs:
                for source_field, value in expand_raw_json(doc).items():
                    decision = recommend_mapping(
                        FieldSample(
                            name=source_field,
                            type=_sample_type(value),
                            samples=[value],
                        )
                    )
                    if (
                        decision.action == "map"
                        and (
                            solution,
                            index,
                            source_field,
                        )
                        not in truth_keys
                    ):
                        missing.add((solution, index, source_field))

    assert not missing


def test_performance_cli_writes_metrics_json(tmp_path: Path) -> None:
    """CLI가 평가 dataset과 metrics JSON을 파일로 남기는지 확인한다."""
    runner = CliRunner()

    generated = runner.invoke(
        app,
        [
            "generate-performance-dataset",
            "--count",
            "6",
            "--output-dir",
            str(tmp_path),
        ],
    )

    assert generated.exit_code == 0
    assert not (tmp_path / "actual_results.json").exists()
    _copy_answer_key_to_actual_results(tmp_path)
    evaluated = runner.invoke(
        app,
        ["evaluate-performance-dataset", "--dataset-dir", str(tmp_path)],
    )
    assert evaluated.exit_code == 0
    assert (tmp_path / "actual_results.json").exists()
    metrics = json.loads((tmp_path / "metrics.json").read_text(encoding="utf-8"))
    assert metrics["field_mapping_precision"] == 1.0
    assert metrics["field_mapping_recall"] == 1.0
    assert metrics["lineage_traceability"] == 1.0


def _copy_answer_key_to_actual_results(root: Path) -> None:
    """테스트용 perfect actual 결과 fixture를 별도 파일로 만든다."""
    answer_key = json.loads((root / "answer_key.json").read_text(encoding="utf-8"))
    actual = {
        "dataset": answer_key["dataset"],
        "field_mappings": answer_key["field_mappings"],
        "lineage": answer_key["lineage"],
    }
    (root / "actual_results.json").write_text(
        json.dumps(actual),
        encoding="utf-8",
    )


def _sample_type(value: object) -> str:
    """테스트에서 FieldSample type 이름을 최소 규칙으로 계산한다."""
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "number"
    if isinstance(value, list):
        return "array"
    if isinstance(value, dict):
        return "object"
    return "string"
