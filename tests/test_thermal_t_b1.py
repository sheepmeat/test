"""Focused, payload-free tests for the Thermal T-B1 Stage-1 contract."""

from __future__ import annotations

import json
from pathlib import Path
import shutil

import numpy as np
import pytest

import datasets.thermal.t_b1_runner as runner
import scripts.validate_thermal_t_b1 as validator
from datasets.thermal.t_b1_model import (
    EXPECTED_PARAMETER_COUNT,
    PRIMARY_SEED,
    architecture_fingerprint,
    backend_info,
    create_small_cnn_baseline,
    fingerprint_weight_arrays,
    initial_weights,
)
from datasets.thermal.t_b1_preprocessing import (
    CLASS_ORDER,
    PreprocessingContractError,
    apply_p0,
    apply_p1,
    apply_p2,
    canonical_batch,
    compare_validation_rows,
    fit_p1_statistics,
    select_validation_winner,
)


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / validator.EVIDENCE_REL


def _copy_evidence(tmp_path: Path) -> Path:
    target = tmp_path / "T-B1"
    shutil.copytree(EVIDENCE, target)
    return target


def _mutated_evidence(tmp_path: Path, filename: str, mutate) -> dict:
    target = _copy_evidence(tmp_path)
    path = target / filename
    document = json.loads(path.read_text(encoding="utf-8"))
    mutate(document)
    path.write_text(json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    # The stale checksum is intentional: a changed contract must fail closed.
    monkey = pytest.MonkeyPatch()
    monkey.setattr(validator, "_validate_predecessors", lambda repo_root, errors: {
        "T-A6": {"evidence_validation": "PASS"},
        "T-B0": {"evidence_validation": "PASS", "t_b1_authorized": "YES_WITH_LIMITATIONS"},
    })
    try:
        return validator.validate_evidence(repo_root=ROOT, evidence_dir=target)
    finally:
        monkey.undo()


def test_clean_stage1_validator_passes() -> None:
    result = validator.validate_evidence(repo_root=ROOT, evidence_dir=EVIDENCE)
    assert result["evidence_validation"] == "PASS"
    assert result["overall_outcome"] == "T_B1_STAGE1_IMPLEMENTATION_READY_WITH_LIMITATIONS"
    assert result["t_b2_authorized"] is False


@pytest.mark.parametrize(
    ("filename", "mutate"),
    [
        ("dataset_input_contract.json", lambda d: d["roles"]["TRAIN"].update(sha256="0" * 64)),
        ("dataset_input_contract.json", lambda d: d["roles"]["VALIDATION"].update(sha256="0" * 64)),
        ("dataset_input_contract.json", lambda d: d["roles"]["REAL_EVAL_DEVELOPMENT"].update(sha256="0" * 64)),
        ("dataset_input_contract.json", lambda d: d.update(legacy_npz_authority="ALLOWED")),
        ("dataset_input_contract.json", lambda d: d.update(random_resplit="ALLOWED")),
        ("dataset_input_contract.json", lambda d: d.update(hash_resplit="ALLOWED")),
        ("dataset_input_contract.json", lambda d: d["roles"]["REAL_EVAL_DEVELOPMENT"].update(winner_selection=True)),
        ("preprocessing_implementation_registry.json", lambda d: d["profiles"][1].update(fit_role="VALIDATION")),
        ("preprocessing_implementation_registry.json", lambda d: d["profiles"][1].update(real_fit_allowed=True)),
        ("training_runtime_contract.json", lambda d: d["budget"].update(augmentation="ENABLED")),
        ("training_runtime_contract.json", lambda d: d["budget"].update(class_weighting="ENABLED")),
        ("training_runtime_contract.json", lambda d: d["budget"].update(oversampling="ENABLED")),
        ("training_runtime_contract.json", lambda d: d["budget"].update(focal_loss="ENABLED")),
        ("initialization_contract.json", lambda d: d["seed_bindings"].update(numpy=7)),
        ("limitations.json", lambda d: d.update(near_duplicate_pairs=0)),
        ("limitations.json", lambda d: d.update(sensitivity_subset="FABRICATED_CLEAN_SUBSET")),
        ("expected_result_schema.json", lambda d: d.update(stage1_status="FINALIZED")),
        ("stage1_validation_result.json", lambda d: d.update(performance_winner_selected=True)),
        ("baseline_model_contract.json", lambda d: d.update(legacy_model_replacement=True)),
        ("t_b1_execution_contract.json", lambda d: d["runner"].update(canonical_root="/Users/owner/thermal")),
        ("external_storage_contract.json", lambda d: d["canonical_role_layouts"].append("archive/thermal.npy")),
    ],
)
def test_contract_tamper_is_rejected(tmp_path: Path, filename: str, mutate) -> None:
    result = _mutated_evidence(tmp_path, filename, mutate)
    assert result["evidence_validation"] == "FAIL"
    assert result["error_count"] > 0


def test_t_a6_predecessor_tamper_is_live_checked(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []

    def fake_a6(**kwargs):
        calls.append("T-A6")
        return {"evidence_validation": "FAIL", "overall_outcome": "TAMPERED"}

    def fake_b0(**kwargs):
        calls.append("T-B0")
        return {"evidence_validation": "PASS", "t_b1_authorized": "YES_WITH_LIMITATIONS"}

    def fake_predecessors(repo_root, errors):
        a6 = fake_a6()
        b0 = fake_b0()
        errors.append({"code": "T_A6_PREDECESSOR_INVALID", "location": "T-A6", "message": "tampered"})
        return {"T-A6": a6, "T-B0": b0}

    monkeypatch.setattr(validator, "_validate_predecessors", fake_predecessors)
    result = validator.validate_evidence(repo_root=ROOT, evidence_dir=EVIDENCE, check_checksums=False)
    assert calls == ["T-A6", "T-B0"]
    assert result["evidence_validation"] == "FAIL"
    assert any(error["code"] == "T_A6_PREDECESSOR_INVALID" for error in result["errors"])


def test_p0_preserves_canonical_values_and_only_adds_channel() -> None:
    full = np.linspace(20.0, 24.25, 62 * 80, dtype="<f4").reshape(1, 62, 80)
    result = apply_p0(full)
    assert result.shape == (1, 62, 80, 1)
    np.testing.assert_array_equal(result[..., 0], full)
    assert result.dtype == np.dtype("<f4")


def test_p1_is_train_only_and_deterministic() -> None:
    train = np.arange(2 * 62 * 80, dtype="<f4").reshape(2, 62, 80) + 20.0
    first = fit_p1_statistics(train, train_artifact_sha256="train")
    second = fit_p1_statistics(train, train_artifact_sha256="train")
    assert first.to_dict() == second.to_dict()
    assert first.fit_role == "TRAIN"
    assert first.fit_sample_count == 2
    with pytest.raises(PreprocessingContractError):
        fit_p1_statistics(train, fit_role="VALIDATION")
    with pytest.raises(PreprocessingContractError):
        fit_p1_statistics(train, fit_role="REAL_EVAL_DEVELOPMENT")
    applied = apply_p1(train[:1], first)
    assert applied.shape == (1, 62, 80, 1)


def test_p2_matches_legacy_preparation_and_constant_behavior() -> None:
    from inference.thermal_interpreter import ThermalInterpreter

    varied = np.linspace(20.0, 30.0, 62 * 80, dtype="<f4").reshape(1, 62, 80)
    expected = ThermalInterpreter._prepare_float_frame(varied[0])
    actual = apply_p2(varied)
    np.testing.assert_allclose(actual, expected, rtol=0, atol=0)
    constant = np.full((1, 62, 80), 42.0, dtype="<f4")
    expected_constant = ThermalInterpreter._prepare_float_frame(constant[0])
    np.testing.assert_allclose(apply_p2(constant), expected_constant, rtol=0, atol=0)


@pytest.mark.parametrize("bad", [
    np.zeros((61, 80), dtype="<f4"),
    np.zeros((62, 80), dtype="<i2"),
    np.full((62, 80), np.nan, dtype="<f4"),
    np.full((62, 80), np.inf, dtype="<f4"),
])
def test_canonical_shape_dtype_and_finite_checks(bad: np.ndarray) -> None:
    with pytest.raises(PreprocessingContractError):
        canonical_batch(bad)


def test_baseline_parameter_count_and_architecture_identity() -> None:
    model = create_small_cnn_baseline()
    assert int(model.count_params()) == EXPECTED_PARAMETER_COUNT
    assert architecture_fingerprint(model) == "937fceb88900a779d67a8e407cebc3362cc21346721f92cea5ae8de1413aba2a"
    _, fingerprint, _ = initial_weights(PRIMARY_SEED)
    assert fingerprint == "72a9805e1772aa0ee0a414fb7d41bc17ea0d183fa29e0e43049b22e0d5d35058"


def test_same_initial_weights_are_reproducible() -> None:
    first, first_fp, _ = initial_weights(PRIMARY_SEED)
    second, second_fp, _ = initial_weights(PRIMARY_SEED)
    assert first_fp == second_fp
    assert fingerprint_weight_arrays(first) == fingerprint_weight_arrays(second)


def test_winner_rule_is_validation_only_and_tie_deterministic() -> None:
    base = {"validation_metrics": {"macro_f1": 0.5, "balanced_accuracy": 0.5, "h_fall_posture_proxy_recall": 0.5}, "parameter_count": 10, "tflite_artifact_size_bytes": 100}
    left = {**base, "profile_id": "P0"}
    right = {**base, "profile_id": "P1"}
    assert compare_validation_rows(left, right) < 0
    tie_left = {**left, "profile_id": "SAME", "validation_metrics": {**base["validation_metrics"], "macro_f1": 0.500005}}
    tie_right = {**right, "profile_id": "SAME"}
    assert compare_validation_rows(tie_left, tie_right) == 0
    winner = select_validation_winner([right, left])
    assert winner["profile_id"] == "P0"
    with pytest.raises(PreprocessingContractError):
        select_validation_winner([{**left, "real_metrics": {"macro_f1": 1.0}}])


def test_stage1_does_not_require_external_ssd() -> None:
    result = runner.run(
        mode=runner.STAGE1_MODE,
        canonical_root="/path/that/is/not/required/in_stage1",
        work_root=ROOT / ".tmp-t-b1-test-work",
        output_root=ROOT / ".tmp-t-b1-test-output",
        repo_root=ROOT,
        dry_run=True,
    )
    assert result["status"] == "STAGE1_IMPLEMENTATION_READY"


def test_full_dry_run_missing_ssd_fails_closed(tmp_path: Path) -> None:
    with pytest.raises(runner.RunnerContractError, match="EXTERNAL_CANONICAL_ROOT_UNAVAILABLE"):
        runner.run(
            mode=runner.FULL_MODE,
            canonical_root=tmp_path / "missing-canonical",
            work_root=tmp_path / "work",
            output_root=tmp_path / "output",
            repo_root=ROOT,
            dry_run=True,
        )


@pytest.mark.parametrize("wrong_role", ["TRAIN", "VALIDATION", "REAL_EVAL_DEVELOPMENT"])
def test_full_canonical_preflight_rejects_wrong_role_sha(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, wrong_role: str) -> None:
    canonical = tmp_path / "canonical"
    canonical.mkdir()
    for role, original in runner.EXPECTED_ROLES.items():
        role_dir = canonical / role
        role_dir.mkdir()
        array_path = role_dir / original["filename"]
        np.save(array_path, np.zeros((1, 62, 80), dtype="<f4"), allow_pickle=False)
        provenance = role_dir / original["provenance_filename"]
        provenance.write_text(
            json.dumps({"original_label_name": "LYING", "compatibility_target": "HUMAN_FALL"}, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        spec = dict(original)
        spec["rows"] = 1
        spec["size_bytes"] = array_path.stat().st_size
        spec["sha256"] = "0" * 64 if role == wrong_role else runner.sha256_file(array_path)
        monkeypatch.setitem(runner.EXPECTED_ROLES, role, spec)
    with pytest.raises(runner.RunnerContractError, match="SHA-256 mismatch"):
        runner.validate_canonical_root(canonical, full_hash=True)


def test_full_mode_requires_owner_authorization(tmp_path: Path) -> None:
    with pytest.raises(runner.RunnerContractError, match="OWNER_AUTHORIZATION"):
        runner.run_full_experiment(
            canonical_root=tmp_path / "unused",
            work_root=tmp_path / "work",
            output_root=tmp_path / "output",
            repo_root=ROOT,
            dry_run=False,
            owner_authorized=False,
        )


def test_cpu_backend_policy_allows_missing_gpu() -> None:
    info = backend_info()
    assert info["gpu_optional"] is True
    assert info["backend_selected"] in {"CPU", "APPLE_METAL"}


def test_fixture_result_cannot_be_finalized_in_stage1() -> None:
    schema = json.loads((EVIDENCE / "expected_result_schema.json").read_text(encoding="utf-8"))
    assert schema["stage1_status"] == "PENDING_FULL_EXPERIMENT"
    assert "full_performance_metrics" in schema["stage1_forbidden"]


def test_legacy_tflite_is_not_replaced() -> None:
    contract = json.loads((EVIDENCE / "baseline_model_contract.json").read_text(encoding="utf-8"))
    assert contract["legacy_model_replacement"] is False
    assert contract["tflite_conversion_in_stage1"] is False


def test_runner_role_order_is_frozen() -> None:
    assert runner.ROLE_ORDER == ("TRAIN", "VALIDATION", "REAL_EVAL_DEVELOPMENT")
    assert list(CLASS_ORDER) == ["NOT_HUMAN", "HUMAN_NORMAL", "HUMAN_FALL"]


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__]))
