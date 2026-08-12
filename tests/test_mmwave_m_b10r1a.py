"""Focused fail-closed tests for M-B10R1-A recovery harness pre-freeze.

No real recovery LOCKED_TEST access. Mutations use temporary copies / mocks.
"""

from __future__ import annotations

import ast
import copy
import hashlib
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts import validate_mmwave_m_b10r1a as validator
from scripts.mmwave_m_b10r1_metrics import (
    metric_bundle,
    saturation_audit_from_rows,
    subject_metrics,
    quantize_with_saturation,
)
from scripts.mmwave_m_b10r1_recovery_access import (
    EXPECTED_ELIGIBLE,
    ORIGINAL_FINAL_TOKEN,
    RECOVERY_AUTHORIZATION_TOKEN,
    LimitedReuseRecoveryAccessController,
    RecoveryAccessError,
    RecoveryReadiness,
)
from scripts.mmwave_m_b10r1_recovery_eval import (
    build_bound_contract_identity,
    readiness_summary,
)
from scripts.mmwave_m_b10r1a_prefreeze import generate_m_b10r1a_prefreeze
from scripts import run_mmwave_m_b10r1 as runner_cli

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / validator.OUT_DIR_REL


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _rewrite_checksums(path: Path) -> None:
    lines = []
    for item in sorted(path.iterdir(), key=lambda value: value.name):
        if not item.is_file() or item.name == "checksums.sha256":
            continue
        lines.append(f"{_sha256_file(item)}  {item.name}")
    (path / "checksums.sha256").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _copy_output() -> tuple[tempfile.TemporaryDirectory[str], Path]:
    holder = tempfile.TemporaryDirectory()
    destination = Path(holder.name) / "evidence"
    shutil.copytree(OUT, destination)
    return holder, destination


def _mutate_json(path: Path, filename: str, **updates: object) -> None:
    target = path / filename
    data = json.loads(target.read_text(encoding="utf-8"))
    data.update(updates)
    target.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    _rewrite_checksums(path)


def _nested_set(data: dict, dotted: str, value: object) -> None:
    parts = dotted.split(".")
    cur = data
    for part in parts[:-1]:
        cur = cur[part]
    cur[parts[-1]] = value


def _mutate_nested(path: Path, filename: str, dotted: str, value: object) -> None:
    target = path / filename
    data = json.loads(target.read_text(encoding="utf-8"))
    _nested_set(data, dotted, value)
    target.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    _rewrite_checksums(path)


def _bound_for_tests(root: Path = ROOT) -> dict:
    return build_bound_contract_identity(root)


def _authorized_readiness() -> RecoveryReadiness:
    return RecoveryReadiness(
        recovery_execution_authorized=True,
        recovery_payload_release_authorized=True,
        independent_review_required=True,
        mechanism_implemented=True,
        runner_implemented=True,
        pre_access_validator_pass=True,
        M_B10R1B_started=True,
    )


