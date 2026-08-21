#!/usr/bin/env python3
"""M-PV0: freeze public source roles, V1 baseline, and D2 lock.

Metadata/governance only. No training, adapter implementation, D2 payload
download, D2 semantic inspection, or V2 split generation.
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

PHASE_ID = "M-PV0"
SCHEMA_VERSION = "M-PV0.1"
REGISTRY_ID = "MMWAVE_M_PV0_PUBLIC_MULTIDOMAIN_REGISTRY_V1"
AUDIT_DATE = "2026-08-22"
REGISTRY_DIR = ROOT / "datasets/mmwave/manifests/M-PV0_public_multidomain_registry"
BASE_SHA_MEANING = "origin/main at M-PV0 freeze; no unmerged parallel-track ancestry"

FLOAT_PATH = ROOT / "models/mmwave/m_n6/MMWAVE_M_N6_SELECTED_FLOAT_V1.keras"
INT8_PATH = ROOT / "models/mmwave/m_n9/MMWAVE_M_N9_FULL_INT8_V1.tflite"
MN9_LOCK = ROOT / "config/mmwave/m_n9_full_int8_artifact_lock.json"
MN9_RESULT = ROOT / "datasets/mmwave/manifests/m_n9_full_int8_result.json"
MN6_LOCK = ROOT / "config/mmwave/m_n6_selected_candidate_lock.json"
MN6_HELDOUT = ROOT / "datasets/mmwave/manifests/m_n6_heldout_result.json"
MN7_RESULT = ROOT / "datasets/mmwave/manifests/m_n7_device_domain_result.json"
MN4_CONTRACT = ROOT / "config/mmwave/m_n4_canonical_input_dataset_contract.json"
MN4_SPLIT = ROOT / "datasets/mmwave/splits/mmwave_mr60_compat_subject_split_v1.json"
MN4_SUMMARY = ROOT / "datasets/mmwave/manifests/m_n4_canonical/split_structural_summary.json"
A0_IDENTITY = ROOT / "datasets/mmwave/manifests/a0_raw_inventory/source_identity.json"
A5_SPLIT = ROOT / "datasets/mmwave/splits/mmwave_real_subject_split_v1.json"
DATASETS_MANIFEST = ROOT / "datasets/MANIFEST.json"
MODEL_MANIFEST = ROOT / "models/model_manifest.json"
V2_ROADMAP = ROOT / "docs/20260822_SafeNest_mmWave_Public_Multidomain_V2_Development_Roadmap_01.md"
MN_ROADMAP = ROOT / "docs/20260817_SafeNest_mmWave_MR60_Compatible_Model_Development_Roadmap_01.md"

REGISTRY_JSON_FILES = (
    "source_registry.json",
    "role_lock_policy.json",
    "license_access_audit.json",
    "v1_failure_baseline.json",
    "exception_registry.json",
)

ABSOLUTE_PATH_RE = re.compile(
    r"(?:/Users/|file://|~(?:/|$)|[A-Za-z]:\\|/home/|/private/tmp/)"
)

# Public landing-page metadata frozen during M-PV0. Values are not guessed
# beyond what the cited public pages/APIs returned on 2026-08-22.
PUBLIC_METADATA_AUDIT = {
    "D0": {
        "concept_record_id": "16760683",
        "concept_doi": "10.5281/zenodo.16760683",
        "roadmap_cited_record_id": "16760684",
        "roadmap_cited_doi": "10.5281/zenodo.16760684",
        "roadmap_cited_version": "1.0",
        "roadmap_cited_publication_date": "2025-08-07",
        "canonical_record_id": "18599983",
        "canonical_doi": "10.5281/zenodo.18599983",
        "canonical_version": "1.1",
        "canonical_publication_date": "2026-02-10",
        "same_concept": True,
        "official_db_records_zip_bytes": 245284102,
        "official_db_records_zip_md5": "408c5b347c751c553abe6d0f640a6f98",
        "license": "CC-BY-4.0",
        "access_right": "open",
        "title": "Extensive Age-Balanced and Subject-Varied mmWave Radar Dataset of Referenced Records for Vital Signs",
        "radar_frequency": "60 GHz-class FMCW",
        "radar_hardware": [
            "NodeNs IWR6843ISK (lying)",
            "Texas Instruments IWR6843ISK-ODS (sitting)",
        ],
        "metadata_urls": [
            "https://zenodo.org/api/records/18599983",
            "https://zenodo.org/api/records/16760684",
            "https://zenodo.org/records/18599983",
            "https://zenodo.org/records/16760684",
        ],
    },
    "D1": {
        "publication_doi": "10.1038/s41597-020-0390-1",
        "publication_title": "A dataset of radar-recorded heart sounds and vital signs including synchronised reference sensor signals",
        "publication_license": "CC-BY-4.0",
        "collection_doi": "10.6084/m9.figshare.c.4633958.v1",
        "article_doi": "10.6084/m9.figshare.9691544.v1",
        "dataset_title": "A dataset of radar-recorded heart sounds and vital signs including synchronised reference sensor signals",
        "publisher_or_host": "figshare / Scientific Data",
        "license": "CC BY 4.0",
        "access_mode": "OPEN_PUBLIC_DOWNLOAD",
        "expected_download_size_bytes": 583572264,
        "checksum_source": "figshare article 9691544 file datasets_scidata_vsmdb.zip computed_md5",
        "payload_md5": "801c13ae6daef54584ee4ba8fbabed19",
        "payload_filename": "datasets_scidata_vsmdb.zip",
        "radar_frequency": "24.17 GHz",
        "radar_hardware": "Six-Port continuous-wave radar",
        "raw_signal_type": "Six-Port I/Q baseband (B3-B6) digitized at 2000 Hz",
        "processed_signal_type": "phase/displacement reconstructable from I/Q; not pre-adapted in M-PV0",
        "subject_count": 11,
        "recording_duration_claim": "13376 s / ~223 minutes",
        "conditions": [
            "default",
            "breath-hold/apnea",
            "post-exercise",
            "distance variation",
            "angle variation",
            "speech",
            "carotid",
            "back",
        ],
        "metadata_urls": [
            "https://www.nature.com/articles/s41597-020-0390-1",
            "https://doi.org/10.1038/s41597-020-0390-1",
            "https://api.figshare.com/v2/collections/4633958",
            "https://api.figshare.com/v2/articles/9691544",
        ],
    },
    "D2": {
        "publication_doi": "10.1038/s41597-026-07016-6",
        "publication_title": "A dataset of 120 GHz millimeter-wave radar vital signals with synchronized reference recordings",
        "publication_license": "CC-BY-4.0",
        "dataset_doi": "10.21227/wq68-sv85",
        "ieee_dataport_title": "A New Dataset for Millimeter-Wave Radar Vital Sensing With Reference Signals",
        "ieee_dataport_url": "https://ieee-dataport.org/open-access/new-dataset-millimeter-wave-radar-vital-sensing-reference-signals",
        "github_companion": "https://github.com/Rc-W024/VS_DATASET",
        "github_code_license": "MIT",
        "access_mode": "IEEE_DATAPORT_OPEN_ACCESS_LOGIN_REQUIRED",
        "announced_zip_name": "VITALSENSE_120_DATASET.zip",
        "announced_ieee_size": "28.69 MB",
        "announced_github_size": "about 31 MB",
        "checksum_source": "NOT_PUBLISHED_ON_AUDITED_LANDING_PAGES",
        "payload_sha256": None,
        "radar_frequency": "120 GHz (122-123 GHz ISM; paper also notes 3 GHz bandwidth used)",
        "radar_hardware": "CommSensLab-UPC custom 120 GHz FMCW RSoC (Indie transceiver)",
        "raw_signal_type": "processed radar displacement in .mat (VitalSig, millimetres); raw ADC not the published payload",
        "processed_signal_type": "radar displacement / vital signal in VS##_Resting.mat and VS##_Apnea.mat",
        "subject_count": 24,
        "recording_count_claim": "48 radar files + 48 Mindray reference files (4 files x 24 subjects)",
        "duration_claim": "5760 seconds total; 2 minutes per scenario; 4 minutes per subject",
        "conditions": ["Resting", "Apnea (instructed inhale-and-hold transitions)"],
        "breath_hold_protocol": "40 s rest, then inhale and hold 10-20 s, exhale and breathe 15-20 s, another 10 s apnea, then rest to end of 2 min",
        "metadata_urls": [
            "https://doi.org/10.1038/s41597-026-07016-6",
            "https://www.nature.com/articles/s41597-026-07016-6",
            "https://doi.org/10.21227/wq68-sv85",
            "https://ieee-dataport.org/open-access/new-dataset-millimeter-wave-radar-vital-sensing-reference-signals",
            "https://github.com/Rc-W024/VS_DATASET",
        ],
    },
    "D3": {
        "public_url": "https://huggingface.co/datasets/BreathSense/BreathSense",
        "publisher_or_host": "Hugging Face",
        "radar_frequency": "77 GHz",
        "radar_hardware": "Texas Instruments IWR1843BOOST + DCA1000",
        "raw_signal_type": "raw complex-valued radar ADC frames (.npy)",
        "processed_signal_type": "DR-MUSIC processed phase (*_drmusic.csv) plus chest-belt waveform (.csv)",
        "conditions": ["rest", "walk", "run", "stairs"],
        "breath_hold_ground_truth_available": False,
        "license": None,
        "license_status": "UNVERIFIED",
        "license_reason": "Hugging Face dataset API returned HTTP 403 and the dataset card license field was not retrievable during M-PV0. D3 remains non-blocking.",
        "count_claims": [
            {
                "claim": "108 participants / 432 paired recordings",
                "location": "Hugging Face dataset card opening description",
            },
            {
                "claim": "Participants 108 (p1-p108) in a property table, with Total recordings 360 (90 x 4) in the same table",
                "location": "Hugging Face dataset card statistics table",
            },
            {
                "claim": "90 participants spanning ages 22-40; 4 recordings per participant",
                "location": "Hugging Face dataset card participant section",
            },
            {
                "claim": "Each activity directory contains exactly 324 files = 108 participants x 3 file types",
                "location": "Hugging Face dataset card file-structure description",
            },
        ],
        "metadata_urls": [
            "https://huggingface.co/datasets/BreathSense/BreathSense",
        ],
        "raw_adc_downloaded": False,
        "processed_phase_downloaded": False,
    },
}

D2_CONTAMINATION_NEEDLES = (
    "wq68-sv85",
    "VITALSENSE_120",
    "s41597-026-07016",
    "VS01_Resting",
    "VS01_Apnea",
)


def sha256_file(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def dump_json(path: Path, obj: Any) -> str:
    text = json.dumps(obj, indent=2, sort_keys=True, ensure_ascii=True) + "\n"
    path.write_text(text, encoding="utf-8")
    return sha256_bytes(text.encode("utf-8"))


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def git_sha() -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()


def repo_rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def sorted_unique(values: list[str]) -> list[str]:
    return sorted(set(values))


def scan_d2_prelock_access() -> dict[str, Any]:
    """Search tracked text for D2 payload/inference use. Do not open .mat payloads."""
    hits: list[dict[str, Any]] = []
    skip_suffixes = {".png", ".jpg", ".jpeg", ".gif", ".pdf", ".zip", ".npy", ".npz", ".tflite", ".keras"}
    search_roots = (
        ROOT / "docs",
        ROOT / "datasets",
        ROOT / "config",
        ROOT / "models",
        ROOT / "scripts",
        ROOT / "tests",
    )
    for needle in D2_CONTAMINATION_NEEDLES:
        for search_root in search_roots:
            if not search_root.exists():
                continue
            for path in search_root.rglob("*"):
                if not path.is_file():
                    continue
                rel = repo_rel(path)
                if "/archive/" in f"/{rel}":
                    continue
                if path.suffix.lower() in skip_suffixes:
                    continue
                if "M-PV0_public_multidomain_registry" in rel:
                    continue
                if rel.startswith("scripts/mmwave_m_pv0") or rel.startswith("tests/test_mmwave_m_pv0"):
                    continue
                if rel.startswith("docs/mmwave/20260822_SafeNest_mmWave_M-PV0"):
                    continue
                try:
                    text = path.read_text(encoding="utf-8", errors="ignore")
                except OSError:
                    continue
                if needle in text:
                    hits.append({"path": rel, "needle": needle})
    roadmap_only = all(
        hit["path"] == repo_rel(V2_ROADMAP) for hit in hits
    ) if hits else True
    payload_acquired = False
    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue
        name = path.name
        if name.startswith("VS") and name.endswith(".mat"):
            payload_acquired = True
        if "VITALSENSE_120" in name and path.suffix.lower() in {".zip", ".mat"}:
            payload_acquired = True
    return {
        "text_hits": hits,
        "roadmap_citation_only": roadmap_only,
        "payload_files_present": payload_acquired,
        "candidate_inference_count": 0,
        "semantic_inspection_performed": False,
        "feature_extraction_performed": False,
    }


def reconstruct_consumed_subjects() -> dict[str, Any]:
    split = load_json(MN4_SPLIT)
    heldout = list(split["subject_ids"]["NEW_MODEL_HELDOUT_TEST"])
    val_subjects = list(split["subject_ids"]["VAL"])
    train_subjects = list(split["subject_ids"]["TRAIN"])
    a5 = load_json(A5_SPLIT)
    historical_locked = list(a5["subject_ids"]["LOCKED_TEST"])
    overlap_heldout_historical = sorted(set(heldout) & set(historical_locked))
    mn6 = load_json(MN6_HELDOUT)
    mn9 = load_json(MN9_RESULT)
    return {
        "m_n6_new_model_heldout_test": {
            "split_name": "NEW_MODEL_HELDOUT_TEST",
            "subject_count": len(heldout),
            "subject_ids": heldout,
            "window_count_supervised": mn6["heldout_window_count"],
            "heldout_access_state": mn6["heldout_access_state"],
            "heldout_may_be_reused_for_future_model_selection": mn6[
                "heldout_may_be_reused_for_future_model_selection"
            ],
            "provenance": [
                repo_rel(MN4_SPLIT),
                repo_rel(MN6_HELDOUT),
                repo_rel(MN4_SUMMARY),
            ],
            "v2_train_reuse": "FORBIDDEN",
            "v2_val_reuse": "FORBIDDEN",
            "v2_selection_reuse": "FORBIDDEN",
            "V2_SELECTION_REUSE": "FORBIDDEN",
        },
        "m_n9_public_test": {
            "distinct_from_m_n6_heldout": False,
            "NEW_MODEL_HELDOUT_TEST_INFERENCE_M_N9": mn9["NEW_MODEL_HELDOUT_TEST_INFERENCE_M_N9"],
            "public_heldout_rerun": mn9["public_heldout_rerun"],
            "additional_subject_ids": [],
            "provenance": [repo_rel(MN9_RESULT), repo_rel(MN9_LOCK)],
            "v2_selection_reuse": "FORBIDDEN_INHERITED_FROM_M_N6_HELDOUT",
        },
        "m_n6_val_selection_consumed": {
            "split_name": "VAL",
            "subject_count": len(val_subjects),
            "subject_ids": val_subjects,
            "role": "V1 family/seed selection only; not the M-PV0 heldout exclusion set",
            "v2_train_reuse": "ALLOWED_UNDER_NEW_V2_SPLIT_IDENTITY",
            "v2_selection_reuse": "NOT_AUTO_EXCLUDED_BY_M_PV0_HELDOUT_RULE",
            "note": "Roadmap exclusion is M-N6 heldout. V2 D0 may re-split the remaining 94-subject pool. Do not create that split in M-PV0.",
            "provenance": [repo_rel(MN4_SPLIT), repo_rel(MN6_LOCK)],
        },
        "m_n6_train_consumed": {
            "split_name": "TRAIN",
            "subject_count": len(train_subjects),
            "v2_train_reuse": "ALLOWED_UNDER_NEW_V2_SPLIT_IDENTITY",
            "note": "Subject IDs omitted here to keep the exclusion set explicit; full TRAIN list remains in the M-N4 split file.",
            "provenance": [repo_rel(MN4_SPLIT)],
        },
        "historical_b_locked_test": {
            "split_name": "LOCKED_TEST",
            "profile_id": a5["profile_id"],
            "subject_count": len(historical_locked),
            "subject_ids": historical_locked,
            "overlap_with_m_n6_heldout": overlap_heldout_historical,
            "v2_selection_reuse": "NOT_THE_M_PV0_CORE_EXCLUSION",
            "note": "Historical B LOCKED_TEST is a different lineage. Do not reopen the B live gate or copy B scores into V2. Overlap with M-N6 heldout is already forbidden via the heldout set.",
            "provenance": [repo_rel(A5_SPLIT)],
        },
        "remaining_d0_pool_for_future_v2_split": {
            "count": len(train_subjects) + len(val_subjects),
            "formula": "110 public subjects minus 16 M-N6 NEW_MODEL_HELDOUT_TEST subjects",
            "v2_split_created_in_m_pv0": False,
        },
        "CONSUMED_SUBJECT_SET_UNRESOLVED": False,
    }


def build_v1_baseline() -> dict[str, Any]:
    lock = load_json(MN9_LOCK)
    result = load_json(MN9_RESULT)
    mn6_lock = load_json(MN6_LOCK)
    mn6 = load_json(MN6_HELDOUT)
    mn7 = load_json(MN7_RESULT)
    contract = load_json(MN4_CONTRACT)
    float_sha = sha256_file(FLOAT_PATH)
    int8_sha = sha256_file(INT8_PATH)
    occupied = mn7["occupied_device_domain"]["prediction_summaries"]
    return {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE_ID,
        "role": "OBSERVE_ONLY_READ_ONLY_BASELINE",
        "v2_identity_reuse": "FORBIDDEN",
        "overwrite_m_n9_v1": "FORBIDDEN",
        "rewrite_historical_m_a_m_b": "FORBIDDEN",
        "reopen_historical_b_live_gate": "FORBIDDEN",
        "selected_int8": {
            "artifact_id": lock["artifact_id"],
            "artifact_path": lock["locked_artifact_path"],
            "artifact_sha256": int8_sha,
            "lock_sha256": lock["artifact_sha256"],
            "sha_match": int8_sha == lock["artifact_sha256"] == result["artifact_sha256"],
            "size_bytes": INT8_PATH.stat().st_size,
            "dtype_input": lock["input_contract"]["dtype"],
            "input_shape": lock["input_contract"]["shape"],
            "output_shape": lock["output_contract"]["shape"],
            "output_dtype": lock["output_contract"]["dtype"],
            "provenance": [repo_rel(MN9_LOCK), repo_rel(MN9_RESULT), repo_rel(INT8_PATH)],
        },
        "selected_float": {
            "selection_id": lock["source_selection_id"],
            "artifact_path": lock["source_float_path"],
            "artifact_sha256": float_sha,
            "lock_sha256": lock["source_float_sha256"],
            "sha_match": float_sha == lock["source_float_sha256"] == mn6_lock["artifact_sha256"],
            "architecture": lock["source_architecture"],
            "seed": lock["source_seed"],
            "parameter_count": lock["source_parameter_count"],
            "provenance": [repo_rel(MN6_LOCK), repo_rel(FLOAT_PATH), repo_rel(MN9_LOCK)],
        },
        "input_preprocessing_contract": {
            "contract_id": contract["contract_id"],
            "representation": contract["derivative"]["representation"],
            "scale_method": contract["scale"]["method"],
            "normalization_formula": contract["scale"]["normalization_formula"],
            "divide_only_no_centering": contract["scale"]["divide_only_no_centering"],
            "target_rate_hz": contract["resampling"]["target_rate_hz"],
            "window_seconds": contract["resampling"]["window_seconds"],
            "sample_count": contract["resampling"]["sample_count"],
            "input_shape": contract["resampling"]["input_shape"],
            "input_dtype_before_training": contract["resampling"]["input_dtype_before_training"],
            "large_gap_interpolation": contract["gap"]["long_gap_interpolation"],
            "window_containing_large_gap": contract["gap"]["window_containing_large_gap"],
            "provenance": [repo_rel(MN4_CONTRACT)],
        },
        "output_semantics": {
            "class_mapping": contract["target"]["class_mapping"],
            "class_semantics": contract["target"]["class_semantics"],
            "apnea_is_clinical_diagnosis": False,
            "apnea_is_voluntary_breath_hold_proxy": True,
            "neural_class_count": 3,
            "abstention_neural_class": False,
            "input_unavailable_neural_class": False,
            "presence_gate": lock["presence_gate"],
            "presence_gate_exact_runtime": lock["presence_gate"]["exact_runtime_implementation"],
            "provenance": [repo_rel(MN4_CONTRACT), repo_rel(MN9_LOCK)],
        },
        "fail_closed_observed": {
            "large_gap_becomes_synthetic_normal": False,
            "empty_room_zero_tensor_maps_to_high_conf_apnea": True,
            "presence_gate_required": True,
            "input_unavailable_implemented_as_model_output": False,
            "v2_must_preserve_abstention_requirement": True,
        },
        "public_heldout_result": {
            "split": "NEW_MODEL_HELDOUT_TEST",
            "accuracy": mn6["metrics"]["accuracy"],
            "macro_f1": mn6["metrics"]["macro_f1"],
            "per_class_recall": mn6["metrics"]["per_class_recall"],
            "confusion_matrix": mn6["metrics"]["confusion_matrix"],
            "provenance": [repo_rel(MN6_HELDOUT)],
        },
        "m_n7_mr60_application": {
            "check_type": mn7["check_type"],
            "evidence_class": mn7["evidence_class"],
            "mr60_accuracy_computed": mn7["mr60_accuracy_computed"],
            "occupied_predicted_class_distribution": mn7["occupied_device_domain"][
                "predicted_class_distribution"
            ],
            "occupied_windows": occupied,
            "low_amplitude_occupied_window": {
                "session_id": "LEGACY_2026-07-25_occupied_front_d06_60s",
                "mad": 0.016797,
                "predicted_class": "APNEA",
                "confidence": 0.999976,
                "note": "Repository evidence nearest to the V2 roadmap MAD≈0.02 observation. No independent NORMAL/APNEA ground truth.",
            },
            "empty_no_person": {
                "NO_PERSON_INFERENCE_GATING_HAZARD": mn7["empty_no_person"][
                    "NO_PERSON_INFERENCE_GATING_HAZARD"
                ],
                "predicted_class_distribution": mn7["empty_no_person"]["predicted_class_distribution"],
                "confidence_min": mn7["empty_no_person"]["confidence_min"],
            },
            "cadence_gap_freeze": {
                "empty_republications": 507,
                "occupied_d06_republications": 2,
                "canonical_timing_status": "CANONICAL_TIMING_ELIGIBLE",
                "provenance": [repo_rel(MN7_RESULT)],
            },
            "supervised_use": "FORBIDDEN",
            "provenance": [repo_rel(MN7_RESULT)],
        },
        "root_model_manifest_status": {
            "lists_m_n9_v1": load_json(MODEL_MANIFEST).get("models", {}).get("mmwave", {}).get("model_id")
            == "MMWAVE_M_N9_FULL_INT8_V1",
            "historical_mmwave_entry_is_not_v1": True,
            "note": "models/model_manifest.json still describes historical mmwave_resp_int8 artifacts, not M-N9 V1. V1 identity is the M-N9 lock/result pair.",
            "provenance": [repo_rel(MODEL_MANIFEST), repo_rel(MN9_LOCK)],
        },
        "val_int8_parity": {
            "parity_gate": result["val_parity"]["parity_gate"],
            "top1_agreement": result["val_parity"]["top1_agreement"],
            "val_int8_macro_f1": result["val_int8"]["macro_f1"],
            "provenance": [repo_rel(MN9_RESULT)],
        },
    }


def build_source_registry(consumed: dict[str, Any], d2_audit: dict[str, Any]) -> dict[str, Any]:
    a0 = load_json(A0_IDENTITY)
    datasets = load_json(DATASETS_MANIFEST)
    d0_pub = PUBLIC_METADATA_AUDIT["D0"]
    d1_pub = PUBLIC_METADATA_AUDIT["D1"]
    d2_pub = PUBLIC_METADATA_AUDIT["D2"]
    d3_pub = PUBLIC_METADATA_AUDIT["D3"]
    local_zip = ROOT / a0["local_archive"]["path"]
    return {
        "schema_version": SCHEMA_VERSION,
        "registry_id": REGISTRY_ID,
        "phase": PHASE_ID,
        "audit_date": AUDIT_DATE,
        "apnea_policy": {
            "safenest_apnea": "voluntary breath-hold based APNEA proxy, not clinical apnea diagnosis",
            "external_source_term_apnea": "preserve as source metadata only; map explicitly to APNEA-proxy / voluntary breath-hold",
        },
        "consumed_evidence": consumed,
        "sources": {
            "D0": {
                "source_id": "D0",
                "canonical_name": a0["dataset_identity"]["title"],
                "public_url": "https://zenodo.org/records/18599983",
                "publication_doi": None,
                "publication_doi_status": "UNVERIFIED_IN_M_PV0_SEPARATE_FROM_DATASET_DOI",
                "dataset_doi_or_record_id": d0_pub["canonical_doi"],
                "publisher_or_host": "Zenodo",
                "dataset_version": d0_pub["canonical_version"],
                "release_or_update_date": d0_pub["canonical_publication_date"],
                "license": d0_pub["license"],
                "access_mode": "OPEN_PUBLIC_DOWNLOAD",
                "expected_download_size": d0_pub["official_db_records_zip_bytes"],
                "radar_frequency": d0_pub["radar_frequency"],
                "radar_hardware": d0_pub["radar_hardware"],
                "raw_signal_type": "radar_rFFTs.zlib range-FFT arrays",
                "processed_signal_type": "A2 native unwrapped phase then M-N4 R2 + window-local MAD",
                "reference_modality": "Movesense ECG and chest ACC; USB-button non-breathing timestamps",
                "subject_count_claims": {
                    "repository": datasets["datasets"]["mmwave"]["participant_count"],
                    "public_metadata": 110,
                    "conflict": False,
                },
                "recording_count_claims": {
                    "repository": datasets["datasets"]["mmwave"]["recording_count"],
                    "public_metadata": 440,
                    "conflict": False,
                },
                "conditions": ["lying/sitting", "rest", "post-exercise", "voluntary non-breathing"],
                "breath_hold_ground_truth_available": True,
                "intended_role": "REQUIRED_PRIMARY_DEVELOPMENT_DOMAIN",
                "allowed_uses": [
                    "V2 subject-diverse development after excluding M-N6 heldout subjects",
                    "breathing-evidence / RR / APNEA-proxy supervision from public labels",
                ],
                "forbidden_uses": [
                    "Reusing M-N6 NEW_MODEL_HELDOUT_TEST subjects in V2 TRAIN/VAL/selection",
                    "Claiming clinical apnea",
                ],
                "lock_state": "UNLOCKED_DEVELOPMENT_DOMAIN",
                "checksum_source": "Zenodo official db_records.zip md5; A0 local SHA-256 of a repackaged archive",
                "local_payload_present": local_zip.is_file(),
                "provenance_evidence": [
                    repo_rel(A0_IDENTITY),
                    repo_rel(DATASETS_MANIFEST),
                    repo_rel(MN4_CONTRACT),
                    *d0_pub["metadata_urls"],
                ],
                "known_ambiguities": [
                    "Roadmap cites zenodo.org/records/16760684 (v1.0). Repository A0/M-N lineage is locked to 10.5281/zenodo.18599983 (v1.1). Both share concept 16760683 and the same official db_records.zip md5.",
                    a0["official_to_local_relationship"]["relationship_status"],
                ],
                "roadmap_cited_record": {
                    "url": "https://zenodo.org/records/16760684",
                    "doi": d0_pub["roadmap_cited_doi"],
                    "version": d0_pub["roadmap_cited_version"],
                    "same_concept_as_canonical": True,
                },
            },
            "D1": {
                "source_id": "D1",
                "canonical_name": d1_pub["dataset_title"],
                "public_url": "https://doi.org/10.6084/m9.figshare.c.4633958.v1",
                "publication_doi": d1_pub["publication_doi"],
                "dataset_doi_or_record_id": d1_pub["article_doi"],
                "publisher_or_host": d1_pub["publisher_or_host"],
                "dataset_version": "figshare article v1 / collection v1",
                "release_or_update_date": "2019-08-20",
                "license": d1_pub["license"],
                "access_mode": d1_pub["access_mode"],
                "expected_download_size": d1_pub["expected_download_size_bytes"],
                "radar_frequency": d1_pub["radar_frequency"],
                "radar_hardware": d1_pub["radar_hardware"],
                "raw_signal_type": d1_pub["raw_signal_type"],
                "processed_signal_type": d1_pub["processed_signal_type"],
                "reference_modality": "ECG, PCG, temperature-based airflow respiration sensor",
                "subject_count_claims": {"public_metadata": d1_pub["subject_count"], "conflict": False},
                "recording_count_claims": {
                    "public_metadata": d1_pub["recording_duration_claim"],
                    "exact_file_count": None,
                    "reason_if_null": "Landing-page metadata reports duration, not a single authoritative recording-count integer.",
                },
                "conditions": d1_pub["conditions"],
                "breath_hold_ground_truth_available": True,
                "intended_role": "REQUIRED_AUXILIARY_DEVELOPMENT_DOMAIN",
                "allowed_uses": [
                    "Cross-frequency feature/model-family comparison after I/Q adapter",
                    "distance/angle/speech robustness",
                ],
                "forbidden_uses": [
                    "Implementing the I/Q adapter in M-PV0",
                    "Oversampling all 11 subjects to match D0 110-subject weight",
                    "APNEA clinical diagnosis claims",
                ],
                "lock_state": "UNLOCKED_DEVELOPMENT_DOMAIN_METADATA_ONLY_IN_M_PV0",
                "checksum_source": d1_pub["checksum_source"],
                "payload_md5": d1_pub["payload_md5"],
                "local_payload_present": False,
                "provenance_evidence": d1_pub["metadata_urls"],
                "known_ambiguities": [],
                "adapter_implemented_in_m_pv0": False,
            },
            "D2": {
                "source_id": "D2",
                "canonical_name": d2_pub["publication_title"],
                "public_url": d2_pub["ieee_dataport_url"],
                "publication_doi": d2_pub["publication_doi"],
                "dataset_doi_or_record_id": d2_pub["dataset_doi"],
                "publisher_or_host": "IEEE DataPort / Scientific Data; GitHub companion Rc-W024/VS_DATASET",
                "dataset_version": None,
                "dataset_version_status": "UNVERIFIED_NO_NUMERIC_VERSION_ON_AUDITED_PAGES",
                "release_or_update_date": "IEEE DataPort created 2025-10-27; page last updated 2026-05-07; Scientific Data article 2026",
                "license": {
                    "publication": d2_pub["publication_license"],
                    "ieee_dataport": "OPEN_ACCESS_LOGIN_REQUIRED",
                    "ieee_dataport_full_terms": "UNVERIFIED",
                    "github_code": d2_pub["github_code_license"],
                },
                "access_mode": d2_pub["access_mode"],
                "expected_download_size": {
                    "ieee_dataport": d2_pub["announced_ieee_size"],
                    "github_readme": d2_pub["announced_github_size"],
                    "conflict": True,
                },
                "radar_frequency": d2_pub["radar_frequency"],
                "radar_hardware": d2_pub["radar_hardware"],
                "raw_signal_type": d2_pub["raw_signal_type"],
                "processed_signal_type": d2_pub["processed_signal_type"],
                "reference_modality": "Mindray ePM10 ECG, impedance respiration, PPG, sphygmomanometer",
                "subject_count_claims": {"public_metadata": d2_pub["subject_count"], "conflict": False},
                "recording_count_claims": {"public_metadata": d2_pub["recording_count_claim"]},
                "conditions": d2_pub["conditions"],
                "breath_hold_ground_truth_available": True,
                "source_term_apnea": "publication uses 'apnea' for instructed inhale-and-hold; SafeNest maps this to APNEA-proxy / voluntary breath-hold",
                "intended_role": "LOCKED_PUBLIC_CROSS_DEVICE_TEST",
                "allowed_uses": [
                    "PUBLIC_METADATA_ACCESS in M-PV0",
                    "later dedicated acquisition/checksum lane under this lock",
                    "one authorized final cross-device evaluation after M-PV3 lock",
                ],
                "forbidden_uses": [
                    "representation_selection",
                    "feature_selection",
                    "model_family_selection",
                    "seed_selection",
                    "threshold_selection",
                    "calibration_selection",
                    "augmentation_selection",
                    "candidate_inference before authorized D2 evaluation",
                    "loading .mat arrays or plotting/deriving labels beyond public protocol metadata in M-PV0",
                ],
                "lock_state": "LOCKED_BEFORE_SEMANTIC_USE",
                "checksum_source": d2_pub["checksum_source"],
                "local_payload_present": d2_audit["payload_files_present"],
                "provenance_evidence": d2_pub["metadata_urls"],
                "known_ambiguities": [
                    "IEEE DataPort lists 28.69 MB; GitHub README says about 31 MB. No payload SHA-256 was published on the audited landing pages.",
                    "IEEE DataPort requires login even for the open-access zip.",
                ],
                "prelock_access": {
                    "PUBLIC_METADATA_ACCESS": "YES",
                    "PAYLOAD_ACQUISITION": "NO",
                    "PAYLOAD_SEMANTIC_INSPECTION": "NO",
                    "FEATURE_EXTRACTION": "NO",
                    "MODEL_INFERENCE": "NO",
                    "MODEL_INFERENCE_COUNT": 0,
                    "roadmap_citation_only_before_m_pv0": d2_audit["roadmap_citation_only"],
                    "text_hits_before_m_pv0": d2_audit["text_hits"],
                },
            },
            "D3": {
                "source_id": "D3",
                "canonical_name": "BreathSense",
                "public_url": d3_pub["public_url"],
                "publication_doi": None,
                "publication_doi_status": "UNVERIFIED",
                "dataset_doi_or_record_id": None,
                "publisher_or_host": d3_pub["publisher_or_host"],
                "dataset_version": None,
                "dataset_version_status": "UNVERIFIED",
                "release_or_update_date": None,
                "license": d3_pub["license"],
                "license_status": d3_pub["license_status"],
                "access_mode": "HUGGINGFACE_PUBLIC_DATASET_CARD",
                "expected_download_size": None,
                "expected_download_size_status": "UNVERIFIED_RAW_ADC_ANNOUNCED_AS_VERY_LARGE",
                "radar_frequency": d3_pub["radar_frequency"],
                "radar_hardware": d3_pub["radar_hardware"],
                "raw_signal_type": d3_pub["raw_signal_type"],
                "processed_signal_type": d3_pub["processed_signal_type"],
                "reference_modality": "calibrated chest respiratory belt waveform",
                "subject_count_claims": {
                    "claims": d3_pub["count_claims"],
                    "conflict": True,
                    "resolved": False,
                },
                "recording_count_claims": {
                    "claims": ["432 paired recordings", "360 recordings (90 x 4)", "108 participants x 4 activities implied by file structure"],
                    "conflict": True,
                    "resolved": False,
                },
                "conditions": d3_pub["conditions"],
                "breath_hold_ground_truth_available": d3_pub["breath_hold_ground_truth_available"],
                "intended_role": "OPTIONAL_NON_BLOCKING_QUALITY_RR_DEVELOPMENT_DOMAIN",
                "allowed_uses": [
                    "motion contamination",
                    "quality estimation",
                    "abstention development",
                    "respiratory-waveform / RR reconstruction when contents and rights are verified",
                ],
                "forbidden_uses": [
                    "Converting no-breath-hold conditions into APNEA-proxy supervision",
                    "Blocking D0+D1 if D3 license/count/raw-ADC audit is incomplete",
                    "Bulk raw ADC download during M-PV0",
                ],
                "lock_state": "OPTIONAL_NON_BLOCKING",
                "checksum_source": None,
                "local_payload_present": False,
                "processed_phase_local_payload_present": False,
                "raw_adc_local_payload_present": False,
                "provenance_evidence": d3_pub["metadata_urls"],
                "known_ambiguities": [
                    "SOURCE_METADATA_DISCREPANCY: 108/432 vs 90/360 vs 108-participant file-structure counts remain unresolved",
                    "License field UNVERIFIED",
                ],
            },
        },
    }


def build_role_lock_policy(consumed: dict[str, Any], d2_audit: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE_ID,
        "v1_role": "OBSERVE_ONLY",
        "v2_new_identity_required": True,
        "roles": {
            "D0": "REQUIRED_PRIMARY_DEVELOPMENT_DOMAIN",
            "D1": "REQUIRED_AUXILIARY_DEVELOPMENT_DOMAIN",
            "D2": "LOCKED_PUBLIC_CROSS_DEVICE_TEST",
            "D3": "OPTIONAL_NON_BLOCKING_QUALITY_RR_DEVELOPMENT_DOMAIN",
        },
        "D0_ROLE_UNAMBIGUOUS": "YES",
        "D1_ROLE_UNAMBIGUOUS": "YES",
        "D2_ROLE_LOCKED": "YES",
        "D3_NON_BLOCKING": "YES",
        "d2_lock": {
            "lock_state": "LOCKED_BEFORE_SEMANTIC_USE",
            "representation_selection": "FORBIDDEN",
            "feature_selection": "FORBIDDEN",
            "model_family_selection": "FORBIDDEN",
            "seed_selection": "FORBIDDEN",
            "threshold_selection": "FORBIDDEN",
            "calibration_selection": "FORBIDDEN",
            "augmentation_selection": "FORBIDDEN",
            "candidate_inference": "FORBIDDEN",
            "candidate_inference_count": 0,
            "PUBLIC_METADATA_ACCESS": "YES",
            "PAYLOAD_ACQUISITION": "NO",
            "PAYLOAD_SEMANTIC_INSPECTION": "NO",
            "FEATURE_EXTRACTION": "NO",
            "MODEL_INFERENCE": "NO",
            "MODEL_INFERENCE_COUNT": 0,
            "prelock_contamination": False,
            "payload_files_present": d2_audit["payload_files_present"],
            "roadmap_citation_only_before_m_pv0": d2_audit["roadmap_citation_only"],
        },
        "mr60_policy": {
            "supervised_TRAIN": "FORBIDDEN",
            "supervised_VAL": "FORBIDDEN",
            "supervised_TEST": "FORBIDDEN",
            "representation_selection": "FORBIDDEN",
            "model_family_selection": "FORBIDDEN",
            "threshold_tuning": "FORBIDDEN",
            "calibration": "FORBIDDEN",
            "augmentation_tuning": "FORBIDDEN",
            "label_construction": "FORBIDDEN",
            "allowed_later_uses": [
                "cadence/jitter/duplicate/freeze corruption profiles",
                "replay/application smoke",
                "runtime compatibility observations",
            ],
            "current_safenest_mr60_never_supervised_for_v2": True,
        },
        "fail_closed_policy": {
            "flat_stale_gap_freeze_corrupt_motion_must_not_become_synthetic_normal": True,
            "flat_stale_gap_freeze_corrupt_motion_must_not_become_high_confidence_apnea_for_want_of_a_class": True,
            "later_stages_must_provide_abstention_or_INPUT_UNAVAILABLE": True,
            "v1_has_input_unavailable_neural_class": False,
            "v1_presence_gate_required": True,
            "v1_large_gap_window_rejected": True,
        },
        "heldout_exclusion": {
            "OLD_HELDOUT_SELECTION_REUSE_FORBIDDEN": "YES",
            "excluded_subject_ids": consumed["m_n6_new_model_heldout_test"]["subject_ids"],
            "V2_SELECTION_REUSE": "FORBIDDEN",
            "CONSUMED_SUBJECT_SET_UNRESOLVED": False,
            "v2_d0_split_created_in_m_pv0": False,
        },
        "historical_b_live_gate": "CLOSED_DO_NOT_REOPEN",
    }


def build_license_access_audit() -> dict[str, Any]:
    d0 = PUBLIC_METADATA_AUDIT["D0"]
    d1 = PUBLIC_METADATA_AUDIT["D1"]
    d2 = PUBLIC_METADATA_AUDIT["D2"]
    d3 = PUBLIC_METADATA_AUDIT["D3"]
    return {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE_ID,
        "audit_date": AUDIT_DATE,
        "sources": {
            "D0": {
                "license": d0["license"],
                "access_mode": "OPEN_PUBLIC_DOWNLOAD",
                "limitations": [
                    "Canonical identity is Zenodo v1.1 record 18599983, not the roadmap v1.0 record 16760684.",
                    "A0 local archive is a likely repackaged zip; official member-level identity is not fully verified.",
                ],
            },
            "D1": {
                "license": d1["license"],
                "access_mode": d1["access_mode"],
                "payload_filename": d1["payload_filename"],
                "payload_md5": d1["payload_md5"],
                "limitations": [],
            },
            "D2": {
                "publication_license": d2["publication_license"],
                "ieee_dataport_access": d2["access_mode"],
                "ieee_dataport_full_terms": "UNVERIFIED",
                "github_code_license": d2["github_code_license"],
                "checksum_source": d2["checksum_source"],
                "limitations": [
                    "IEEE DataPort zip download requires a free IEEE account login.",
                    "No payload SHA-256 was published on the audited landing pages.",
                    "Announced size differs between IEEE DataPort (28.69 MB) and GitHub README (~31 MB).",
                ],
            },
            "D3": {
                "license": d3["license"],
                "license_status": d3["license_status"],
                "license_reason": d3["license_reason"],
                "raw_adc_downloaded": False,
                "processed_phase_downloaded": False,
                "limitations": [
                    "Participant/recording counts conflict across the public card.",
                    "License UNVERIFIED. Non-blocking for D0+D1.",
                ],
            },
        },
        "d2_access_audit": {
            "PUBLIC_METADATA_ACCESS": "YES",
            "PAYLOAD_ACQUISITION": "NO",
            "PAYLOAD_SEMANTIC_INSPECTION": "NO",
            "FEATURE_EXTRACTION": "NO",
            "MODEL_INFERENCE": "NO",
            "MODEL_INFERENCE_COUNT": 0,
        },
    }


def build_exception_registry(consumed: dict[str, Any], d2_audit: dict[str, Any]) -> dict[str, Any]:
    exceptions = [
        {
            "code": "D0_ZENODO_VERSION_POINTER_DISCREPANCY",
            "severity": "NON_BLOCKING_WARNING",
            "blocking": False,
            "summary": "V2 roadmap cites Zenodo record 16760684 (v1.0). Repository A0/M-N identity is 10.5281/zenodo.18599983 (v1.1). Same concept 16760683; official db_records.zip md5 matches.",
        },
        {
            "code": "D0_LOCAL_PAYLOAD_ABSENT_IN_THIS_WORKTREE",
            "severity": "NON_BLOCKING_WARNING",
            "blocking": False,
            "summary": "gitignored local db_records.zip is not present in the M-PV0 worktree. A0 previously inventoried a local repackaged archive. D0 role remains unambiguous.",
        },
        {
            "code": "D0_OFFICIAL_VS_LOCAL_REPACKAGING",
            "severity": "NON_BLOCKING_WARNING",
            "blocking": False,
            "summary": "A0 relationship_status is LIKELY_REPACKAGED_NOT_FULLY_VERIFIED. Inherited historical limitation, not an M-PV0 role failure.",
        },
        {
            "code": "D2_IEEE_DATAPORT_LOGIN_REQUIRED",
            "severity": "NON_BLOCKING_WARNING",
            "blocking": False,
            "summary": "Later D2 acquisition/checksum lane must use an IEEE DataPort login. M-PV0 did not acquire the zip.",
        },
        {
            "code": "D2_ANNOUNCED_SIZE_DISCREPANCY",
            "severity": "NON_BLOCKING_WARNING",
            "blocking": False,
            "summary": "IEEE DataPort lists 28.69 MB; GitHub README says about 31 MB. No published SHA-256 on audited pages.",
        },
        {
            "code": "D2_PAYLOAD_CHECKSUM_NOT_PUBLISHED",
            "severity": "NON_BLOCKING_WARNING",
            "blocking": False,
            "summary": "D2 lock is established on role/policy. Payload checksum verification belongs to the later acquisition lane.",
        },
        {
            "code": "D3_PARTICIPANT_RECORDING_COUNT_CONFLICT",
            "severity": "NON_BLOCKING_WARNING",
            "blocking": False,
            "summary": "BreathSense public card reports 108/432, 90/360, and 108-participant file-structure counts. Unresolved. Non-blocking.",
        },
        {
            "code": "D3_LICENSE_UNVERIFIED",
            "severity": "NON_BLOCKING_WARNING",
            "blocking": False,
            "summary": "BreathSense license field was not retrievable (Hugging Face API 403 / card auth failure). Non-blocking.",
        },
        {
            "code": "V1_NO_INPUT_UNAVAILABLE_NEURAL_CLASS",
            "severity": "POLICY_REQUIREMENT",
            "blocking": False,
            "summary": "V1 has a required presence gate and rejects large-gap windows, but no INPUT_UNAVAILABLE neural class. Later V2 stages must preserve abstention/fail-closed.",
        },
        {
            "code": "ROOT_MODEL_MANIFEST_DOES_NOT_LIST_M_N9_V1",
            "severity": "INFORMATIONAL",
            "blocking": False,
            "summary": "models/model_manifest.json still describes historical mmwave_resp_int8 artifacts. Authoritative V1 identity is the M-N9 lock/result.",
        },
    ]
    if consumed["CONSUMED_SUBJECT_SET_UNRESOLVED"]:
        exceptions.append(
            {
                "code": "CONSUMED_SUBJECT_SET_UNRESOLVED",
                "severity": "BLOCKER",
                "blocking": True,
                "summary": "M-N6 heldout subject IDs could not be reconstructed.",
            }
        )
    if d2_audit["payload_files_present"] or not d2_audit["roadmap_citation_only"]:
        if d2_audit["payload_files_present"]:
            exceptions.append(
                {
                    "code": "D2_PAYLOAD_ALREADY_PRESENT",
                    "severity": "BLOCKER",
                    "blocking": True,
                    "summary": "D2 payload files were found before the lock.",
                }
            )
        extra = [h for h in d2_audit["text_hits"] if h["path"] != repo_rel(V2_ROADMAP)]
        if extra:
            exceptions.append(
                {
                    "code": "D2_PRELOCK_TEXT_HITS_OUTSIDE_ROADMAP",
                    "severity": "NON_BLOCKING_WARNING",
                    "blocking": False,
                    "summary": "D2 identifiers appear outside the V2 roadmap. Review listed paths; M-PV0 found no payload or inference.",
                    "hits": extra,
                }
            )
    return {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE_ID,
        "total_blockers": sum(1 for row in exceptions if row["blocking"]),
        "total_warnings": sum(1 for row in exceptions if row["severity"] == "NON_BLOCKING_WARNING"),
        "exceptions": exceptions,
        "CONSUMED_SUBJECT_SET_UNRESOLVED": consumed["CONSUMED_SUBJECT_SET_UNRESOLVED"],
    }


def decide_gate(exceptions: dict[str, Any], d2_audit: dict[str, Any], consumed: dict[str, Any]) -> dict[str, Any]:
    flags = {
        "D0_ROLE_UNAMBIGUOUS": "YES",
        "D1_ROLE_UNAMBIGUOUS": "YES",
        "D2_ROLE_LOCKED": "YES",
        "D3_NON_BLOCKING": "YES",
        "D2_PRELOCK_ACCESS_AUDIT_EXISTS": "YES",
        "D2_MODEL_INFERENCE_COUNT": 0,
        "MR60_SUPERVISED_USE_FORBIDDEN": "YES",
        "OLD_HELDOUT_SELECTION_REUSE_FORBIDDEN": "YES",
        "PARALLEL_TRACK_BRANCH_CONTAMINATION": "NO",
        "CONSUMED_SUBJECT_SET_UNRESOLVED": consumed["CONSUMED_SUBJECT_SET_UNRESOLVED"],
        "D2_PRELOCK_CONTAMINATION": bool(d2_audit["payload_files_present"]),
    }
    blockers = [row for row in exceptions["exceptions"] if row["blocking"]]
    core_fail = (
        flags["D0_ROLE_UNAMBIGUOUS"] != "YES"
        or flags["D1_ROLE_UNAMBIGUOUS"] != "YES"
        or flags["D2_ROLE_LOCKED"] != "YES"
        or flags["D3_NON_BLOCKING"] != "YES"
        or flags["D2_PRELOCK_ACCESS_AUDIT_EXISTS"] != "YES"
        or flags["D2_MODEL_INFERENCE_COUNT"] != 0
        or flags["MR60_SUPERVISED_USE_FORBIDDEN"] != "YES"
        or flags["OLD_HELDOUT_SELECTION_REUSE_FORBIDDEN"] != "YES"
        or flags["PARALLEL_TRACK_BRANCH_CONTAMINATION"] != "NO"
        or flags["CONSUMED_SUBJECT_SET_UNRESOLVED"]
        or flags["D2_PRELOCK_CONTAMINATION"]
        or bool(blockers)
    )
    if core_fail:
        gate = "BLOCKED"
    elif exceptions["total_warnings"] > 0:
        gate = "PASS_WITH_LIMITATIONS"
    else:
        gate = "PASS"
    authorized = {
        "D0": gate != "BLOCKED",
        "D1": gate != "BLOCKED",
        "D2_acquisition_checksum_lane": gate != "BLOCKED",
        "D2_semantic_inspection": False,
        "D2_model_inference": False,
        "D3": gate != "BLOCKED",
        "R1": gate != "BLOCKED",
        "Q1": gate != "BLOCKED",
        "I1": gate != "BLOCKED",
        "M-PV1": False,
        "M-PV2": False,
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE_ID,
        "gate": gate,
        "flags": flags,
        "next_lanes_authorized": authorized,
        "base_sha": git_sha(),
        "base_sha_meaning": BASE_SHA_MEANING,
    }


def assert_no_absolute_paths(obj: Any, trail: str = "$") -> None:
    if isinstance(obj, dict):
        for key, value in obj.items():
            assert_no_absolute_paths(value, f"{trail}.{key}")
    elif isinstance(obj, list):
        for idx, value in enumerate(obj):
            assert_no_absolute_paths(value, f"{trail}[{idx}]")
    elif isinstance(obj, str) and ABSOLUTE_PATH_RE.search(obj):
        raise RuntimeError(f"ABSOLUTE_PATH_PERSISTED:{trail}:{obj}")


def write_registry() -> dict[str, Any]:
    for required in (
        FLOAT_PATH,
        INT8_PATH,
        MN9_LOCK,
        MN9_RESULT,
        MN6_LOCK,
        MN6_HELDOUT,
        MN7_RESULT,
        MN4_CONTRACT,
        MN4_SPLIT,
        A0_IDENTITY,
        V2_ROADMAP,
        MN_ROADMAP,
    ):
        if not required.is_file():
            raise RuntimeError(f"MISSING_AUTHORITATIVE_FILE:{repo_rel(required)}")

    REGISTRY_DIR.mkdir(parents=True, exist_ok=True)
    consumed = reconstruct_consumed_subjects()
    d2_audit = scan_d2_prelock_access()
    source_registry = build_source_registry(consumed, d2_audit)
    role_lock = build_role_lock_policy(consumed, d2_audit)
    license_audit = build_license_access_audit()
    v1 = build_v1_baseline()
    exceptions = build_exception_registry(consumed, d2_audit)
    gate = decide_gate(exceptions, d2_audit, consumed)
    role_lock["gate"] = gate["gate"]
    role_lock["gate_flags"] = gate["flags"]
    role_lock["next_lanes_authorized"] = gate["next_lanes_authorized"]
    role_lock["base_sha"] = gate["base_sha"]
    role_lock["base_sha_meaning"] = gate["base_sha_meaning"]

    payloads = {
        "source_registry.json": source_registry,
        "role_lock_policy.json": role_lock,
        "license_access_audit.json": license_audit,
        "v1_failure_baseline.json": v1,
        "exception_registry.json": exceptions,
    }
    for obj in payloads.values():
        assert_no_absolute_paths(obj)

    checksums: dict[str, str] = {}
    for name, obj in payloads.items():
        checksums[name] = dump_json(REGISTRY_DIR / name, obj)
    checksum_doc = {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE_ID,
        "algorithm": "SHA-256",
        "encoding": "utf-8 JSON indent=2 sort_keys=True trailing newline",
        "files": checksums,
    }
    assert_no_absolute_paths(checksum_doc)
    dump_json(REGISTRY_DIR / "checksums.json", checksum_doc)
    return gate


def main() -> int:
    gate = write_registry()
    print(f"M-PV0 gate={gate['gate']} dir={repo_rel(REGISTRY_DIR)}")
    return 0 if gate["gate"] != "BLOCKED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
