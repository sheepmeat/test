"""Focused fail-closed tests for M-B10R0 holdout policy evidence."""

from __future__ import annotations

import copy
import hashlib
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts import validate_mmwave_m_b10r0 as validator
from scripts.mmwave_m_b10r0_holdout_policy import (
    OUT_DIR_REL,
    MODEL_SPECS,
    RESULT_LIMITATION,
    RECOVERY_CONTRACT_STATUS,
    SELECTED_SHA,
    M_B10A_CONTRACT_SHA,
    EXPECTED_CONTRACT_MODEL_IDS,
    generate_m_b10r0_evidence,
)

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / OUT_DIR_REL


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _copy_output() -> tuple[tempfile.TemporaryDirectory[str], Path]:
    holder = tempfile.TemporaryDirectory()
    destination = Path(holder.name) / "evidence"
    shutil.copytree(OUT, destination)
    return holder, destination


def _rewrite_checksums(path: Path) -> None:
    lines = []
    for item in sorted(path.iterdir(), key=lambda value: value.name):
        if not item.is_file() or item.name == "checksums.sha256":
            continue
        lines.append(f"{_sha256_file(item)}  {item.name}")
    (path / "checksums.sha256").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _mutate_json(path: Path, filename: str, **updates: object) -> None:
    target = path / filename
    data = json.loads(target.read_text(encoding="utf-8"))
    data.update(updates)
    target.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    _rewrite_checksums(path)


