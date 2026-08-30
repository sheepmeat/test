#!/usr/bin/env python3
"""Build the Thermal-IM seated hard-negative frame pool for Thermal V2 Candidate A.

Decodes every acquired official clip archive, applies the conservative admitted-token policy,
expands admitted intervals to frames using the verified 15 FPS timing contract, applies the
Thermal-IM source-specific geometry adapter, and writes a frame pool plus a full lineage manifest
and interval decision ledger.

Outputs are written under ``--work-root`` (outside Git). No raw Thermal-IM media is copied into
the repository.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from datasets.thermal import tv2_ca_thermal_im_source as tim  # noqa: E402

REGISTRY = ROOT / "config" / "thermal" / "tv2_candidate_a_thermal_im_source_registry.json"


def main() -> int:
    parser = argparse.ArgumentParser(description="Build Thermal-IM seated hard-negative pool")
    parser.add_argument("--work-root", required=True)
    parser.add_argument("--holdout-groups", type=int, default=3)
    parser.add_argument("--split-seed", type=int, default=42)
    args = parser.parse_args()

    work_root = Path(args.work_root)
    archive_root = work_root / "thermal_im" / "archives"
    receipt_path = work_root / "thermal_im" / "acquisition_receipt.json"
    if not receipt_path.is_file():
        print(json.dumps({"status": "BLOCKED_THERMAL_IM_SOURCE_IDENTITY",
                          "error": f"missing acquisition receipt {receipt_path}"}, indent=2))
        return 2

    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    if receipt["identity_status"] != "VERIFIED_AGAINST_D1_ANCHORS":
        print(json.dumps({"status": "BLOCKED_THERMAL_IM_SOURCE_IDENTITY",
                          "identity_status": receipt["identity_status"]}, indent=2))
        return 2
    observed = {item["archive_name"]: item for item in receipt["archives"]}

    clips: list[dict] = []
    failures: list[dict] = []
    for entry in registry["archives"]:
        name = entry["archive_name"]
        record = observed.get(name)
        if record is None or record["status"] == "FAILED":
            failures.append({"archive_name": name, "reason": "NOT_ACQUIRED"})
            continue
        archive_path = archive_root / name
        if not archive_path.is_file():
            failures.append({"archive_name": name, "reason": "MISSING_ON_DISK"})
            continue
        merged = dict(entry)
        merged["observed_sha256"] = record["sha256"]
        try:
            clips.append(tim.extract_clip(archive_path, merged))
        except tim.ThermalImSourceError as exc:
            failures.append({"archive_name": name, "reason": f"EXTRACTION_FAILED::{exc}"})
        print(f"  processed {name}", flush=True)

    if not clips:
        print(json.dumps({"status": "BLOCKED_THERMAL_IM_INTERVALS",
                          "error": "no clip could be decoded"}, indent=2))
        return 2

    group_ids = [clip["recording_group_id"] for clip in clips]
    split = tim.split_groups(group_ids, args.holdout_groups, seed=args.split_seed)

    frames: list[np.ndarray] = []
    lineage: list[dict] = []
    for clip in clips:
        role = "HN_HOLDOUT_EVAL" if clip["recording_group_id"] in split["holdout_groups"] else "HN_TRAIN_POOL"
        if clip["admitted_frame_count"] == 0:
            continue
        frames.append(clip["frames_intensity"])
        for row in clip["lineage"]:
            enriched = dict(row)
            enriched["source_split_group"] = clip["recording_group_id"]
            enriched["training_eval_role"] = role
            lineage.append(enriched)

    pool = np.concatenate(frames, axis=0) if frames else np.zeros((0, 62, 80), dtype=np.float32)
    roles = np.asarray([row["training_eval_role"] for row in lineage], dtype=object)
    groups = np.asarray([row["recording_group_id"] for row in lineage], dtype=object)
    clip_ids = np.asarray([row["clip_id"] for row in lineage], dtype=object)

    out_dir = work_root / "thermal_im"
    np.savez_compressed(
        out_dir / "hard_negative_pool.npz",
        frames_intensity=pool,
        training_eval_role=roles.astype(str),
        recording_group_id=groups.astype(str),
        clip_id=clip_ids.astype(str),
        source_frame_index=np.asarray([row["source_frame_index"] for row in lineage], dtype=np.int64),
    )
    (out_dir / "hard_negative_lineage.jsonl").write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in lineage), encoding="utf-8"
    )

    ledger = [{
        "clip_id": clip["clip_id"],
        "archive_name": clip["archive_name"],
        "recording_group_id": clip["recording_group_id"],
        "decoded_frame_count": clip["decoded_frame_count"],
        "annotation_status": clip["annotation_status"],
        "annotation_interval_count": clip["annotation_interval_count"],
        "admitted_frame_count": clip["admitted_frame_count"],
        "interval_ledger": clip["interval_ledger"],
    } for clip in clips]

    train_count = int((roles == "HN_TRAIN_POOL").sum()) if lineage else 0
    holdout_count = int((roles == "HN_HOLDOUT_EVAL").sum()) if lineage else 0
    manifest = {
        "schema_version": "safenest.thermal.tv2_candidate_a.thermal_im_hard_negative_manifest.v1",
        "source_id": tim.SOURCE_ID,
        "identity_status": receipt["identity_status"],
        "mapped_class": "HUMAN_NORMAL",
        "semantic_subtype": tim.SEMANTIC_SUBTYPE,
        "event_provenance": tim.EVENT_PROVENANCE,
        "mapping_rule_id": tim.MAPPING_RULE_ID,
        "fall_proxy_contribution": tim.FALL_PROXY_FROM_THERMAL_IM,
        "not_human_contribution": tim.NOT_HUMAN_FROM_THERMAL_IM,
        "admitted_tokens": sorted(f"sit {obj}" for obj in tim.ADMITTED_SIT_OBJECTS),
        "timing_contract": {"native_fps": tim.NATIVE_FPS,
                            "frame_coverage_rule": "FULL_SAMPLE_PERIOD_INSIDE_INTERVAL",
                            "outside_annotated_intervals": "UNLABELED_NOT_USED"},
        "geometry_profile": "TIM_FIXED_ASPECT_CROP_BILINEAR_V1",
        "split": split,
        "clip_count": len(clips),
        "clips_with_admitted_frames": sum(1 for clip in clips if clip["admitted_frame_count"]),
        "total_decoded_frames": sum(clip["decoded_frame_count"] for clip in clips),
        "admitted_frame_total": int(pool.shape[0]),
        "hn_train_pool_frames": train_count,
        "hn_holdout_eval_frames": holdout_count,
        "acquisition_failures": failures,
        "clip_ledger": ledger,
    }
    (out_dir / "hard_negative_manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    print(json.dumps({
        "status": "OK",
        "clip_count": manifest["clip_count"],
        "clips_with_admitted_frames": manifest["clips_with_admitted_frames"],
        "total_decoded_frames": manifest["total_decoded_frames"],
        "admitted_frame_total": manifest["admitted_frame_total"],
        "hn_train_pool_frames": train_count,
        "hn_holdout_eval_frames": holdout_count,
        "train_groups": split["train_groups"],
        "holdout_groups": split["holdout_groups"],
        "acquisition_failures": failures,
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
