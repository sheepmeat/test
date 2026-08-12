"""Focused fail-closed tests for M-B12 Phase-B offline final closure.

Mutations use temporary copies. No LOCKED_TEST or recovery access.
No TFLite invoke is required for mutation tests.
"""

from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts import mmwave_m_b12_phase_b_closure as generator
from scripts import validate_mmwave_m_b12 as validator
from scripts.mmwave_m_b12_phase_b_closure import CLOSURE_DIR_REL, write_checksums

ROOT = Path(__file__).resolve().parents[1]
CLOSURE = ROOT / CLOSURE_DIR_REL


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _dump(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


class MB12Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if not (CLOSURE / "phase_b_closure_identity.json").is_file():
            generator.generate_m_b12_closure(ROOT)

    def _copy_closure(self) -> Path:
        tmp = Path(tempfile.mkdtemp(prefix="m_b12_closure_"))
        shutil.copytree(CLOSURE, tmp / "closure")
        return tmp / "closure"

    def _mutate(self, filename: str, mutator, rewrite: bool = True) -> Path:
        closure_dir = self._copy_closure()
        path = closure_dir / filename
        payload = _load(path)
        mutator(payload)
        _dump(path, payload)
        if rewrite:
            write_checksums(closure_dir)
        return closure_dir

    def _expect_fail(self, closure_dir: Path, fragment: str) -> None:
        with self.assertRaises(validator.MB12ValidationError) as ctx:
            validator.validate_m_b12(ROOT, closure_dir=closure_dir, skip_m_b11=True)
        self.assertIn(fragment, str(ctx.exception))

    def test_valid_closure_passes(self) -> None:
        result = validator.validate_m_b12(ROOT)
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["macro_f1"], 0.494836)
        self.assertEqual(result["model_sha256"], generator.EXPECTED_MODEL_SHA)
        self.assertTrue(result["phase_b_offline_intermediate_release_ready_after_merge"])
        self.assertFalse(result["Phase_B_release_ready"])
        self.assertFalse(result["git_tag_created"])
        self.assertFalse(result["github_release_created"])
        self.assertFalse(result["m_c_started"])
        self.assertEqual(result["new_locked_test_access"], 0)
        self.assertEqual(result["new_recovery_access"], 0)
        self.assertEqual(result["new_model_inference"], 0)
        self.assertEqual(result["source_ledger"]["unique_ids"], 75)
        self.assertEqual(result["source_ledger"]["pairs"], 225)
        self.assertEqual(result["source_ledger"]["recording_mismatches"], 0)

    def test_no_access_monkeypatch_still_passes(self) -> None:
        def boom(*_args, **_kwargs):
            raise AssertionError("ACCESSOR_TOUCHED")

        with mock.patch(
            "scripts.mmwave_phase_b_access.PhaseBAccessGuard.get_locked_test_final_evaluation_dataset",
            side_effect=boom,
        ), mock.patch(
            "scripts.mmwave_m_b10r1_recovery_access.LimitedReuseRecoveryAccessController.get_locked_test_recovery_evaluation_dataset",
            side_effect=boom,
        ):
            result = validator.validate_m_b12(ROOT)
        self.assertEqual(result["status"], "PASS")

    def test_no_inference_monkeypatch_still_passes(self) -> None:
        import tensorflow as tf  # type: ignore

        def boom(*_args, **_kwargs):
            raise AssertionError("TFLITE_INVOKE_TOUCHED")

        with mock.patch.object(tf.lite.Interpreter, "invoke", side_effect=boom):
            result = validator.validate_m_b12(ROOT)
        self.assertEqual(result["status"], "PASS")

    def test_identity_result_limitation_pristine(self) -> None:
        closure_dir = self._mutate(
            "phase_b_closure_identity.json",
            lambda payload: payload.__setitem__("result_limitation", "PRISTINE_LOCKED_TEST"),
        )
        self._expect_fail(closure_dir, "FORBIDDEN_POSITIVE_CLAIM")

    def test_summary_phase_b_release_ready_true(self) -> None:
        closure_dir = self._mutate(
            "phase_b_closure_summary.json",
            lambda payload: payload.__setitem__("Phase_B_release_ready", True),
        )
        self._expect_fail(closure_dir, "FORBIDDEN_POSITIVE_CLAIM")

    def test_readiness_deployment_ready_true(self) -> None:
        closure_dir = self._mutate(
            "release_readiness_manifest.json",
            lambda payload: payload.__setitem__("deployment_ready", True),
        )
        self._expect_fail(closure_dir, "FORBIDDEN_POSITIVE_CLAIM")

    def test_git_tag_created_true(self) -> None:
        closure_dir = self._mutate(
            "release_readiness_manifest.json",
            lambda payload: payload.__setitem__("git_tag_created", True),
        )
        self._expect_fail(closure_dir, "FORBIDDEN_POSITIVE_CLAIM")

    def test_github_release_created_true(self) -> None:
        closure_dir = self._mutate(
            "claim_boundary.json",
            lambda payload: payload.__setitem__("github_release_created", True),
        )
        self._expect_fail(closure_dir, "FORBIDDEN_POSITIVE_CLAIM")

    def test_m_c_started_true(self) -> None:
        closure_dir = self._mutate(
            "device_domain_handoff.json",
            lambda payload: payload.__setitem__("m_c_started", True),
        )
        self._expect_fail(closure_dir, "FORBIDDEN_POSITIVE_CLAIM")

    def test_clinical_apnea_validated_true(self) -> None:
        closure_dir = self._mutate(
            "claim_boundary.json",
            lambda payload: payload.__setitem__("clinical_apnea_validated", True),
        )
        self._expect_fail(closure_dir, "FORBIDDEN_POSITIVE_CLAIM")

    def test_result_not_pristine_false(self) -> None:
        closure_dir = self._mutate(
            "final_evaluation_summary.json",
            lambda payload: payload.__setitem__("result_not_pristine", False),
        )
        self._expect_fail(closure_dir, "RESULT_NOT_PRISTINE_FALSE")

    def test_macro_f1_altered(self) -> None:
        closure_dir = self._mutate(
            "final_evaluation_summary.json",
            lambda payload: payload.__setitem__("macro_f1", 0.999999),
        )
        self._expect_fail(closure_dir, "MACRO_F1")

    def test_model_sha_altered(self) -> None:
        closure_dir = self._mutate(
            "locked_candidate_summary.json",
            lambda payload: payload.__setitem__("sha256", "0" * 64),
        )
        self._expect_fail(closure_dir, "CANDIDATE_SHA")

    def test_historical_total_altered(self) -> None:
        closure_dir = self._mutate(
            "final_evaluation_summary.json",
            lambda payload: payload.__setitem__("historical_total_payload_releases", 1),
        )
        self._expect_fail(closure_dir, "HIST_TOTAL")

    def test_recording_mismatch_field_altered(self) -> None:
        closure_dir = self._mutate(
            "final_evaluation_summary.json",
            lambda payload: payload.__setitem__("cross_model_recording_mismatches", 1),
        )
        self._expect_fail(closure_dir, "RECORDING")

    def test_seed43_reselection(self) -> None:
        def mutate(payload: dict) -> None:
            payload["candidate_id"] = "M-B3_CONV1D_GAP_BASELINE_seed43_M-B5_CAL_CLASS_BALANCED_120"
            payload["seed"] = 43

        closure_dir = self._mutate("locked_candidate_summary.json", mutate)
        self._expect_fail(closure_dir, "CANDIDATE_ID")

    def test_absolute_path(self) -> None:
        closure_dir = self._mutate(
            "source_and_population_summary.json",
            lambda payload: payload.__setitem__("raw_archive_repo_relative_path", "/tmp/db_records.zip"),
        )
        self._expect_fail(closure_dir, "UNSAFE_PATH")

    def test_missing_file(self) -> None:
        closure_dir = self._copy_closure()
        (closure_dir / "final_evaluation_summary.json").unlink()
        self._expect_fail(closure_dir, "CHECKSUM_TARGET_MISSING")

    def test_checksum_corruption(self) -> None:
        closure_dir = self._copy_closure()
        checksum = closure_dir / "checksums.sha256"
        lines = checksum.read_text(encoding="utf-8").splitlines()
        digest, name = lines[0].split()
        lines[0] = ("0" * 64) + "  " + name
        checksum.write_text("\n".join(lines) + "\n", encoding="utf-8")
        self._expect_fail(closure_dir, "CHECKSUM_MISMATCH")

    def test_validator_does_not_generate_or_invoke(self) -> None:
        source = Path(validator.__file__).read_text(encoding="utf-8")
        self.assertNotIn("generate_m_b12_closure", source)
        self.assertNotIn("analyze_recovery_ledger", source)


if __name__ == "__main__":
    unittest.main()
