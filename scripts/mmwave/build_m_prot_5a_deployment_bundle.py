#!/usr/bin/env python3
"""Build/verify the M-PROT-5A portable mmWave predeployment bundle.

Gathers only RUNTIME_REQUIRED / MODEL_REQUIRED / CONFIG_REQUIRED files from the
canonical sheepmeat/test tree, verifies frozen B23/scaler identities, and
stages a portable layout for a future team-repo Pi runtime port (M-PROT-5B).

Does NOT deploy to Pi. Does NOT modify the team repository.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from adapters.mmwave_m_prot_2_b23_runtime import (  # noqa: E402
    CANONICAL_PARAMETER_SHA256,
    SCALER_CONTENT_SHA256,
    SCALER_REL,
    SOURCE_ARTIFACT_REL,
    SOURCE_ARTIFACT_SHA256,
    verify_artifact,
    verify_scaler,
)

PHASE_ID = "M-PROT-5A"
HANDOFF_SCHEMA = "M_PROT_5A_PREDEPLOYMENT_HANDOFF_V1"
BUNDLE_MANIFEST_SCHEMA = "M_PROT_5A_DEPLOYMENT_BUNDLE_MANIFEST_V1"
ABS_PATH_RE = re.compile(r"(/Users/|/home/|[A-Za-z]:\\\\|file://)")

# Classification for future team-repo port (symbolic destinations only).
FILE_INVENTORY: list[dict[str, str]] = [
    {
        "path": "adapters/mmwave_sw01_interface_checker.py",
        "class": "RUNTIME_REQUIRED",
        "role": "PI_RUNTIME_MMWAVE_MODULE",
    },
    {
        "path": "adapters/mmwave_sw01_source.py",
        "class": "RUNTIME_REQUIRED",
        "role": "PI_RUNTIME_MMWAVE_MODULE",
    },
    {
        "path": "adapters/mmwave_r1_sensor_independent_trace.py",
        "class": "RUNTIME_REQUIRED",
        "role": "PI_RUNTIME_MMWAVE_MODULE",
    },
    {
        "path": "adapters/mmwave_r2_representation_features.py",
        "class": "RUNTIME_REQUIRED",
        "role": "PI_RUNTIME_MMWAVE_MODULE",
    },
    {
        "path": "adapters/mmwave_m_prot_2_b23_runtime.py",
        "class": "RUNTIME_REQUIRED",
        "role": "PI_RUNTIME_MMWAVE_MODULE",
    },
    {
        "path": "adapters/mmwave_m_prot_3_integration_runtime.py",
        "class": "RUNTIME_REQUIRED",
        "role": "PI_RUNTIME_MMWAVE_MODULE",
    },
    {
        "path": "scripts/mmwave_m_pv2_candidate_training.py",
        "class": "RUNTIME_REQUIRED",
        "role": "PI_RUNTIME_MMWAVE_MODULE",
        "note": "Imported by M-PROT-2 for TraceModel/_feature_arrays (not for training).",
    },
    {
        "path": SOURCE_ARTIFACT_REL,
        "class": "MODEL_REQUIRED",
        "role": "PI_RUNTIME_MODEL_DIR",
    },
    {
        "path": SCALER_REL,
        "class": "CONFIG_REQUIRED",
        "role": "PI_RUNTIME_CONFIG_DIR",
    },
    {
        "path": "adapters/mmwave_m_prot_4_system_smoke.py",
        "class": "OPTIONAL_DEBUG_TOOL",
        "role": "NOT_FOR_DEPLOYMENT",
    },
    {
        "path": "tests/test_mmwave_m_prot_3_integration_runtime.py",
        "class": "TEST_ONLY",
        "role": "NOT_FOR_DEPLOYMENT",
    },
    {
        "path": "tests/test_mmwave_m_prot_4_system_smoke.py",
        "class": "TEST_ONLY",
        "role": "NOT_FOR_DEPLOYMENT",
    },
    {
        "path": "docs/mmwave/20260827_SafeNest_mmWave_V2_M_PROT_3_Integration_Runtime_Wiring_01.md",
        "class": "DOC_ONLY",
        "role": "NOT_FOR_DEPLOYMENT",
    },
    {
        "path": "docs/mmwave/20260827_SafeNest_mmWave_V2_M_PROT_4_System_Smoke_01.md",
        "class": "DOC_ONLY",
        "role": "NOT_FOR_DEPLOYMENT",
    },
]

DEPLOY_CLASSES = {"RUNTIME_REQUIRED", "MODEL_REQUIRED", "CONFIG_REQUIRED"}

PYTHON_DEPS = {
    "python": ">=3.9",
    "numpy": "required",
    "scipy": "required (R1 resample_poly / R2 welch)",
    "torch": "required for frozen PYTORCH_FLOAT32_STATE_DICT B23; Pi install NOT live verified",
    "scikit-learn": "imported by training-script module used at runtime; keep available",
}

MUST_NOT_REPLACE = [
    SOURCE_ARTIFACT_REL,
    SCALER_REL,
    "adapters/mmwave_m_prot_2_b23_runtime.py",
    "adapters/mmwave_m_prot_3_integration_runtime.py",
    "adapters/mmwave_r1_sensor_independent_trace.py",
]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def required_entries() -> list[dict[str, str]]:
    return [e for e in FILE_INVENTORY if e["class"] in DEPLOY_CLASSES]


def verify_frozen_identities(root: Path) -> dict[str, Any]:
    verify_artifact(root)
    verify_scaler(root)
    art = root / SOURCE_ARTIFACT_REL
    scaler = root / SCALER_REL
    return {
        "artifact_path": SOURCE_ARTIFACT_REL,
        "artifact_sha256": sha256_file(art),
        "artifact_sha256_expected": SOURCE_ARTIFACT_SHA256,
        "parameter_sha256": CANONICAL_PARAMETER_SHA256,
        "scaler_path": SCALER_REL,
        "scaler_file_sha256": sha256_file(scaler),
        "scaler_content_sha256_expected": SCALER_CONTENT_SHA256,
    }


def reject_absolute_paths(root: Path, rel_paths: list[str]) -> None:
    for rel in rel_paths:
        text = (root / rel).read_text(encoding="utf-8", errors="replace")
        # Allow docs that mention /home as historical Pi notes only in DOC_ONLY;
        # required runtime modules must not embed machine-local absolute paths.
        if ABS_PATH_RE.search(text):
            # scripts/mmwave_m_pv2_candidate_training may mention paths in comments;
            # fail only on file:// or Mac /Users leakage in required files.
            if "/Users/" in text or "file://" in text or re.search(r"[A-Za-z]:\\\\", text):
                raise RuntimeError(f"absolute_path_leakage:{rel}")


def build_handoff_document() -> dict[str, Any]:
    return {
        "schema_version": HANDOFF_SCHEMA,
        "phase": PHASE_ID,
        "primary_goal": "PROTOTYPE_SOFTWARE_INTEGRATION",
        "test_repo": "https://github.com/sheepmeat/test.git",
        "future_team_repo": "https://github.com/jinsu1011/safenest-embedded-competition",
        "team_repo_modified_in_this_phase": False,
        "pi_runtime_subtree_assumed": False,
        "live_pi_executed": False,
        "model": {
            "panel_id": "B23",
            "candidate_id": "M-PV2_FAMILY_B_TRACE_TCN_BREATHING_RR_QUALITY",
            "artifact": SOURCE_ARTIFACT_REL,
            "artifact_sha256": SOURCE_ARTIFACT_SHA256,
            "parameter_sha256": CANONICAL_PARAMETER_SHA256,
            "representation": "PYTORCH_FLOAT32_STATE_DICT",
        },
        "scaler": {
            "path": SCALER_REL,
            "content_sha256": SCALER_CONTENT_SHA256,
            "policy": "TRAIN_FITTED_APPLY_ONCE_NO_REFIT",
        },
        "window": {
            "duration_s_conceptual": 30,
            "target_span_s": 29.9,
            "target_rate_hz": 10,
            "r1_samples": 300,
            "assembled_dim": 621,
            "readiness_basis": "CAUSAL_TIME_COVERAGE",
            "r1_owns_resampling": True,
        },
        "modules": {
            "sw01": [
                "adapters/mmwave_sw01_interface_checker.py",
                "adapters/mmwave_sw01_source.py",
            ],
            "r1": ["adapters/mmwave_r1_sensor_independent_trace.py"],
            "r2": ["adapters/mmwave_r2_representation_features.py"],
            "m_prot_2": ["adapters/mmwave_m_prot_2_b23_runtime.py"],
            "m_prot_3": ["adapters/mmwave_m_prot_3_integration_runtime.py"],
            "runtime_support_script": ["scripts/mmwave_m_pv2_candidate_training.py"],
        },
        "python_dependencies": PYTHON_DEPS,
        "input_bridge_contract": {
            "required_semantics": [
                "phase_like_waveform_sample",
                "monotonic_timestamp",
            ],
            "preferred_continuity": ["sequence", "session_identity", "reset_indication"],
            "source_identity": [
                "device_identity",
                "interface_identity",
                "configuration_identity",
                "observation_kind",
            ],
            "presence": "explicit_defensible_presence_source_if_available",
            "forbidden_model_input": ["vendor_scalar_rr_alone"],
            "transport_field_names": "NOT_FROZEN_IN_5A; semantic requirements only",
        },
        "output_contract": {
            "fields": [
                "status_or_availability",
                "window_ready",
                "breathing_state_or_score",
                "rr_bpm_or_unavailable",
                "quality_state_or_score",
                "fail_closed_code",
                "model_identity",
                "timestamp_or_update_identity",
            ],
            "team_ui_backend_mapping": "DEFERRED_TO_M_PROT_5B",
        },
        "fail_closed_states_examples": [
            "SW01_ADMISSION_REQUIRED",
            "SOURCE_VALIDATION_FAILED",
            "WINDOW_NOT_READY",
            "PRESENCE_UNAVAILABLE",
            "R1_*",
            "R1_SAMPLE_COUNT_MISMATCH",
            "QUALITY_SUPPRESSED",
            "RR_UNAVAILABLE",
            "UNAVAILABLE_INVALID_DECODE",
        ],
        "file_inventory": FILE_INVENTORY,
        "must_not_replace": MUST_NOT_REPLACE,
        "symbolic_destinations": [
            "PI_RUNTIME_MMWAVE_MODULE",
            "PI_RUNTIME_MODEL_DIR",
            "PI_RUNTIME_CONFIG_DIR",
        ],
        "future_team_repo_handoff": {
            "inspect_first": "https://github.com/jinsu1011/safenest-embedded-competition",
            "locate": "CURRENT Pi-side runtime subtree (do not assume old folder names)",
            "deploy_model": "team Pi subtree → clone/place on Pi → execute runtime inside subtree",
            "integrate": "insert frozen mmWave prototype components from this handoff; do not copy whole sheepmeat/test",
            "yuname_integration_repo": "HISTORICAL_EVIDENCE_ONLY_NOT_FINAL_TARGET",
        },
    }


def build_bundle(root: Path, out_dir: Path) -> dict[str, Any]:
    identities = verify_frozen_identities(root)
    entries = required_entries()
    rels = [e["path"] for e in entries]
    for rel in rels:
        src = root / rel
        if not src.is_file():
            raise FileNotFoundError(rel)
    reject_absolute_paths(root, rels)

    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True)

    file_checksums: dict[str, str] = {}
    for entry in entries:
        rel = entry["path"]
        src = root / rel
        dst = out_dir / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        digest = sha256_file(dst)
        file_checksums[rel] = digest
        # Identity gates for frozen artifacts
        if rel == SOURCE_ARTIFACT_REL and digest != SOURCE_ARTIFACT_SHA256:
            raise RuntimeError("artifact_sha_mismatch_in_bundle")
        if rel == SCALER_REL:
            # content sha verified via verify_scaler already; keep file sha recorded
            pass

    manifest = {
        "schema_version": BUNDLE_MANIFEST_SCHEMA,
        "phase": PHASE_ID,
        "source_root_policy": "canonical_sheepmeat_test_relative_paths",
        "identities": identities,
        "files": file_checksums,
        "inventory": entries,
        "live_hardware": False,
        "team_repo_modified": False,
    }
    (out_dir / "deployment_bundle_manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    checksum_lines = [f"{digest}  {rel}" for rel, digest in sorted(file_checksums.items())]
    (out_dir / "checksums.sha256").write_text("\n".join(checksum_lines) + "\n", encoding="utf-8")
    return manifest


def verify_bundle(out_dir: Path) -> dict[str, Any]:
    manifest_path = out_dir / "deployment_bundle_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    files = manifest["files"]
    for rel, expected in files.items():
        got = sha256_file(out_dir / rel)
        if got != expected:
            raise RuntimeError(f"bundle_checksum_mismatch:{rel}")
    art = sha256_file(out_dir / SOURCE_ARTIFACT_REL)
    if art != SOURCE_ARTIFACT_SHA256:
        raise RuntimeError("bundle_artifact_sha_mismatch")
    # Re-verify scaler content semantics using staged tree as root
    verify_scaler(out_dir)
    return {"ok": True, "file_count": len(files), "artifact_sha256": art}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("/tmp/m_prot_5a_deployment_bundle"),
        help="staging output directory (not committed)",
    )
    parser.add_argument("--handoff-out", type=Path, default=None)
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args(argv)
    root = args.root.resolve()

    if args.handoff_out is not None:
        handoff = build_handoff_document()
        args.handoff_out.parent.mkdir(parents=True, exist_ok=True)
        args.handoff_out.write_text(json.dumps(handoff, indent=2) + "\n", encoding="utf-8")

    if args.verify_only:
        result = verify_bundle(args.out)
        print(json.dumps(result, indent=2))
        return 0

    manifest = build_bundle(root, args.out.resolve())
    verify_bundle(args.out.resolve())
    print(json.dumps({"built": True, "out": str(args.out), "files": len(manifest["files"])}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
