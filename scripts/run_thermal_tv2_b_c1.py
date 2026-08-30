#!/usr/bin/env python3
"""Run the Thermal V2 C1 matched pooled-MLP control and Candidate B comparison.

PUBLIC_SDT TRAIN/DEVELOPMENT only. LOCKED_PUBLIC_TEST is never referenced.
Thermal-IM is not loaded.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
import time

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from datasets.thermal import tv2_b_c1_runner as exp  # noqa: E402
from datasets.thermal import tv2_ca_representation as rep  # noqa: E402
from datasets.thermal import tv2_ca_runner as ca  # noqa: E402
from datasets.thermal import tv2_ca_sdt_source as sdt  # noqa: E402

FAMILIES = (exp.FAMILY_C1, exp.FAMILY_B)


def sha256_file(path: Path, chunk: int = 1 << 20) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(chunk), b""):
            digest.update(block)
    return digest.hexdigest()


def emit(record: dict, results_path: Path) -> None:
    with results_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True) + "\n")


def existing_run_ids(results_path: Path) -> set[str]:
    if not results_path.is_file():
        return set()
    ids: set[str] = set()
    for line in results_path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            ids.add(json.loads(line)["run_id"])
    return ids


def summarize(record: dict) -> str:
    dev = record["result"]["sdt_development"]
    primary = dev["primary_metric"]
    return (
        f"{record['run_id']:<36s} params={record['result']['parameter_count']:>6d} "
        f"macroF1={dev['macro_f1']:.4f} "
        f"N->F={primary['count']:>4d}/{primary['denominator']} ({primary['rate']*100:.2f}%) "
        f"FALLrecall={dev['per_class']['HUMAN_FALL_PROXY']['recall']:.4f}"
    )


def run_smoke() -> int:
    reports = []
    for family in FAMILIES:
        report = exp.smoke_family(family)
        reports.append(report)
        print(json.dumps(report, sort_keys=True), flush=True)
    print(json.dumps({"status": "OK", "stage": "smoke", "families": reports}, indent=2))
    return 0


def run_train(args: argparse.Namespace) -> int:
    canonical_root = Path(args.canonical_root)
    work_root = Path(args.work_root)
    work_root.mkdir(parents=True, exist_ok=True)
    artifact_dir = work_root / "artifacts"
    artifact_dir.mkdir(parents=True, exist_ok=True)
    results_path = work_root / "candidate_b_c1_results.jsonl"
    completed = existing_run_ids(results_path)

    print(f"[cache] SDT TRAIN/DEVELOPMENT {exp.NORMALIZATION}", flush=True)
    train = ca.build_sdt_cache(
        work_root, canonical_root, "TRAIN", exp.NORMALIZATION,
        verify_checksums=args.verify_checksums,
    )
    dev = ca.build_sdt_cache(
        work_root, canonical_root, "DEVELOPMENT", exp.NORMALIZATION,
        verify_checksums=args.verify_checksums,
    )

    families = [item.strip() for item in args.families.split(",") if item.strip()]
    seeds = [int(item) for item in args.seeds.split(",") if item.strip()]
    executed = skipped = exported = 0

    for family in families:
        for seed in seeds:
            rid = exp.run_id(family, seed)
            checkpoint = artifact_dir / f"{rid}.keras"
            if rid in completed and checkpoint.is_file():
                print(f"[skip] {rid} already recorded", flush=True)
                skipped += 1
                continue
            arm_data = ca.build_arm(train, None, ca.ARM_A0, 0.0, seed)
            started = time.time()
            result, model = exp.train_and_evaluate(
                arm_data, train["frames"], dev["frames"], dev["labels"], family, seed,
            )
            record = {
                "run_id": rid,
                "stage": "matched_architecture_comparison",
                "family": family,
                "hn_ratio": 0.0,
                "thermal_im_used": False,
                "normalization": exp.NORMALIZATION,
                "seed": seed,
                "wall_clock_seconds": round(time.time() - started, 2),
                "training_membership": arm_data["membership"],
                "representation_contract": rep.representation_contract(exp.NORMALIZATION),
                "architecture_contract": exp.architecture_contract(family, result["parameter_count"]),
                "training_policy": ca.TRAINING_POLICY,
                "locked_test_policy": sdt.LOCKED_TEST_POLICY,
                "sdt_artifact_identity": {
                    "TRAIN": train["identity"],
                    "DEVELOPMENT": dev["identity"],
                },
                "result": result,
            }
            model.save(checkpoint)
            record["artifact"] = {
                "path": checkpoint.name,
                "sha256": sha256_file(checkpoint),
                "size_bytes": checkpoint.stat().st_size,
                "format": "keras_v3_float32",
            }
            exported += 1
            if rid not in completed:
                emit(record, results_path)
                completed.add(rid)
            executed += 1
            print(summarize(record), flush=True)

    print(json.dumps({
        "status": "OK",
        "stage": "train",
        "executed": executed,
        "skipped": skipped,
        "exported": exported,
        "results": str(results_path),
    }, indent=2))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Thermal V2 C1 / Candidate B matched experiment")
    parser.add_argument("--canonical-root", required=True)
    parser.add_argument("--work-root", required=True)
    parser.add_argument("--stage", required=True, choices=("smoke", "train"))
    parser.add_argument("--families", default="C1,B")
    parser.add_argument("--seeds", default="42,7,1337")
    parser.add_argument("--verify-checksums", action="store_true")
    args = parser.parse_args()
    if args.stage == "smoke":
        return run_smoke()
    return run_train(args)


if __name__ == "__main__":
    raise SystemExit(main())
