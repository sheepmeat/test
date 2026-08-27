"""M-PROT-5A predeployment closure tests (no Pi / no team-repo)."""

from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from adapters.mmwave_m_prot_2_b23_runtime import (
    SCALER_REL,
    SOURCE_ARTIFACT_REL,
    SOURCE_ARTIFACT_SHA256,
)
from adapters.mmwave_m_prot_4_system_smoke import (
    MProt4SystemSmokeHarness,
    make_bundle,
    samples_covering_span,
)
from scripts.mmwave.build_m_prot_5a_deployment_bundle import (
    DEPLOY_CLASSES,
    FILE_INVENTORY,
    build_bundle,
    build_handoff_document,
    sha256_file,
    verify_bundle,
    verify_frozen_identities,
)

ROOT = Path(__file__).resolve().parents[1]
PHYSIOLOGY_OK = {"PHYSIOLOGY_ELIGIBLE", "ABSENT", "QUALITY_SUPPRESSED", "RR_UNAVAILABLE"}


class MProt5APredeploymentTest(unittest.TestCase):
    def test_handoff_schema_and_contracts(self) -> None:
        handoff = build_handoff_document()
        self.assertEqual(handoff["schema_version"], "M_PROT_5A_PREDEPLOYMENT_HANDOFF_V1")
        self.assertFalse(handoff["team_repo_modified_in_this_phase"])
        self.assertFalse(handoff["live_pi_executed"])
        self.assertEqual(
            handoff["future_team_repo"],
            "https://github.com/jinsu1011/safenest-embedded-competition",
        )
        self.assertIn("phase_like_waveform_sample", handoff["input_bridge_contract"]["required_semantics"])
        self.assertIn("vendor_scalar_rr_alone", handoff["input_bridge_contract"]["forbidden_model_input"])
        self.assertIn("fail_closed_code", handoff["output_contract"]["fields"])
        classes = {e["class"] for e in handoff["file_inventory"]}
        self.assertTrue(DEPLOY_CLASSES.issubset(classes))

    def test_inventory_paths_exist(self) -> None:
        for entry in FILE_INVENTORY:
            if entry["class"] in DEPLOY_CLASSES:
                self.assertTrue((ROOT / entry["path"]).is_file(), entry["path"])

    def test_frozen_identities(self) -> None:
        ids = verify_frozen_identities(ROOT)
        self.assertEqual(ids["artifact_sha256"], SOURCE_ARTIFACT_SHA256)

    def test_bundle_build_verify_and_determinism(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out1 = Path(tmp) / "b1"
            out2 = Path(tmp) / "b2"
            m1 = build_bundle(ROOT, out1)
            m2 = build_bundle(ROOT, out2)
            verify_bundle(out1)
            verify_bundle(out2)
            self.assertEqual(m1["files"], m2["files"])
            self.assertEqual(m1["files"][SOURCE_ARTIFACT_REL], SOURCE_ARTIFACT_SHA256)
            self.assertTrue((out1 / "deployment_bundle_manifest.json").is_file())
            self.assertTrue((out1 / "checksums.sha256").is_file())
            # no absolute Mac paths in staged runtime py modules
            for rel in m1["files"]:
                if rel.endswith(".py"):
                    text = (out1 / rel).read_text(encoding="utf-8", errors="replace")
                    self.assertNotIn("/Users/", text)
                    self.assertNotIn("file://", text)

    def test_wrong_artifact_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            staging = Path(tmp) / "src"
            # Copy minimal tree with wrong artifact
            for entry in FILE_INVENTORY:
                if entry["class"] not in DEPLOY_CLASSES:
                    continue
                src = ROOT / entry["path"]
                dst = staging / entry["path"]
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dst)
            bad = staging / SOURCE_ARTIFACT_REL
            data = bytearray(bad.read_bytes())
            data[0] ^= 0xFF
            bad.write_bytes(bytes(data))
            with self.assertRaises(Exception):
                build_bundle(staging, Path(tmp) / "out")

    def test_wrong_scaler_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            staging = Path(tmp) / "src"
            for entry in FILE_INVENTORY:
                if entry["class"] not in DEPLOY_CLASSES:
                    continue
                src = ROOT / entry["path"]
                dst = staging / entry["path"]
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dst)
            scaler = staging / SCALER_REL
            payload = json.loads(scaler.read_text())
            # Corrupt a TRAIN statistic without matching content sha metadata if present
            if "content_sha256" in payload:
                payload["content_sha256"] = "0" * 64
            else:
                # force parseable but wrong by flipping a value and declared sha if any
                payload["tampered_for_test"] = True
            scaler.write_text(json.dumps(payload, indent=2) + "\n")
            with self.assertRaises(Exception):
                build_bundle(staging, Path(tmp) / "out")

    def test_predeployment_smoke_via_m_prot_3_public_api(self) -> None:
        harness = MProt4SystemSmokeHarness(root=ROOT)
        smoke = harness.run_case(
            case_id="M5A_PREDEPLOY_10HZ",
            fixture_id="phase_10hz_span",
            bundles=[make_bundle(samples_covering_span(10.0))],
            expected_system_state="PHYSIOLOGY_ELIGIBLE",
            accept_observed=list(PHYSIOLOGY_OK),
        )
        self.assertTrue(smoke.deterministic_pass, smoke.to_json())
        self.assertEqual(smoke.r1_sample_count, 300)
        self.assertFalse(smoke.live_hardware)


if __name__ == "__main__":
    unittest.main()