class MetricEngineTests(unittest.TestCase):
    def test_perfect_predictions(self) -> None:
        labels = [0, 1, 2, 0, 1, 2]
        preds = [0, 1, 2, 0, 1, 2]
        bundle = metric_bundle(labels, preds)
        self.assertEqual(bundle["accuracy"], 1.0)
        self.assertEqual(bundle["macro_f1"], 1.0)
        self.assertEqual(bundle["apnea_proxy"]["misses"], 0)
        self.assertFalse(bundle["class_collapse"]["collapsed"])

    def test_support_zero_semantics(self) -> None:
        labels = [0, 0, 1, 1]
        preds = [0, 0, 1, 1]
        bundle = metric_bundle(labels, preds)
        self.assertEqual(bundle["per_class"]["APNEA"]["support"], 0)
        self.assertEqual(bundle["per_class"]["APNEA"]["precision"], 0.0)
        self.assertEqual(bundle["per_class"]["APNEA"]["recall"], 0.0)
        self.assertEqual(bundle["per_class"]["APNEA"]["f1_score"], 0.0)
        self.assertIn("APNEA", bundle["class_collapse"]["zero_prediction_classes"])

    def test_confusion_and_apnea_misses(self) -> None:
        labels = [2, 2, 2, 0]
        preds = [2, 0, 1, 0]
        bundle = metric_bundle(labels, preds)
        self.assertEqual(bundle["apnea_proxy"]["misses"], 2)
        self.assertEqual(bundle["confusion_matrix"][2][2], 1)

    def test_subject_metrics_worst_and_median(self) -> None:
        records = [
            {"subject_id": "A", "true_class_index": 0, "predicted_class_index": 0},
            {"subject_id": "A", "true_class_index": 1, "predicted_class_index": 1},
            {"subject_id": "B", "true_class_index": 0, "predicted_class_index": 2},
            {"subject_id": "B", "true_class_index": 1, "predicted_class_index": 2},
        ]
        result = subject_metrics(records)
        self.assertEqual(result["subject_count"], 2)
        self.assertEqual(result["worst_subject_id"], "B")
        self.assertGreater(result["median_subject_macro_f1"], result["worst_subject_macro_f1"] - 1e-9)

    def test_saturation_audit_and_quantize(self) -> None:
        ready = np.full((1, 300, 1), 100.0, dtype=np.float32)
        q = quantize_with_saturation(ready, scale=0.01, zero_point=0, contract_id="TEST")
        self.assertGreater(q["input_saturation_count"], 0)
        audit = saturation_audit_from_rows(
            [
                {
                    "window_id": "w1",
                    "input_saturation_count": q["input_saturation_count"],
                    "input_saturation_ratio": q["input_saturation_ratio"],
                }
            ]
        )
        self.assertEqual(audit["total_quantized_elements"], 300)
        self.assertEqual(audit["samples_with_any_saturation"], 1)


class RecoveryAccessNegativeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        self.state_path = Path(self.tmpdir.name) / "state.json"
        self.controller = LimitedReuseRecoveryAccessController(ROOT, audit_state_path=self.state_path)
        self.bound = _bound_for_tests()

    def tearDown(self) -> None:
        self.tmpdir.cleanup()

    def test_no_auth_refused(self) -> None:
        with self.assertRaises(RecoveryAccessError):
            self.controller.get_locked_test_recovery_evaluation_dataset(
                None, self.bound, _authorized_readiness()
            )

    def test_wrong_original_final_token_refused(self) -> None:
        with self.assertRaises(RecoveryAccessError) as ctx:
            self.controller.get_locked_test_recovery_evaluation_dataset(
                ORIGINAL_FINAL_TOKEN, self.bound, _authorized_readiness()
            )
        self.assertIn("ORIGINAL_FINAL_TOKEN_REJECTED", str(ctx.exception))

    def test_malformed_auth_refused(self) -> None:
        with self.assertRaises(RecoveryAccessError):
            self.controller.get_locked_test_recovery_evaluation_dataset(
                "NOT_A_VALID_TOKEN", self.bound, _authorized_readiness()
            )

    def test_readiness_false_refused(self) -> None:
        readiness = RecoveryReadiness(
            recovery_execution_authorized=False,
            recovery_payload_release_authorized=False,
        )
        with self.assertRaises(RecoveryAccessError):
            self.controller.get_locked_test_recovery_evaluation_dataset(
                RECOVERY_AUTHORIZATION_TOKEN, self.bound, readiness
            )

    def test_contract_sha_mismatch_refused(self) -> None:
        bad = copy.deepcopy(self.bound)
        bad["selected_model_sha256"] = "0" * 64
        with self.assertRaises(RecoveryAccessError) as ctx:
            self.controller.get_locked_test_recovery_evaluation_dataset(
                RECOVERY_AUTHORIZATION_TOKEN, bad, _authorized_readiness()
            )
        self.assertIn("BOUND_CONTRACT_SHA_MISMATCH", str(ctx.exception))

    def test_include_ambiguous_true_refused(self) -> None:
        bad = copy.deepcopy(self.bound)
        bad["include_ambiguous"] = True
        with self.assertRaises(RecoveryAccessError):
            self.controller.get_locked_test_recovery_evaluation_dataset(
                RECOVERY_AUTHORIZATION_TOKEN, bad, _authorized_readiness()
            )

    def test_second_recovery_after_consumed(self) -> None:
        # Simulate consumed without real load.
        self.controller._state["payload_consumed"] = True
        self.controller._state["recovery_payload_release_events"] = 1
        self.controller._persist()
        with self.assertRaises(RecoveryAccessError):
            self.controller.get_locked_test_recovery_evaluation_dataset(
                RECOVERY_AUTHORIZATION_TOKEN, self.bound, _authorized_readiness()
            )

    def test_retry_after_release_keeps_consumed(self) -> None:
        fake_payload = {
            "total_count": EXPECTED_ELIGIBLE,
            "windows": [
                {"assignment_status": "PURE", "split": "LOCKED_TEST", "subject_id": f"s{i % 16}"}
                for i in range(EXPECTED_ELIGIBLE)
            ],
            "signals": [None] * EXPECTED_ELIGIBLE,
        }

        def _fake_load(**_kwargs):
            return fake_payload

        with mock.patch.object(self.controller, "_load_eligible_locked_test", side_effect=_fake_load):
            payload = self.controller.get_locked_test_recovery_evaluation_dataset(
                RECOVERY_AUTHORIZATION_TOKEN, self.bound, _authorized_readiness()
            )
            self.assertEqual(payload["total_count"], EXPECTED_ELIGIBLE)
        self.assertTrue(self.controller.snapshot()["payload_consumed"])
        self.assertEqual(self.controller.snapshot()["recovery_payload_release_events"], 1)
        # Second access refused
        with self.assertRaises(RecoveryAccessError):
            self.controller.get_locked_test_recovery_evaluation_dataset(
                RECOVERY_AUTHORIZATION_TOKEN, self.bound, _authorized_readiness()
            )
        # Historical original never reset
        self.assertEqual(self.controller.snapshot()["original_final_accessor_invocations"], 1)

    def test_post_release_failure_still_consumed_no_retry(self) -> None:
        def _boom(**_kwargs):
            raise RuntimeError("simulated post-mark failure")

        with mock.patch.object(self.controller, "_load_eligible_locked_test", side_effect=_boom):
            with self.assertRaises(RuntimeError):
                self.controller.get_locked_test_recovery_evaluation_dataset(
                    RECOVERY_AUTHORIZATION_TOKEN, self.bound, _authorized_readiness()
                )
        self.assertTrue(self.controller.snapshot()["payload_consumed"])
        with self.assertRaises(RecoveryAccessError):
            self.controller.get_locked_test_recovery_evaluation_dataset(
                RECOVERY_AUTHORIZATION_TOKEN, self.bound, _authorized_readiness()
            )


class PrefreezeValidatorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        # Ensure evidence exists for validator tests.
        if not OUT.is_dir():
            generate_m_b10r1a_prefreeze(ROOT)

    def test_validator_passes(self) -> None:
        # Never stamp/mutate the live prefreeze tree from unit tests.
        result = validator.validate_m_b10r1a_artifacts(
            ROOT, skip_upstream=True, mark_validator_pass=False
        )
        self.assertEqual(result["validation_status"], "PASS")
        self.assertFalse(result["recovery_execution_authorized"])

    def test_historical_counter_reset_fails(self) -> None:
        holder, destination = _copy_output()
        try:
            _mutate_json(
                destination,
                "recovery_access_audit.json",
                **{"historical_original_final_accessor_invocations": 0},
            )
            with self.assertRaises(validator.MB10R1AValidationError):
                validator.validate_m_b10r1a_artifacts(
                    ROOT, output_dir=destination, skip_upstream=True, mark_validator_pass=False
                )
        finally:
            holder.cleanup()

    def test_original_consumed_false_fails(self) -> None:
        holder, destination = _copy_output()
        try:
            _mutate_json(destination, "recovery_access_audit.json", original_locked_test_consumed=False)
            with self.assertRaises(validator.MB10R1AValidationError):
                validator.validate_m_b10r1a_artifacts(
                    ROOT, output_dir=destination, skip_upstream=True, mark_validator_pass=False
                )
        finally:
            holder.cleanup()

    def test_wrong_population_counts_fail(self) -> None:
        holder, destination = _copy_output()
        try:
            _mutate_json(destination, "recovery_population_contract.json", supervised_eligible_windows=88)
            with self.assertRaises(validator.MB10R1AValidationError):
                validator.validate_m_b10r1a_artifacts(
                    ROOT, output_dir=destination, skip_upstream=True, mark_validator_pass=False
                )
        finally:
            holder.cleanup()

    def test_include_ambiguous_true_fails(self) -> None:
        holder, destination = _copy_output()
        try:
            _mutate_json(destination, "recovery_population_contract.json", include_ambiguous=True)
            with self.assertRaises(validator.MB10R1AValidationError):
                validator.validate_m_b10r1a_artifacts(
                    ROOT, output_dir=destination, skip_upstream=True, mark_validator_pass=False
                )
        finally:
            holder.cleanup()

    def test_seed43_model_fails(self) -> None:
        holder, destination = _copy_output()
        try:
            data = json.loads((destination / "model_identity_registry.json").read_text(encoding="utf-8"))
            data["models"][0]["model_id"] = "M-B3_CONV1D_GAP_BASELINE_seed43_M-B6_STRICT_INT8"
            (destination / "model_identity_registry.json").write_text(
                json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8"
            )
            _rewrite_checksums(destination)
            with self.assertRaises(validator.MB10R1AValidationError):
                validator.validate_m_b10r1a_artifacts(
                    ROOT, output_dir=destination, skip_upstream=True, mark_validator_pass=False
                )
        finally:
            holder.cleanup()

    def test_seed44_and_fourth_model_fail(self) -> None:
        holder, destination = _copy_output()
        try:
            data = json.loads((destination / "model_identity_registry.json").read_text(encoding="utf-8"))
            data["models"].append({"model_id": "M-B3_CONV1D_GAP_BASELINE_seed44_M-B6_STRICT_INT8"})
            (destination / "model_identity_registry.json").write_text(
                json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8"
            )
            _rewrite_checksums(destination)
            with self.assertRaises(validator.MB10R1AValidationError):
                validator.validate_m_b10r1a_artifacts(
                    ROOT, output_dir=destination, skip_upstream=True, mark_validator_pass=False
                )
        finally:
            holder.cleanup()

    def test_baseline_executor_sha_change_fails(self) -> None:
        holder, destination = _copy_output()
        try:
            _mutate_nested(
                destination,
                "baseline_identity_registry.json",
                "executor_sha256",
                "0" * 64,
            )
            with self.assertRaises(validator.MB10R1AValidationError):
                validator.validate_m_b10r1a_artifacts(
                    ROOT, output_dir=destination, skip_upstream=True, mark_validator_pass=False
                )
        finally:
            holder.cleanup()

    def test_baseline_metadata_sha_change_fails(self) -> None:
        holder, destination = _copy_output()
        try:
            _mutate_nested(
                destination,
                "baseline_identity_registry.json",
                "v0_1.metadata_sha256",
                "0" * 64,
            )
            with self.assertRaises(validator.MB10R1AValidationError):
                validator.validate_m_b10r1a_artifacts(
                    ROOT, output_dir=destination, skip_upstream=True, mark_validator_pass=False
                )
        finally:
            holder.cleanup()

    def test_metric_schema_corruption_fails(self) -> None:
        holder, destination = _copy_output()
        try:
            data = json.loads((destination / "metric_contract.json").read_text(encoding="utf-8"))
            data["metrics_schema"]["primary"] = "accuracy"
            (destination / "metric_contract.json").write_text(
                json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8"
            )
            _rewrite_checksums(destination)
            with self.assertRaises(validator.MB10R1AValidationError):
                validator.validate_m_b10r1a_artifacts(
                    ROOT, output_dir=destination, skip_upstream=True, mark_validator_pass=False
                )
        finally:
            holder.cleanup()

    def test_authorization_true_fails(self) -> None:
        holder, destination = _copy_output()
        try:
            _mutate_json(destination, "recovery_access_readiness.json", recovery_execution_authorized=True)
            with self.assertRaises(validator.MB10R1AValidationError):
                validator.validate_m_b10r1a_artifacts(
                    ROOT, output_dir=destination, skip_upstream=True, mark_validator_pass=False
                )
        finally:
            holder.cleanup()


