#!/usr/bin/env python3
"""Run the Thermal V2 Candidate A data-corrective prototype experiment.

Stages
------
``representation``  A0 only, 2 relative-appearance operators x 2 head variants, seed 42.
                    Selects the representation and head using PUBLIC_SDT DEVELOPMENT.
``ratio``           A1 at bounded Thermal-IM hard-negative ratios, seed 42.
``final``           A0 / A1(selected ratio) / A0R(prior-shift control) over multiple seeds.

``LOCKED_PUBLIC_TEST`` is never referenced. PUBLIC_SDT DEVELOPMENT is the only selection set.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import platform
import sys
import time

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from datasets.thermal import tv2_ca_model as arch  # noqa: E402
from datasets.thermal import tv2_ca_representation as rep  # noqa: E402
from datasets.thermal import tv2_ca_runner as runner  # noqa: E402
from datasets.thermal import tv2_ca_sdt_source as sdt  # noqa: E402

DEFAULT_SEEDS = (42, 7, 1337)


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


def make_run_id(step: dict) -> str:
    return (f"{step['arm']}_hn{int(round(step['ratio'] * 100)):03d}"
            f"_{step['normalization']}_{step['head']}_seed{step['seed']}")


def summarize(record: dict) -> str:
    dev = record["result"]["sdt_development"]
    primary = dev["primary_metric"]
    line = (
        f"{record['run_id']:<44s} params={record['result']['parameter_count']:>6d} "
        f"macroF1={dev['macro_f1']:.4f} "
        f"N->F={primary['count']:>4d}/{primary['denominator']} ({primary['rate']*100:.2f}%) "
        f"FALLrecall={dev['per_class']['HUMAN_FALL_PROXY']['recall']:.4f}"
    )
    hn = record["result"].get("thermal_im_holdout_hard_negative")
    if hn:
        line += (f" | TIM-HN n={hn['hard_negative_frame_count']} "
                 f"acceptNORMAL={hn['normal_acceptance_rate']*100:.1f}% "
                 f"falseFALL={hn['fall_proxy_false_positive_rate']*100:.1f}%")
    return line


def main() -> int:
    parser = argparse.ArgumentParser(description="Thermal V2 Candidate A prototype experiment")
    parser.add_argument("--canonical-root", required=True, help="T-A6 canonical artifact root (read-only)")
    parser.add_argument("--work-root", required=True, help="Non-Git working root")
    parser.add_argument("--stage", required=True, choices=("representation", "ratio", "final"))
    parser.add_argument("--normalization", default=rep.NORM_ROBUST, choices=list(rep.NORMALIZATION_CANDIDATES))
    parser.add_argument("--head-variant", default=arch.HEAD_SPATIAL, choices=list(arch.HEAD_VARIANTS))
    parser.add_argument("--ratios", default="0.10,0.25")
    parser.add_argument("--final-ratio", type=float, default=0.25)
    parser.add_argument("--seeds", default=",".join(str(seed) for seed in DEFAULT_SEEDS))
    parser.add_argument("--verify-checksums", action="store_true")
    parser.add_argument("--export-arm", default="", help="Arm whose per-seed checkpoints are exported")
    parser.add_argument(
        "--arms",
        default="",
        help="Optional comma-separated arm filter (A0,A1,A0R). Empty = all planned arms.",
    )
    args = parser.parse_args()

    canonical_root = Path(args.canonical_root)
    work_root = Path(args.work_root)
    work_root.mkdir(parents=True, exist_ok=True)
    results_path = work_root / f"candidate_a_results_{args.stage}.jsonl"
    artifact_dir = work_root / "artifacts"
    artifact_dir.mkdir(parents=True, exist_ok=True)

    plan: list[dict] = []
    if args.stage == "representation":
        for normalization in rep.NORMALIZATION_CANDIDATES:
            for head in arch.HEAD_VARIANTS:
                plan.append({"arm": runner.ARM_A0, "ratio": 0.0, "normalization": normalization,
                             "head": head, "seed": 42})
    elif args.stage == "ratio":
        for ratio in [float(item) for item in args.ratios.split(",") if item.strip()]:
            plan.append({"arm": runner.ARM_A1, "ratio": ratio, "normalization": args.normalization,
                         "head": args.head_variant, "seed": 42})
    else:
        for seed in [int(item) for item in args.seeds.split(",") if item.strip()]:
            plan.append({"arm": runner.ARM_A0, "ratio": 0.0, "normalization": args.normalization,
                         "head": args.head_variant, "seed": seed})
            plan.append({"arm": runner.ARM_A1, "ratio": args.final_ratio,
                         "normalization": args.normalization, "head": args.head_variant, "seed": seed})
            plan.append({"arm": runner.ARM_A0R, "ratio": args.final_ratio,
                         "normalization": args.normalization, "head": args.head_variant, "seed": seed})

    if args.arms.strip():
        allowed = {item.strip() for item in args.arms.split(",") if item.strip()}
        plan = [step for step in plan if step["arm"] in allowed]

    completed_ids = existing_run_ids(results_path)
    caches: dict[str, dict] = {}

    def get_cache(normalization: str) -> dict:
        if normalization not in caches:
            print(f"[cache] materializing normalized memmaps for {normalization}", flush=True)
            train = runner.build_sdt_cache(work_root, canonical_root, "TRAIN", normalization,
                                          verify_checksums=args.verify_checksums)
            dev = runner.build_sdt_cache(work_root, canonical_root, "DEVELOPMENT", normalization,
                                        verify_checksums=args.verify_checksums)
            pool = runner.build_thermal_im_cache(work_root, normalization)
            hn_eval = None
            if pool is not None:
                mask = pool["role"] == "HN_HOLDOUT_EVAL"
                hn_eval = pool["frames"][np.flatnonzero(mask)] if mask.any() else None
            caches[normalization] = {"train": train, "dev": dev, "pool": pool, "hn_eval": hn_eval}
        return caches[normalization]

    executed = 0
    skipped = 0
    exported = 0
    for step in plan:
        run_id = make_run_id(step)
        checkpoint = artifact_dir / f"{run_id}.keras"
        want_export = bool(args.export_arm) and step["arm"] == args.export_arm
        already = run_id in completed_ids
        if already and not (want_export and not checkpoint.is_file()):
            print(f"[skip] {run_id} already recorded", flush=True)
            skipped += 1
            continue

        normalization = step["normalization"]
        cache = get_cache(normalization)
        arm_data = runner.build_arm(cache["train"], cache["pool"], step["arm"],
                                   step["ratio"], step["seed"])
        started = time.time()
        result, model = runner.train_and_evaluate(
            arm_data,
            cache["train"]["frames"],
            cache["pool"]["frames"] if cache["pool"] is not None else None,
            cache["dev"]["frames"],
            cache["dev"]["labels"],
            cache["hn_eval"],
            step["head"],
            step["seed"],
        )
        record = {
            "run_id": run_id,
            "stage": args.stage,
            "arm": step["arm"],
            "hn_ratio": step["ratio"],
            "normalization": normalization,
            "head_variant": step["head"],
            "seed": step["seed"],
            "wall_clock_seconds": round(time.time() - started, 2),
            "training_membership": arm_data["membership"],
            "representation_contract": rep.representation_contract(normalization),
            "architecture_contract": arch.architecture_contract(step["head"], result["parameter_count"]),
            "training_policy": runner.TRAINING_POLICY,
            "locked_test_policy": sdt.LOCKED_TEST_POLICY,
            "sdt_artifact_identity": {
                "TRAIN": cache["train"]["identity"],
                "DEVELOPMENT": cache["dev"]["identity"],
            },
            "result": result,
        }
        if want_export:
            model.save(checkpoint)
            record["artifact"] = {
                "path": checkpoint.name,
                "sha256": sha256_file(checkpoint),
                "size_bytes": checkpoint.stat().st_size,
                "format": "keras_v3_float32",
            }
            exported += 1
        if already:
            record["jsonl_append"] = "SKIPPED_EXISTING_RUN_ID"
            print(f"[export-only] {run_id} artifact={checkpoint.name}", flush=True)
        else:
            emit(record, results_path)
            completed_ids.add(run_id)
        executed += 1
        print(summarize(record), flush=True)

    environment_path = work_root / f"candidate_a_environment_{args.stage}.json"
    if not environment_path.is_file():
        environment = {
            "python": sys.version.split()[0],
            "platform": platform.platform(),
            "machine": platform.machine(),
            "numpy": np.__version__,
        }
        environment_path.write_text(
            json.dumps(environment, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
    print(json.dumps({"status": "OK", "stage": args.stage, "planned": len(plan),
                      "executed": executed, "skipped": skipped, "exported": exported,
                      "results": str(results_path)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