class MB10R0PolicyTests(unittest.TestCase):
    def test_validator_passes_on_current_evidence(self) -> None:
        result = validator.validate_m_b10r0_artifacts(ROOT, output_dir=OUT)
        self.assertEqual(result["validation_status"], "PASS")
        self.assertEqual(result["policy_decision"], "LIMITED_LOCKED_TEST_REUSE_EXCEPTION_RECOMMENDED")
        self.assertFalse(result["recovery_execution_authorized"])
        self.assertFalse(result["locked_test_reopen_authorized"])
        self.assertFalse(result["m_b11_authorized"])
        self.assertEqual(result["m_b10r0_accessor_invocations"], 0)

    def test_validator_never_calls_final_accessor(self) -> None:
        def _boom(*_args, **_kwargs):
            raise AssertionError("final accessor must not be called")

        with mock.patch(
            "scripts.mmwave_phase_b_access.PhaseBAccessGuard.get_locked_test_final_evaluation_dataset",
            side_effect=_boom,
        ):
            result = validator.validate_m_b10r0_artifacts(ROOT, output_dir=OUT)
        self.assertEqual(result["validation_status"], "PASS")

    def test_rejects_previous_accessor_zero(self) -> None:
        holder, dest = _copy_output()
        try:
            _mutate_json(dest, "incident_identity.json", original_accessor_invocations=0)
            with self.assertRaises(validator.MB10R0ValidationError):
                validator.validate_m_b10r0_artifacts(ROOT, output_dir=dest)
        finally:
            holder.cleanup()

    def test_rejects_previous_accessor_two(self) -> None:
        holder, dest = _copy_output()
        try:
            _mutate_json(dest, "incident_identity.json", original_accessor_invocations=2)
            with self.assertRaises(validator.MB10R0ValidationError):
                validator.validate_m_b10r0_artifacts(ROOT, output_dir=dest)
        finally:
            holder.cleanup()

    def test_rejects_inference_count_positive(self) -> None:
        holder, dest = _copy_output()
        try:
            _mutate_json(dest, "incident_identity.json", model_inference_invocations=1)
            with self.assertRaises(validator.MB10R0ValidationError):
                validator.validate_m_b10r0_artifacts(ROOT, output_dir=dest)
        finally:
            holder.cleanup()

    def test_rejects_predictions_generated(self) -> None:
        holder, dest = _copy_output()
        try:
            _mutate_json(dest, "policy_decision.json", original_predictions_generated=True)
            with self.assertRaises(validator.MB10R0ValidationError):
                validator.validate_m_b10r0_artifacts(ROOT, output_dir=dest)
        finally:
            holder.cleanup()

    def test_rejects_metrics_generated(self) -> None:
        holder, dest = _copy_output()
        try:
            _mutate_json(dest, "policy_decision.json", original_metrics_generated=True)
            with self.assertRaises(validator.MB10R0ValidationError):
                validator.validate_m_b10r0_artifacts(ROOT, output_dir=dest)
        finally:
            holder.cleanup()

    def test_rejects_recovery_authorized(self) -> None:
        holder, dest = _copy_output()
        try:
            _mutate_json(dest, "policy_decision.json", recovery_execution_authorized=True)
            with self.assertRaises(validator.MB10R0ValidationError):
                validator.validate_m_b10r0_artifacts(ROOT, output_dir=dest)
        finally:
            holder.cleanup()

    def test_rejects_locked_test_reopen_authorized(self) -> None:
        holder, dest = _copy_output()
        try:
            _mutate_json(dest, "policy_decision.json", locked_test_reopen_authorized=True)
            with self.assertRaises(validator.MB10R0ValidationError):
                validator.validate_m_b10r0_artifacts(ROOT, output_dir=dest)
        finally:
            holder.cleanup()

    def test_rejects_m_b11_authorized(self) -> None:
        holder, dest = _copy_output()
        try:
            _mutate_json(dest, "policy_decision.json", m_b11_authorized=True)
            with self.assertRaises(validator.MB10R0ValidationError):
                validator.validate_m_b10r0_artifacts(ROOT, output_dir=dest)
        finally:
            holder.cleanup()

    def test_rejects_reuse_with_unused_holdout(self) -> None:
        holder, dest = _copy_output()
        try:
            inv = json.loads((dest / "existing_unused_holdout_inventory.json").read_text())
            inv["independent_existing_holdout_available"] = True
            inv["potential_independent_replacement_subjects"] = 5
            (dest / "existing_unused_holdout_inventory.json").write_text(json.dumps(inv, indent=2, sort_keys=True) + "\n")
            _mutate_json(dest, "policy_decision.json", decision="LIMITED_LOCKED_TEST_REUSE_EXCEPTION_RECOMMENDED")
            with self.assertRaises(validator.MB10R0ValidationError):
                validator.validate_m_b10r0_artifacts(ROOT, output_dir=dest)
        finally:
            holder.cleanup()

    def test_rejects_reuse_with_failed_gate(self) -> None:
        holder, dest = _copy_output()
        try:
            gates = json.loads((dest / "reuse_exception_gate_results.json").read_text())
            gates["gates"]["R3_zero_model_evaluation"]["pass"] = False
            gates["failed_gates"] = ["R3_zero_model_evaluation"]
            gates["all_r1_r10_pass"] = False
            (dest / "reuse_exception_gate_results.json").write_text(json.dumps(gates, indent=2, sort_keys=True) + "\n")
            _mutate_json(dest, "policy_decision.json", decision="LIMITED_LOCKED_TEST_REUSE_EXCEPTION_RECOMMENDED", failed_reuse_gates=[])
            with self.assertRaises(validator.MB10R0ValidationError):
                validator.validate_m_b10r0_artifacts(ROOT, output_dir=dest)
        finally:
            holder.cleanup()

    def test_rejects_train_subject_as_replacement(self) -> None:
        holder, dest = _copy_output()
        try:
            inv = json.loads((dest / "existing_unused_holdout_inventory.json").read_text())
            inv["replacement_subject_ids"] = ["train-subject-1"]
            inv["train_subject_reuse_prohibited"] = False
            (dest / "existing_unused_holdout_inventory.json").write_text(json.dumps(inv, indent=2, sort_keys=True) + "\n")
            with self.assertRaises(validator.MB10R0ValidationError):
                validator.validate_m_b10r0_artifacts(ROOT, output_dir=dest)
        finally:
            holder.cleanup()

    def test_rejects_recovery_contract_authorized(self) -> None:
        holder, dest = _copy_output()
        try:
            _mutate_json(dest, "proposed_recovery_evaluation_contract.json", status="AUTHORIZED")
            with self.assertRaises(validator.MB10R0ValidationError):
                validator.validate_m_b10r0_artifacts(ROOT, output_dir=dest)
        finally:
            holder.cleanup()

    def test_rejects_pristine_result_limitation(self) -> None:
        holder, dest = _copy_output()
        try:
            _mutate_json(dest, "proposed_recovery_evaluation_contract.json", required_result_designation="PRISTINE_ONE_TIME_LOCKED_TEST")
            with self.assertRaises(validator.MB10R0ValidationError):
                validator.validate_m_b10r0_artifacts(ROOT, output_dir=dest)
        finally:
            holder.cleanup()

    def test_rejects_nonzero_m_b10r0_accessor(self) -> None:
        holder, dest = _copy_output()
        try:
            _mutate_json(dest, "locked_test_access_audit.json", new_m_b10r0_accessor_invocations=1)
            with self.assertRaises(validator.MB10R0ValidationError):
                validator.validate_m_b10r0_artifacts(ROOT, output_dir=dest)
        finally:
            holder.cleanup()

    def test_rejects_checksum_corruption(self) -> None:
        holder, dest = _copy_output()
        try:
            checksum = dest / "checksums.sha256"
            checksum.write_text(checksum.read_text().replace("a", "b", 1), encoding="utf-8")
            with self.assertRaises(validator.MB10R0ValidationError):
                validator.validate_m_b10r0_artifacts(ROOT, output_dir=dest)
        finally:
            holder.cleanup()

    def test_rejects_checksum_traversal(self) -> None:
        holder, dest = _copy_output()
        try:
            lines = []
            for item in sorted(dest.iterdir(), key=lambda value: value.name):
                if not item.is_file() or item.name == "checksums.sha256":
                    continue
                rel = f"../{item.name}" if item.name == "policy_decision.json" else item.name
                lines.append(f"{_sha256_file(item)}  {rel}")
            (dest / "checksums.sha256").write_text("\n".join(lines) + "\n", encoding="utf-8")
            with self.assertRaises(validator.MB10R0ValidationError):
                validator.validate_m_b10r0_artifacts(ROOT, output_dir=dest)
        finally:
            holder.cleanup()

    def test_generator_produces_expected_decision(self) -> None:
        generate_m_b10r0_evidence(ROOT)
        result = validator.validate_m_b10r0_artifacts(ROOT, output_dir=OUT)
        self.assertEqual(result["policy_decision"], "LIMITED_LOCKED_TEST_REUSE_EXCEPTION_RECOMMENDED")

    # --- Negative tests for independent subject-universe inventory ---

    def test_rejects_missing_a0_subject_in_a5(self) -> None:
        """If an original A0 subject is missing from A5, inventory must not say zero unassigned."""
        fake_inv = {
            "total_original_subjects": 110,
            "train_subjects": 78,
            "validation_subjects": 15,
            "locked_test_subjects": 16,
            "assigned_subjects": 109,
            "unassigned_subjects": 1,
            "unassigned_subject_ids": ["fake-subject-999"],
            "potential_independent_replacement_subjects": 1,
            "replacement_subject_ids": ["fake-subject-999"],
            "train_subject_reuse_prohibited": True,
            "validation_subject_reuse_prohibited": True,
            "a5_reshuffle_prohibited": True,
            "evidence_paths": [
                "datasets/mmwave/manifests/a0_raw_inventory/recording_index.jsonl",
                "datasets/mmwave/manifests/a5_subject_split/subject_split_manifest.jsonl",
            ],
            "independent_existing_holdout_available": True,
            "reason": "1 subjects in A0 are not assigned in A5.",
        }
        with mock.patch("scripts.mmwave_m_b10r0_holdout_policy._a5_inventory", return_value=fake_inv):
            with mock.patch("scripts.validate_mmwave_m_b10r0._a5_inventory", return_value=fake_inv):
                holder, dest = _copy_output()
                try:
                    with self.assertRaises(validator.MB10R0ValidationError):
                        validator.validate_m_b10r0_artifacts(ROOT, output_dir=dest)
                finally:
                    holder.cleanup()

    def test_rejects_duplicate_subject_across_splits(self) -> None:
        """If subjects overlap between splits, _a5_inventory must raise."""
        from scripts.mmwave_m_b10r0_holdout_policy import MB10R0PolicyError, _a5_inventory, A5_DIR_REL, A0_DIR_REL
        holder = tempfile.TemporaryDirectory()
        try:
            fake_root = Path(holder.name)
            a0_dir = fake_root / A0_DIR_REL
            a0_dir.mkdir(parents=True)
            a5_dir = fake_root / A5_DIR_REL
            a5_dir.mkdir(parents=True)
            (a0_dir / "recording_index.jsonl").write_text(
                '{"subject_id": "s1"}\n{"subject_id": "s2"}\n{"subject_id": "s3"}\n'
            )
            (a5_dir / "subject_split_manifest.jsonl").write_text(
                '{"subject_id": "s1", "split": "TRAIN"}\n'
                '{"subject_id": "s2", "split": "VALIDATION"}\n'
                '{"subject_id": "s2", "split": "LOCKED_TEST"}\n'
                '{"subject_id": "s3", "split": "LOCKED_TEST"}\n'
            )
            with self.assertRaises(MB10R0PolicyError) as ctx:
                _a5_inventory(fake_root)
            self.assertIn("OVERLAP", str(ctx.exception))
        finally:
            holder.cleanup()

    def test_rejects_a0_a5_subject_set_mismatch(self) -> None:
        """If A5 has subjects not in A0, _a5_inventory must raise."""
        from scripts.mmwave_m_b10r0_holdout_policy import MB10R0PolicyError, _a5_inventory, A5_DIR_REL, A0_DIR_REL
        holder = tempfile.TemporaryDirectory()
        try:
            fake_root = Path(holder.name)
            a0_dir = fake_root / A0_DIR_REL
            a0_dir.mkdir(parents=True)
            a5_dir = fake_root / A5_DIR_REL
            a5_dir.mkdir(parents=True)
            (a0_dir / "recording_index.jsonl").write_text('{"subject_id": "s1"}\n')
            (a5_dir / "subject_split_manifest.jsonl").write_text(
                '{"subject_id": "s1", "split": "TRAIN"}\n'
                '{"subject_id": "s_extra", "split": "VALIDATION"}\n'
            )
            with self.assertRaises(MB10R0PolicyError) as ctx:
                _a5_inventory(fake_root)
            self.assertIn("NOT_IN_A0", str(ctx.exception))
        finally:
            holder.cleanup()

    # --- Negative tests for R4 ---

    def test_rejects_registry_with_sample_rows(self) -> None:
        """R4 must fail if registry has actual sample rows."""
        from scripts.mmwave_m_b10r0_holdout_policy import _reuse_gates, M_B10B_DIR_REL
        holder = tempfile.TemporaryDirectory()
        try:
            fake_root = Path(holder.name)
            mb10b = fake_root / M_B10B_DIR_REL
            mb10b.mkdir(parents=True)
            # Copy real M-B10B artifacts then corrupt registry
            real_mb10b = ROOT / M_B10B_DIR_REL
            for f in real_mb10b.iterdir():
                shutil.copy2(f, mb10b / f.name)
            registry = json.loads((mb10b / "locked_test_registry.json").read_text())
            registry["samples"] = [{"id": "fake"}]
            (mb10b / "locked_test_registry.json").write_text(json.dumps(registry))
            # Also need M-B10A and A5/A6 dirs
            shutil.copytree(ROOT / "datasets/mmwave/manifests/M-B10A_candidate_selection_setup", fake_root / "datasets/mmwave/manifests/M-B10A_candidate_selection_setup")
            shutil.copytree(ROOT / "datasets/mmwave/manifests/a5_subject_split", fake_root / "datasets/mmwave/manifests/a5_subject_split")
            shutil.copytree(ROOT / "datasets/mmwave/manifests/a6_full_conversion", fake_root / "datasets/mmwave/manifests/a6_full_conversion")
            shutil.copytree(ROOT / "datasets/mmwave/manifests/a0_raw_inventory", fake_root / "datasets/mmwave/manifests/a0_raw_inventory")
            # Copy model files
            for m in [{"path": "models/mmwave/mmwave_resp_int8_v0.1.0.tflite"}, {"path": "models/mmwave/mmwave_resp_int8_v0.2.0_candidate.tflite"}]:
                src = ROOT / m["path"]
                dst = fake_root / m["path"]
                dst.parent.mkdir(parents=True, exist_ok=True)
                if src.is_file():
                    shutil.copy2(src, dst)
            gates = _reuse_gates(fake_root)
            self.assertFalse(gates["gates"]["R4_no_persisted_sample_level_payload"]["pass"])
        finally:
            holder.cleanup()

    def test_rejects_persisted_sample_id(self) -> None:
        """R4 must fail if prediction ledger has rows."""
        from scripts.mmwave_m_b10r0_holdout_policy import _exposure_assessment, M_B10B_DIR_REL
        holder = tempfile.TemporaryDirectory()
        try:
            fake_root = Path(holder.name)
            mb10b = fake_root / M_B10B_DIR_REL
            mb10b.mkdir(parents=True)
            real_mb10b = ROOT / M_B10B_DIR_REL
            for f in real_mb10b.iterdir():
                shutil.copy2(f, mb10b / f.name)
            (mb10b / "locked_test_sample_predictions.jsonl").write_text('{"sample_id": "x"}\n')
            shutil.copytree(ROOT / "datasets/mmwave/manifests/a6_full_conversion", fake_root / "datasets/mmwave/manifests/a6_full_conversion")
            exposure = _exposure_assessment(fake_root)
            self.assertTrue(exposure["E3_persistent_sample_registry"]["persisted_sample_registry_exposure"])
            self.assertTrue(exposure["summary"]["PERSISTED_SAMPLE_REGISTRY_EXPOSURE"])
        finally:
            holder.cleanup()

    def test_rejects_persisted_label_or_tensor(self) -> None:
        """R4 must fail if raw_tensors_persisted is True."""
        from scripts.mmwave_m_b10r0_holdout_policy import _exposure_assessment, M_B10B_DIR_REL
        holder = tempfile.TemporaryDirectory()
        try:
            fake_root = Path(holder.name)
            mb10b = fake_root / M_B10B_DIR_REL
            mb10b.mkdir(parents=True)
            real_mb10b = ROOT / M_B10B_DIR_REL
            for f in real_mb10b.iterdir():
                shutil.copy2(f, mb10b / f.name)
            registry = json.loads((mb10b / "locked_test_registry.json").read_text())
            registry["raw_tensors_persisted"] = True
            (mb10b / "locked_test_registry.json").write_text(json.dumps(registry))
            shutil.copytree(ROOT / "datasets/mmwave/manifests/a6_full_conversion", fake_root / "datasets/mmwave/manifests/a6_full_conversion")
            exposure = _exposure_assessment(fake_root)
            self.assertTrue(exposure["E3_persistent_sample_registry"]["persisted_sample_registry_exposure"])
        finally:
            holder.cleanup()

    # --- Negative tests for R6 ---

    def test_rejects_missing_baseline_file(self) -> None:
        """R6 must fail if baseline model file is missing."""
        from scripts.mmwave_m_b10r0_holdout_policy import _reuse_gates, M_B10B_DIR_REL
        holder = tempfile.TemporaryDirectory()
        try:
            fake_root = Path(holder.name)
            # Copy all needed dirs
            shutil.copytree(ROOT / M_B10B_DIR_REL, fake_root / M_B10B_DIR_REL)
            shutil.copytree(ROOT / "datasets/mmwave/manifests/M-B10A_candidate_selection_setup", fake_root / "datasets/mmwave/manifests/M-B10A_candidate_selection_setup")
            shutil.copytree(ROOT / "datasets/mmwave/manifests/a5_subject_split", fake_root / "datasets/mmwave/manifests/a5_subject_split")
            shutil.copytree(ROOT / "datasets/mmwave/manifests/a6_full_conversion", fake_root / "datasets/mmwave/manifests/a6_full_conversion")
            shutil.copytree(ROOT / "datasets/mmwave/manifests/a0_raw_inventory", fake_root / "datasets/mmwave/manifests/a0_raw_inventory")
            # Do NOT copy model files -> R6 will fail
            gates = _reuse_gates(fake_root)
            self.assertFalse(gates["gates"]["R6_baselines_immutable"]["pass"])
        finally:
            holder.cleanup()

    def test_rejects_baseline_sha_change(self) -> None:
        """R6 must fail if baseline SHA changes."""
        from scripts.mmwave_m_b10r0_holdout_policy import _reuse_gates, M_B10B_DIR_REL, MODEL_SPECS
        holder = tempfile.TemporaryDirectory()
        try:
            fake_root = Path(holder.name)
            shutil.copytree(ROOT / M_B10B_DIR_REL, fake_root / M_B10B_DIR_REL)
            shutil.copytree(ROOT / "datasets/mmwave/manifests/M-B10A_candidate_selection_setup", fake_root / "datasets/mmwave/manifests/M-B10A_candidate_selection_setup")
            shutil.copytree(ROOT / "datasets/mmwave/manifests/a5_subject_split", fake_root / "datasets/mmwave/manifests/a5_subject_split")
            shutil.copytree(ROOT / "datasets/mmwave/manifests/a6_full_conversion", fake_root / "datasets/mmwave/manifests/a6_full_conversion")
            shutil.copytree(ROOT / "datasets/mmwave/manifests/a0_raw_inventory", fake_root / "datasets/mmwave/manifests/a0_raw_inventory")
            for m in MODEL_SPECS[1:]:
                src = ROOT / m["path"]
                dst = fake_root / m["path"]
                dst.parent.mkdir(parents=True, exist_ok=True)
                if src.is_file():
                    dst.write_bytes(b"corrupted model data")
            gates = _reuse_gates(fake_root)
            self.assertFalse(gates["gates"]["R6_baselines_immutable"]["pass"])
        finally:
            holder.cleanup()

    # --- Negative tests for R9 ---

    def test_rejects_seed43_in_future_contract(self) -> None:
        """R9 must fail if seed43 appears in planned_models."""
        from scripts.mmwave_m_b10r0_holdout_policy import _reuse_gates, M_B10B_DIR_REL, M_B10A_DIR_REL
        holder = tempfile.TemporaryDirectory()
        try:
            fake_root = Path(holder.name)
            shutil.copytree(ROOT / M_B10B_DIR_REL, fake_root / M_B10B_DIR_REL)
            shutil.copytree(ROOT / "datasets/mmwave/manifests/M-B10A_candidate_selection_setup", fake_root / "datasets/mmwave/manifests/M-B10A_candidate_selection_setup")
            shutil.copytree(ROOT / "datasets/mmwave/manifests/a5_subject_split", fake_root / "datasets/mmwave/manifests/a5_subject_split")
            shutil.copytree(ROOT / "datasets/mmwave/manifests/a6_full_conversion", fake_root / "datasets/mmwave/manifests/a6_full_conversion")
            shutil.copytree(ROOT / "datasets/mmwave/manifests/a0_raw_inventory", fake_root / "datasets/mmwave/manifests/a0_raw_inventory")
            for m in MODEL_SPECS[1:]:
                src = ROOT / m["path"]
                dst = fake_root / m["path"]
                dst.parent.mkdir(parents=True, exist_ok=True)
                if src.is_file():
                    shutil.copy2(src, dst)
            # Corrupt contract to add seed43
            contract_path = fake_root / M_B10A_DIR_REL / "locked_test_evaluation_contract.json"
            contract = json.loads(contract_path.read_text())
            contract["planned_models"].append({"model_id": "seed43_model", "role": "EXTRA", "class_map_compatibility": {"mapping": {}}})
            contract_path.write_text(json.dumps(contract))
            gates = _reuse_gates(fake_root)
            self.assertFalse(gates["gates"]["R9_future_contract_unchanged_models_metrics"]["pass"])
        finally:
            holder.cleanup()

    def test_rejects_fourth_model_in_contract(self) -> None:
        """R9 must fail if 4 models in contract."""
        from scripts.mmwave_m_b10r0_holdout_policy import _reuse_gates, M_B10B_DIR_REL, M_B10A_DIR_REL
        holder = tempfile.TemporaryDirectory()
        try:
            fake_root = Path(holder.name)
            shutil.copytree(ROOT / M_B10B_DIR_REL, fake_root / M_B10B_DIR_REL)
            shutil.copytree(ROOT / "datasets/mmwave/manifests/M-B10A_candidate_selection_setup", fake_root / "datasets/mmwave/manifests/M-B10A_candidate_selection_setup")
            shutil.copytree(ROOT / "datasets/mmwave/manifests/a5_subject_split", fake_root / "datasets/mmwave/manifests/a5_subject_split")
            shutil.copytree(ROOT / "datasets/mmwave/manifests/a6_full_conversion", fake_root / "datasets/mmwave/manifests/a6_full_conversion")
            shutil.copytree(ROOT / "datasets/mmwave/manifests/a0_raw_inventory", fake_root / "datasets/mmwave/manifests/a0_raw_inventory")
            for m in MODEL_SPECS[1:]:
                src = ROOT / m["path"]
                dst = fake_root / m["path"]
                dst.parent.mkdir(parents=True, exist_ok=True)
                if src.is_file():
                    shutil.copy2(src, dst)
            contract_path = fake_root / M_B10A_DIR_REL / "locked_test_evaluation_contract.json"
            contract = json.loads(contract_path.read_text())
            contract["planned_models"].append({"model_id": "fourth_model", "role": "EXTRA", "class_map_compatibility": {"mapping": {}}})
            contract_path.write_text(json.dumps(contract))
            gates = _reuse_gates(fake_root)
            self.assertFalse(gates["gates"]["R9_future_contract_unchanged_models_metrics"]["pass"])
        finally:
            holder.cleanup()

    def test_rejects_metric_schema_altered(self) -> None:
        """R9 must fail if metric schema primary is changed."""
        from scripts.mmwave_m_b10r0_holdout_policy import _reuse_gates, M_B10B_DIR_REL, M_B10A_DIR_REL
        holder = tempfile.TemporaryDirectory()
        try:
            fake_root = Path(holder.name)
            shutil.copytree(ROOT / M_B10B_DIR_REL, fake_root / M_B10B_DIR_REL)
            shutil.copytree(ROOT / "datasets/mmwave/manifests/M-B10A_candidate_selection_setup", fake_root / "datasets/mmwave/manifests/M-B10A_candidate_selection_setup")
            shutil.copytree(ROOT / "datasets/mmwave/manifests/a5_subject_split", fake_root / "datasets/mmwave/manifests/a5_subject_split")
            shutil.copytree(ROOT / "datasets/mmwave/manifests/a6_full_conversion", fake_root / "datasets/mmwave/manifests/a6_full_conversion")
            shutil.copytree(ROOT / "datasets/mmwave/manifests/a0_raw_inventory", fake_root / "datasets/mmwave/manifests/a0_raw_inventory")
            for m in MODEL_SPECS[1:]:
                src = ROOT / m["path"]
                dst = fake_root / m["path"]
                dst.parent.mkdir(parents=True, exist_ok=True)
                if src.is_file():
                    shutil.copy2(src, dst)
            contract_path = fake_root / M_B10A_DIR_REL / "locked_test_evaluation_contract.json"
            contract = json.loads(contract_path.read_text())
            contract["metrics_schema"]["primary"] = "accuracy"
            contract_path.write_text(json.dumps(contract))
            gates = _reuse_gates(fake_root)
            self.assertFalse(gates["gates"]["R9_future_contract_unchanged_models_metrics"]["pass"])
        finally:
            holder.cleanup()

    # --- R10 negative test ---

    def test_rejects_pristine_result_limitation_in_r10(self) -> None:
        """R10 must report correct constants; stored evidence must match."""
        holder, dest = _copy_output()
        try:
            # Corrupt stored recovery contract to claim pristine
            rc = json.loads((dest / "proposed_recovery_evaluation_contract.json").read_text())
            rc["required_result_designation"] = "PRISTINE_ONE_TIME_LOCKED_TEST"
            (dest / "proposed_recovery_evaluation_contract.json").write_text(json.dumps(rc, indent=2, sort_keys=True) + "\n")
            _rewrite_checksums(dest)
            with self.assertRaises(validator.MB10R0ValidationError):
                validator.validate_m_b10r0_artifacts(ROOT, output_dir=dest)
        finally:
            holder.cleanup()


if __name__ == "__main__":
    unittest.main(verbosity=2)