class CliAndMonkeypatchTests(unittest.TestCase):
    def test_default_cli_no_access(self) -> None:
        called = {"recovery": False}

        def _boom(*_a, **_k):
            called["recovery"] = True
            raise AssertionError("recovery must not be called")

        with mock.patch(
            "scripts.mmwave_m_b10r1_recovery_access.LimitedReuseRecoveryAccessController.get_locked_test_recovery_evaluation_dataset",
            side_effect=_boom,
        ):
            rc = runner_cli.main([])
        self.assertEqual(rc, 0)
        self.assertFalse(called["recovery"])
        summary = readiness_summary(ROOT)
        self.assertFalse(summary["recovery_accessor_invoked"])

    def test_execute_flag_without_token_refuses(self) -> None:
        rc = runner_cli.main(["--execute-authorized-limited-reuse-recovery"])
        self.assertEqual(rc, 2)

    def test_monkeypatch_forbids_real_recovery_during_generator_validator(self) -> None:
        def _forbidden(*_a, **_k):
            raise RuntimeError("FORBIDDEN_M_B10R1A_REAL_RECOVERY_ACCESS")

        holder = tempfile.TemporaryDirectory()
        try:
            with mock.patch(
                "scripts.mmwave_m_b10r1_recovery_access.LimitedReuseRecoveryAccessController.get_locked_test_recovery_evaluation_dataset",
                side_effect=_forbidden,
            ):
                # Pre-access CLI must not call recovery get_*
                self.assertEqual(runner_cli.main(["--pre-access"]), 0)
                # Validator against live committed evidence must not call recovery get_*
                outcome = validator.validate_m_b10r1a_artifacts(
                    ROOT, skip_upstream=True, mark_validator_pass=False
                )
                self.assertEqual(outcome["validation_status"], "PASS")
                # Validate an isolated evidence copy (never mutate committed tree)
                dest = Path(holder.name) / "evidence"
                shutil.copytree(OUT, dest)
                outcome2 = validator.validate_m_b10r1a_artifacts(
                    ROOT, output_dir=dest, skip_upstream=True, mark_validator_pass=False
                )
                self.assertEqual(outcome2["validation_status"], "PASS")
        finally:
            holder.cleanup()

    def test_recovery_module_never_calls_final_accessor(self) -> None:
        source = (ROOT / "scripts/mmwave_m_b10r1_recovery_access.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func = node.func
                name = None
                if isinstance(func, ast.Name):
                    name = func.id
                elif isinstance(func, ast.Attribute):
                    name = func.attr
                self.assertNotEqual(name, "get_locked_test_final_evaluation_dataset")

    def test_validator_source_never_calls_recovery_get(self) -> None:
        source = (ROOT / "scripts/validate_mmwave_m_b10r1a.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func = node.func
                name = None
                if isinstance(func, ast.Name):
                    name = func.id
                elif isinstance(func, ast.Attribute):
                    name = func.attr
                self.assertNotEqual(name, "get_locked_test_recovery_evaluation_dataset")
                self.assertNotEqual(name, "get_locked_test_final_evaluation_dataset")


if __name__ == "__main__":
    unittest.main()
