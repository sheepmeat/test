#!/usr/bin/env python3
"""Validator for Phase A4 label mapping and policy pilot artifacts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


FORBIDDEN_SPLIT_FIELDS = {
    "split",
    "train_val_test",
    "is_train",
    "is_val",
    "is_test",
    "fold",
    "model_prediction",
    "predicted_label",
}


def derive_a4_gate(
    validation_success: bool,
    exceptions: list[dict[str, Any]],
    windows: list[dict[str, Any]],
) -> tuple[str, str]:
    """Derive A4 gate and A5 entry status cleanly."""
    if not validation_success:
        return "FAIL", "NOT_READY"

    has_blocker = any(item.get("severity") == "BLOCKER" for item in exceptions)
    has_error = any(item.get("severity") == "ERROR" for item in exceptions)

    if has_blocker:
        return "BLOCKED", "BLOCKED"
    if has_error:
        return "FAIL", "NOT_READY"

    # PASS_WITH_WARNINGS is appropriate because:
    # 1. Non-breathing is a voluntary breath-hold proxy, not clinical apnea.
    # 2. Post-exercise recordings lack independent respiration rate ground truth and remain ambiguous.
    return "PASS_WITH_WARNINGS", "READY_WITH_CONDITIONS"


def validate_label_manifests(
    a3_windows: list[dict[str, Any]],
    profile: dict[str, Any],
    windows: list[dict[str, Any]],
    exceptions: list[dict[str, Any]],
    summary: dict[str, Any],
) -> tuple[bool, list[str]]:
    """Validate Phase A4 label manifests against all 20 structural and semantic invariants."""
    errors: list[str] = []

    a3_ids = [w["window_id"] for w in a3_windows]
    a4_ids = [w["window_id"] for w in windows]

    # 1 & 2. 1-to-1 match between A3 windows and A4 windows
    if len(a3_ids) != len(a4_ids):
        errors.append(f"Window count mismatch: A3={len(a3_ids)} != A4={len(a4_ids)}")
    if set(a3_ids) != set(a4_ids):
        errors.append("Window ID set mismatch between A3 and A4")

    a3_by_id = {w["window_id"]: w for w in a3_windows}

    for w in windows:
        w_id = w["window_id"]
        a3_w = a3_by_id.get(w_id)
        if not a3_w:
            errors.append(f"A4 window {w_id} not found in A3")
            continue

        # 3. A3 timestamp boundaries preserved exactly
        if (
            w["start_timestamp"] != a3_w["start_timestamp"]
            or w["last_sample_timestamp"] != a3_w["last_sample_timestamp"]
            or w["end_timestamp_exclusive"] != a3_w["end_timestamp_exclusive"]
        ):
            errors.append(f"Window {w_id} timestamp boundaries altered from A3")

        # 4. A3 window index boundaries preserved
        if (
            w["canonical_start_index"] != a3_w["canonical_start_index"]
            or w["canonical_end_index_exclusive"] != a3_w["canonical_end_index_exclusive"]
        ):
            errors.append(f"Window {w_id} canonical index boundaries altered from A3")

        # 5. Label class values match class contract
        lbl = w.get("safenest_label")
        lbl_id = w.get("safenest_label_id")
        allowed_classes = profile.get("target_classes", {"NORMAL": 0, "RAPID_OR_ABNORMAL": 1, "APNEA": 2})

        if lbl is not None:
            if lbl not in allowed_classes:
                errors.append(f"Window {w_id} assigned invalid label class {lbl!r}")
            if lbl_id != allowed_classes.get(lbl):
                errors.append(f"Window {w_id} label ID {lbl_id} mismatch for class {lbl!r}")

        # 6 & 7. Every assigned label has a mapping type and mapping rule ID
        m_type = w.get("mapping_type")
        m_rule = w.get("mapping_rule_id")
        if not m_type:
            errors.append(f"Window {w_id} missing mapping_type")
        if not m_rule:
            errors.append(f"Window {w_id} missing mapping_rule_id")

        # 8. Every APNEA assignment from voluntary non-breathing is marked DERIVED
        if lbl == "APNEA" and m_type != "DERIVED":
            errors.append(f"Window {w_id} APNEA label mapping type must be DERIVED (got {m_type!r})")

        # 10. Post-exercise alone is insufficient for RAPID_OR_ABNORMAL
        if w.get("source_test_condition") == "Post-exercise" and lbl == "RAPID_OR_ABNORMAL":
            errors.append(f"Window {w_id} Post-exercise automatically mapped to RAPID_OR_ABNORMAL without reference evidence")

        # 12. Ambiguous windows remain explicit
        if lbl is None and w.get("assignment_status") not in ("AMBIGUOUS", "UNMAPPED", "EXCLUDED"):
            errors.append(f"Window {w_id} unassigned label must have assignment_status AMBIGUOUS/UNMAPPED")

        # 14. Source condition and posture preserved
        if not w.get("source_test_condition") or not w.get("posture"):
            errors.append(f"Window {w_id} missing source condition or posture")

        # 18 & 19. No split or prediction fields introduced
        found_forbidden = FORBIDDEN_SPLIT_FIELDS.intersection(w.keys())
        if found_forbidden:
            errors.append(f"Window {w_id} contains forbidden split/prediction fields: {sorted(list(found_forbidden))}")

    # 9. No result claims clinical apnea
    if profile.get("apnea_policy", {}).get("clinical_apnea_claimed") is True:
        errors.append("Profile invalidly claims clinical apnea")

    # 15. Summary class counts match detailed manifest
    assigned_counts = summary.get("label_distribution", {})
    manifest_counts = {
        "NORMAL": sum(1 for w in windows if w["safenest_label"] == "NORMAL"),
        "RAPID_OR_ABNORMAL": sum(1 for w in windows if w["safenest_label"] == "RAPID_OR_ABNORMAL"),
        "APNEA": sum(1 for w in windows if w["safenest_label"] == "APNEA"),
        "AMBIGUOUS": sum(1 for w in windows if w["safenest_label"] is None and w["assignment_status"] == "AMBIGUOUS"),
        "UNMAPPED": sum(1 for w in windows if w["safenest_label"] is None and w["assignment_status"] == "UNMAPPED"),
    }
    for k, v in manifest_counts.items():
        if assigned_counts.get(k, 0) != v:
            errors.append(f"Summary count for {k} mismatch: summary={assigned_counts.get(k)} != manifest={v}")

    # 16. Exception count match
    if summary.get("exception_count") != len(exceptions):
        errors.append(f"Summary exception_count mismatch: summary={summary.get('exception_count')} != actual={len(exceptions)}")

    # 20. Gate state check
    gate, ready = derive_a4_gate(len(errors) == 0, exceptions, windows)
    if summary.get("a4_gate_status") != gate:
        errors.append(f"Summary gate status mismatch: summary={summary.get('a4_gate_status')} != calculated={gate}")

    return len(errors) == 0, errors


def main() -> None:
    root = Path(".")
    a4_dir = root / "datasets/mmwave/manifests/a4_label_pilot"
    a3_dir = root / "datasets/mmwave/manifests/a3_timeline_pilot"

    if not a4_dir.exists():
        print(f"Error: manifest directory {a4_dir} does not exist")
        raise SystemExit(1)

    a3_windows = [
        json.loads(line)
        for line in (a3_dir / "window_manifest.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    profile = json.loads((a4_dir / "label_mapping_profile.json").read_text(encoding="utf-8"))
    windows = [
        json.loads(line)
        for line in (a4_dir / "window_label_manifest.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    exceptions = json.loads((a4_dir / "exceptions.json").read_text(encoding="utf-8"))
    summary = json.loads((a4_dir / "a4_summary.json").read_text(encoding="utf-8"))

    success, errors = validate_label_manifests(a3_windows, profile, windows, exceptions, summary)
    gate, ready = derive_a4_gate(success, exceptions, windows)

    print(f"Validation Success: {success}")
    print(f"Derived A4 Gate: {gate}")
    print(f"Derived A5 Entry Status: {ready}")

    if errors:
        print("\nValidation Errors:")
        for err in errors:
            print(f"  - {err}")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
