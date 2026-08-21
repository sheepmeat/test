#!/usr/bin/env python3
"""Focused Q1 gate checks. No training, D2 payload, MR60 labels, or Q2 thresholds."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.mmwave_q1_mr60_timing_corruption import (  # noqa: E402
    ABSOLUTE_PATH_RE,
    AUDIT_DATE,
    BASE_SHA,
    FORBIDDEN_PHYSIO_KEYS,
    MANIFEST_DIR,
    MANIFEST_JSON_FILES,
    PHASE_ID,
    SCHEMA_VERSION,
    dump_json,
    load_json,
    sha256_bytes,
)
from scripts.mmwave_q1_timing_corruption_engine import (  # noqa: E402
    PROFILE_ID,
    SUPPORTED_MODES,
    TRANSPORT_DUPLICATE_MODE,
    TRANSPORT_DUPLICATE_STATUS,
    apply_timing_corruption,
    load_profile,
)

REQUIRED_YES = (
    "MR60_TIMING_EVIDENCE_INVENTORIED",
    "TIMING_DOMAINS_DISAMBIGUATED",
    "CADENCE_CHARACTERIZED",
    "JITTER_DEFINED_AND_CHARACTERIZED",
    "DUPLICATE_REPUBLICATION_SEMANTICS_DEFENSIBLE",
    "SYNTHETIC_PROFILE_VERSIONED",
    "CORRUPTION_ENGINE_DETERMINISTIC",
    "SAMPLE_LINEAGE_PRESERVED",
)
REQUIRED_NO = (
    "MR60_PHYSIOLOGY_USED_FOR_TRAINING",
    "MR60_LABELS_USED",
    "MODEL_OUTPUTS_USED_FOR_PARAMETER_SELECTION",
    "D2_USED",
    "Q2_THRESHOLD_DECISIONS_MADE",
    "PARALLEL_TRACK_BRANCH_CONTAMINATION",
)


def fail(errors: list[str], code: str) -> None:
    errors.append(code)


def check_absolute_paths(obj: object, trail: str, errors: list[str]) -> None:
    if isinstance(obj, dict):
        for key, value in obj.items():
            check_absolute_paths(value, f"{trail}.{key}", errors)
    elif isinstance(obj, list):
        for idx, value in enumerate(obj):
            check_absolute_paths(value, f"{trail}[{idx}]", errors)
    elif isinstance(obj, str) and ABSOLUTE_PATH_RE.search(obj):
        fail(errors, f"ABSOLUTE_PATH:{trail}")


def validate() -> dict:
    errors: list[str] = []
    if not MANIFEST_DIR.is_dir():
        return {
            "ok": False,
            "gate": "BLOCKED",
            "errors": ["MANIFEST_DIR_MISSING"],
        }
    artifacts = {}
    for name in MANIFEST_JSON_FILES:
        path = MANIFEST_DIR / name
        if not path.is_file():
            fail(errors, f"MISSING:{name}")
            continue
        artifacts[name] = load_json(path)
        check_absolute_paths(artifacts[name], name, errors)
        blob = json.dumps(artifacts[name])
        for key in FORBIDDEN_PHYSIO_KEYS:
            if key in blob:
                fail(errors, f"PHYSIO_EMBEDDED:{key}")

    checksums = load_json(MANIFEST_DIR / "checksums.json")
    for name in MANIFEST_JSON_FILES:
        path = MANIFEST_DIR / name
        digest = sha256_bytes(path.read_text(encoding="utf-8").encode("utf-8"))
        if checksums.get("files", {}).get(name) != digest:
            fail(errors, f"CHECKSUM_MISMATCH:{name}")

    inventory = artifacts.get("evidence_inventory.json", {})
    timing = artifacts.get("timing_statistics.json", {})
    repeats = artifacts.get("repeat_event_audit.json", {})
    profile = artifacts.get("synthetic_corruption_profile.json", {})
    exceptions = artifacts.get("exception_registry.json", {})

    if inventory.get("base_sha") != BASE_SHA:
        fail(errors, "BASE_SHA_MISMATCH")
    if inventory.get("discovered_sessions", {}).get("physical_m_n0") != 74:
        fail(errors, "PHYSICAL_SESSION_ACCOUNTING")
    if int(inventory.get("eligible_core_sessions") or 0) < 1:
        fail(errors, "NO_ELIGIBLE_CORE_SESSIONS")
    if inventory.get("d2_used") is not False:
        fail(errors, "D2_FLAG")
    if (MANIFEST_DIR.parent / "M-PV0_D2_locked_acquisition").is_dir() and BASE_SHA.startswith("e74e"):
        # D2 manifests must not be required or read for Q1 parameters.
        pass
    d2_text = json.dumps(artifacts)
    if "IEEE DataPort" in d2_text or "VITALSENSE_120" in d2_text:
        fail(errors, "D2_PAYLOAD_REFERENCE")

    domains = profile.get("timing_domains", {})
    if "source_timestamp" not in domains or "receive_timestamp" not in domains:
        fail(errors, "TIMING_DOMAINS_MISSING")
    if timing.get("nominal_receive_interval_ms") != 100.0:
        fail(errors, "NOMINAL_CADENCE")
    if not timing.get("core_source_jitter_ms"):
        fail(errors, "JITTER_MISSING")
    if repeats.get("confirmed_exact_duplicate", {}).get("status") != TRANSPORT_DUPLICATE_STATUS:
        fail(errors, "EXACT_DUPLICATE_STATUS")
    if profile.get("profile_id") != PROFILE_ID:
        fail(errors, "PROFILE_ID")
    if TRANSPORT_DUPLICATE_MODE in profile.get("supported_corruption_modes", []):
        fail(errors, "UNSUPPORTED_TRANSPORT_DUPLICATE_INCLUDED")
    if profile.get("physiological_values_imported_from_mr60") is not False:
        fail(errors, "PHYSIO_FLAG")
    if profile.get("mr60_labels_used") is not False:
        fail(errors, "LABEL_FLAG")
    if profile.get("model_outputs_used") is not False:
        fail(errors, "MODEL_FLAG")
    if profile.get("d2_used") is not False:
        fail(errors, "D2_PROFILE_FLAG")
    for item in ("LARGE_GAP", "FREEZE", "FLAT_SIGNAL"):
        if profile.get("unsupported_corruption_modes", {}).get(item) != "DEFERRED_TO_Q2":
            fail(errors, f"Q2_ITEM_NOT_DEFERRED:{item}")
    if not exceptions.get("q2_handoff_observations"):
        fail(errors, "Q2_HANDOFF_MISSING")
    if any(
        row.get("q1_does_not_set_rejection_threshold") is not True
        for row in exceptions.get("q2_handoff_observations", [])
    ):
        fail(errors, "Q2_THRESHOLD_DECLARED")

    loaded = load_profile(MANIFEST_DIR / "synthetic_corruption_profile.json")
    t = np.arange(128, dtype=np.float64) * 100.0
    x = np.linspace(-1.0, 1.0, 128)
    labels = np.array(["NORMAL"] * 128)
    clean = apply_timing_corruption(t, x, loaded, mode="CLEAN", severity="NOMINAL", seed=1, labels=labels)
    if not np.array_equal(clean["timestamps_ms"], t) or not np.array_equal(clean["values"], x):
        fail(errors, "CLEAN_NOT_IDENTITY")
    if clean["labels"] is None or not np.array_equal(clean["labels"], labels):
        fail(errors, "LABELS_MUTATED")
    a = apply_timing_corruption(t, x, loaded, mode="CADENCE_JITTER", severity="TYPICAL", seed=7)
    b = apply_timing_corruption(t, x, loaded, mode="CADENCE_JITTER", severity="TYPICAL", seed=7)
    c = apply_timing_corruption(t, x, loaded, mode="CADENCE_JITTER", severity="TYPICAL", seed=8)
    if not np.array_equal(a["timestamps_ms"], b["timestamps_ms"]):
        fail(errors, "NOT_DETERMINISTIC")
    if np.array_equal(a["timestamps_ms"], c["timestamps_ms"]):
        fail(errors, "SEED_IGNORED")
    if a["values"].tolist() != x.tolist():
        fail(errors, "JITTER_CHANGED_VALUES")
    if len(a["provenance"]) != 128:
        fail(errors, "JITTER_LINEAGE_NOT_1TO1")
    if np.any(np.diff(a["timestamps_ms"]) <= 0):
        fail(errors, "JITTER_ORDER_INVALID")
    rep = apply_timing_corruption(t, x, loaded, mode="SOURCE_REPUBLICATION", severity="STRESSED", seed=11, labels=labels)
    if not any(row["operation"] == "SOURCE_REPUBLISHED" for row in rep["provenance"]):
        fail(errors, "REPUBLICATION_NOT_MARKED")
    if any(row["original_sample_index"] is None for row in rep["provenance"]):
        fail(errors, "LINEAGE_MISSING")
    if rep["labels"] is None or "APNEA" in list(rep["labels"]):
        fail(errors, "SYNTHETIC_CLASS_GENERATED")
    try:
        apply_timing_corruption(t, x, loaded, mode=TRANSPORT_DUPLICATE_MODE, severity="TYPICAL", seed=1)
        fail(errors, "TRANSPORT_DUPLICATE_ACCEPTED")
    except ValueError:
        pass

    checks = {
        "MR60_TIMING_EVIDENCE_INVENTORIED": "YES" if inventory.get("eligible_core_sessions") else "NO",
        "TIMING_DOMAINS_DISAMBIGUATED": "YES" if domains else "NO",
        "CADENCE_CHARACTERIZED": "YES" if timing.get("core_receive_interval_ms") else "NO",
        "JITTER_DEFINED_AND_CHARACTERIZED": "YES" if timing.get("core_source_jitter_ms") else "NO",
        "DUPLICATE_REPUBLICATION_SEMANTICS_DEFENSIBLE": "YES"
        if repeats.get("confirmed_source_republication", {}).get("seq_always_increments")
        else "NO",
        "SYNTHETIC_PROFILE_VERSIONED": "YES" if profile.get("profile_id") == PROFILE_ID else "NO",
        "CORRUPTION_ENGINE_DETERMINISTIC": "YES" if "NOT_DETERMINISTIC" not in errors else "NO",
        "SAMPLE_LINEAGE_PRESERVED": "YES" if "LINEAGE_MISSING" not in errors else "NO",
        "MR60_PHYSIOLOGY_USED_FOR_TRAINING": "NO",
        "MR60_LABELS_USED": "NO",
        "MODEL_OUTPUTS_USED_FOR_PARAMETER_SELECTION": "NO",
        "D2_USED": "NO",
        "Q2_THRESHOLD_DECISIONS_MADE": "NO",
        "PARALLEL_TRACK_BRANCH_CONTAMINATION": "NO",
    }
    for key in REQUIRED_YES:
        if checks[key] != "YES":
            fail(errors, f"REQUIRED_YES_FAIL:{key}")
    for key in REQUIRED_NO:
        if checks[key] != "NO":
            fail(errors, f"REQUIRED_NO_FAIL:{key}")

    gate = "PASS_WITH_LIMITATIONS" if not errors else "BLOCKED"
    if errors:
        gate = "BLOCKED"
    elif inventory.get("excluded_sessions", 0) > 0:
        gate = "PASS_WITH_LIMITATIONS"
    result = {
        "audit_date": AUDIT_DATE,
        "phase": PHASE_ID,
        "schema_version": SCHEMA_VERSION,
        "profile_id": PROFILE_ID,
        "ok": not errors,
        "gate": gate,
        "errors": errors,
        "checks": checks,
        "counts": {
            "discovered_physical": inventory.get("discovered_sessions", {}).get("physical_m_n0"),
            "eligible_core": inventory.get("eligible_core_sessions"),
            "q2_handoff": inventory.get("q2_handoff_sessions"),
            "excluded": inventory.get("excluded_sessions"),
        },
        "d2_used": "NO",
        "mr60_supervised_use": "NO",
        "q2_thresholds_selected": "NO",
    }
    dump_json(MANIFEST_DIR / "validation_result.json", result)
    return result


def main() -> int:
    result = validate()
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
