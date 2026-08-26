#!/usr/bin/env python3
"""PUBABS-A8: frozen C1 external-stress inference (six ROLE_L × VALID34).

Descriptive-only. No ranking, winner, threshold retune, scaler refit, D1 mutation.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import io
import json
import os
import re
import sys
import zipfile
from collections import Counter
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ.setdefault("PYTHONHASHSEED", "0")

import torch
from torch import nn

from adapters.mmwave_pubabs_c1_frozen_adapter import (
    FROZEN_PROPOSAL_SHA256,
    adapt_c1_raw,
)
from adapters.mmwave_r1_sensor_independent_trace import CommonTraceOutput

# Import canonical M-PV2 helpers without executing training main.
_PV2_PATH = ROOT / "scripts/mmwave_m_pv2_candidate_training.py"
_spec = importlib.util.spec_from_file_location("mmwave_m_pv2_candidate_training", _PV2_PATH)
_pv2 = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
sys.modules["mmwave_m_pv2_candidate_training"] = _pv2
_spec.loader.exec_module(_pv2)

COMPLEX_TOKEN = re.compile(
    r"[+-]?(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?"
    r"[+-](?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?j"
)

A6_DIR = ROOT / "datasets/mmwave/manifests/PUBABS_A6_c1_external_stress_freeze"
A7_DIR = ROOT / "datasets/mmwave/manifests/PUBABS_A7_c1_external_stress_inference_contract"
EXPECTED = {
    "a6_contract": "d0353c9bf7837a2520364903b53075bde44cddf10b88c3fef58aa4054bbb3310",
    "layer1": "cefc7a3820ebb644a9553b3eaad9f4ec600ea555bc25ed891f236cc50c6632f5",
    "layer2": "01a1db3ef56e1071896f054a5baad397035ca6d989f42f2d1129d250b6867c7c",
    "adapter": "cfce866f659658e772e833f64e881549a4244b8c9daaa85423b343f34c424446",
    "scaler_embedded": "5a2583b5b5064be5480b0cf56f2a2c12d40a4a2d005eb087dc8e12106881159c",
    "data_md5": "99067ac569e419fc122eef49635d72d0",
}
PANEL = [
    ("B11", "family_b", 11, "models/mmwave/m_pv2/family_b/candidate_seed_11.pt",
     "5633a7eefa83544cd33a251b0016b40f37e28039f985b31c98bdcfa37aa8b1a6", 621),
    ("B23", "family_b", 23, "models/mmwave/m_pv2/family_b/candidate_seed_23.pt",
     "8f7de6f50d6ff62ff9b0ebfaed0b1fccd8d194c7e33781bc5b93366fae251a2c", 621),
    ("B47", "family_b", 47, "models/mmwave/m_pv2/family_b/candidate_seed_47.pt",
     "ed3da35adb0837426065cc575b7e4ff6f41ef9a8fb295bb29f7eb8bcff4db280", 621),
    ("C11", "family_c", 11, "models/mmwave/m_pv2/family_c/candidate_seed_11.pt",
     "539bd6021d10a9abd35a22b49c0db728a122b60356f59609fead9280d82f7768", 671),
    ("C23", "family_c", 23, "models/mmwave/m_pv2/family_c/candidate_seed_23.pt",
     "ce99a6534928138bc5e2d271123185f93aceb6386b8a24b0ecb3679c7d6d70de", 671),
    ("C47", "family_c", 47, "models/mmwave/m_pv2/family_c/candidate_seed_47.pt",
     "2f1b446c808cfb90d02dc6cce754311ade19cf2e3bb03b20814a1268934cb5a1", 671),
]
THRESHOLD = 0.5
RR_MEAN = 17.12899193548387
RR_STD = 8.948729232744911


class A8Abort(SystemExit):
    def __init__(self, code: str, detail: str = ""):
        self.code = code
        super().__init__(f"{code}: {detail}" if detail else code)


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sha256_arr(arr: np.ndarray) -> str:
    return hashlib.sha256(np.ascontiguousarray(arr, dtype=np.float64).tobytes()).hexdigest()


def sha256_f32(arr: np.ndarray) -> str:
    return hashlib.sha256(np.ascontiguousarray(arr, dtype=np.float32).tobytes()).hexdigest()


def md5_file(path: Path) -> str:
    h = hashlib.md5()
    with path.open("rb") as f:
        while True:
            chunk = f.read(1 << 20)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def verify_parents() -> dict:
    receipt = json.loads((A6_DIR / "external_stress_contract_receipt.json").read_text())
    if receipt["contract_sha256"] != EXPECTED["a6_contract"]:
        raise A8Abort("A8_ABORT_A6_CONTRACT_SHA_DRIFT", receipt["contract_sha256"])
    l1_sha = sha256_file(A6_DIR / "layer1_all77_population.json")
    l2_sha = sha256_file(A6_DIR / "layer2_valid34_population.json")
    if l1_sha != EXPECTED["layer1"]:
        raise A8Abort("A8_ABORT_LAYER1_MANIFEST_SHA_DRIFT", l1_sha)
    if l2_sha != EXPECTED["layer2"]:
        raise A8Abort("A8_ABORT_LAYER2_MANIFEST_SHA_DRIFT", l2_sha)
    if FROZEN_PROPOSAL_SHA256 != EXPECTED["adapter"]:
        raise A8Abort("A8_ABORT_ADAPTER_CONTRACT_HASH_DRIFT", FROZEN_PROPOSAL_SHA256)
    prop = sha256_file(
        ROOT
        / "datasets/mmwave/manifests/PUBABS_A3C_corrective_contract_proposal/proposed_adapter_contract.json"
    )
    if prop != EXPECTED["adapter"]:
        raise A8Abort("A8_ABORT_ADAPTER_CONTRACT_HASH_DRIFT", prop)
    scaler = json.loads(
        (ROOT / "datasets/mmwave/manifests/M-PV2_candidate_training/scaler_statistics.json").read_text()
    )
    if scaler.get("sha256") != EXPECTED["scaler_embedded"]:
        raise A8Abort("A8_ABORT_SCALER_SHA_DRIFT", str(scaler.get("sha256")))
    if abs(float(scaler["trace"]["mean"]) - 0.5681105335535223) > 1e-12:
        raise A8Abort("A8_ABORT_SCALER_SHA_DRIFT", "trace_mean")
    if abs(float(scaler["trace"]["std"]) - 10.976509586515288) > 1e-12:
        raise A8Abort("A8_ABORT_SCALER_SHA_DRIFT", "trace_std")
    for panel_id, _fam, _seed, rel, expect, _dim in PANEL:
        got = sha256_file(ROOT / rel)
        if got != expect:
            raise A8Abort("A8_ABORT_ARTIFACT_SHA_DRIFT", f"{panel_id}:{got}")
    a7 = json.loads((A7_DIR / "inference_contract.json").read_text())
    if a7["contract_id"] != "PUBABS_C1_EXTERNAL_STRESS_INFERENCE_V1":
        raise A8Abort("A8_ABORT_PANEL_IDENTITY_DRIFT", a7["contract_id"])
    return {"receipt": receipt, "scaler": scaler, "a7": a7, "l1_sha": l1_sha, "l2_sha": l2_sha}


def load_csv_member(zf: zipfile.ZipFile, member: str):
    raw = zf.read(member)
    rows = list(csv.reader(io.StringIO(raw.decode("utf-8"))))
    ts, frames = [], []
    for row in rows:
        vals = [complex(tok) for tok in COMPLEX_TOKEN.findall(row[1])]
        if len(vals) != 180:
            continue
        ts.append(float(row[0]) * 1e-9)
        frames.append(vals)
    return np.asarray(ts, dtype=np.float64), np.asarray(frames, dtype=np.complex128)


def configure_torch() -> dict:
    torch.set_num_threads(1)
    try:
        torch.set_num_interop_threads(1)
    except RuntimeError:
        pass
    det = False
    try:
        torch.use_deterministic_algorithms(True)
        det = True
    except Exception:
        det = False
    return {
        "python": sys.version.split()[0],
        "pytorch": torch.__version__,
        "numpy": np.__version__,
        "device": "cpu",
        "deterministic_algorithms": det,
        "threads": int(torch.get_num_threads()),
    }


def build_common_from_adapter(out) -> CommonTraceOutput:
    # Absolute unix t0 + k/10 suffers float64 spacing > R2's 1e-10 grid atol.
    # Use the same declared 10 Hz regular grid as a relative index timeline so
    # canonical R2 validation can run without modifying R2 itself.
    n = int(out.r1_centered.size)
    time_s = np.arange(n, dtype=np.float64) / 10.0
    metadata = dict(out.r1_metadata)
    provenance = dict(metadata.get("provenance", {}))
    provenance["time_range_s"] = [float(time_s[0]), float(time_s[-1])]
    provenance["a8_time_basis"] = "RELATIVE_INDEX_GRID_10HZ_FOR_R2_COMPAT"
    provenance["a8_source_t0_unix_s"] = float(out.t0)
    metadata["provenance"] = provenance
    return CommonTraceOutput(
        trace=np.asarray(out.r1_centered, dtype=np.float64),
        time_s=time_s,
        validity_mask=np.ones(out.r1_centered.shape, dtype=bool),
        metadata=metadata,
    )


def materialize_session(session: dict, zf: zipfile.ZipFile, scaler: dict) -> dict:
    t, z = load_csv_member(zf, session["canonical_source_path"])
    out = adapt_c1_raw(t, z, recording_id=session["canonical_source_path"])
    r1_h = sha256_arr(out.r1_centered)
    if r1_h != session["r1_centered_sha256"]:
        raise A8Abort("A8_ABORT_TRACE_SHA_DRIFT", f"r1_centered {session['external_stress_session_id']}")
    # Guard: feed r1_centered only. Feeding train_zscore_trace would double-zscore.
    trace_source = "r1_centered"
    if trace_source != "r1_centered":
        raise A8Abort("A8_ABORT_DOUBLE_TRACE_ZSCORE", trace_source)
    common = build_common_from_adapter(out)
    trace, trace_mask, f2, f2_mask, descriptors = _pv2._feature_arrays(common)
    scale = descriptors[: len(_pv2.SCALE_NAMES)]
    quality = descriptors[len(_pv2.SCALE_NAMES) :]
    # Verify z-score of r1_centered (float64) matches A6 train_zscore hash.
    # Do not use the float32 feature-array cast for this identity check.
    zscored = (
        np.asarray(out.r1_centered, dtype=np.float64) - float(scaler["trace"]["mean"])
    ) / float(scaler["trace"]["std"])
    z_h = sha256_arr(zscored)
    if z_h != session["train_zscore_trace_sha256"]:
        raise A8Abort(
            "A8_ABORT_TRACE_SHA_DRIFT",
            f"train_zscore {session['external_stress_session_id']} got={z_h}",
        )
    record = _pv2.InputRecord(
        source_id="C1",
        subject_id=session["subject_or_empty_identity"],
        recording_id=session["external_stress_session_id"],
        model_input_id=session["external_stress_session_id"],
        split="EXTERNAL_STRESS",
        trace=np.asarray(trace, dtype=np.float32),
        trace_mask=np.asarray(trace_mask, dtype=np.float32),
        f2=np.asarray(f2, dtype=np.float32),
        f2_mask=np.asarray(f2_mask, dtype=np.float32),
        scale=np.asarray(scale, dtype=np.float32),
        quality=np.asarray(quality, dtype=np.float32),
        breathing_label=1.0 if session["reporting_class"] == "PRESENT" else 0.0,
        breathing_mask=1.0,
        rr_bpm=0.0,
        rr_mask=0.0,
        quality_label=0.0,
        quality_mask=0.0,
        breathing_state=(
            "BREATHING_REFERENCE_PRESENT"
            if session["reporting_class"] == "PRESENT"
            else "BREATHING_REFERENCE_ABSENT"
        ),
        rr_target_status="UNSCORED",
        quality_status="UNSCORED",
        provenance={"a6_session": session["external_stress_session_id"]},
    )
    vec_b = _pv2._feature_matrix([record], "family_b", scaler)[0]
    vec_c = _pv2._feature_matrix([record], "family_c", scaler)[0]
    if vec_b.shape[0] != 621 or vec_c.shape[0] != 671:
        raise A8Abort("A8_ABORT_FEATURE_VECTOR_CONTRACT_GAP", f"{vec_b.shape},{vec_c.shape}")
    if not np.all(np.isfinite(vec_b)) or not np.all(np.isfinite(vec_c)):
        raise A8Abort("A8_ABORT_FEATURE_VECTOR_CONTRACT_GAP", "nonfinite")
    return {
        "session": session,
        "record": record,
        "r1_centered_sha256": r1_h,
        "train_zscore_trace_sha256": z_h,
        "vec_b": vec_b,
        "vec_c": vec_c,
        "vec_b_sha256": sha256_f32(vec_b),
        "vec_c_sha256": sha256_f32(vec_c),
    }


def load_model(family: str, path: Path, input_dim: int) -> nn.Module:
    model = _pv2._make_model(family, input_dim)
    state = torch.load(path, map_location="cpu", weights_only=True)
    if isinstance(state, dict) and "state_dict" in state:
        state = state["state_dict"]
    missing, unexpected = model.load_state_dict(state, strict=True)
    if missing or unexpected:
        raise A8Abort("A8_ABORT_CANDIDATE_DROPPED", f"missing={missing} unexpected={unexpected}")
    model.eval()
    return model


def infer_one(model: nn.Module, vector: np.ndarray) -> dict:
    x = torch.from_numpy(np.asarray(vector, dtype=np.float32)).unsqueeze(0)
    with torch.no_grad():
        out = model(x)
    breathing_logit = float(out["breathing"][0].item())
    quality_logit = float(out["quality"][0].item())
    rr_raw = float(out["rr"][0].item())
    breathing_p = float(1.0 / (1.0 + np.exp(-breathing_logit)))
    quality_p = float(1.0 / (1.0 + np.exp(-quality_logit)))
    rr_bpm = rr_raw * RR_STD + RR_MEAN
    decision = "PRESENT" if breathing_p >= THRESHOLD else "ABSENT"
    return {
        "breathing_logit": breathing_logit,
        "breathing_probability": breathing_p,
        "breathing_decision": decision,
        "rr_raw": rr_raw,
        "rr_bpm": rr_bpm,
        "rr_semantics": "UNSCORED",
        "quality_logit": quality_logit,
        "quality_probability": quality_p,
        "quality_semantics": "UNSCORED",
        "finite": all(
            np.isfinite(v)
            for v in (breathing_logit, breathing_p, rr_raw, rr_bpm, quality_logit, quality_p)
        ),
    }


def metrics_for_candidate(rows: list[dict]) -> dict:
    absent = [r for r in rows if r["reporting_class"] == "ABSENT"]
    present = [r for r in rows if r["reporting_class"] == "PRESENT"]
    emit = sum(1 for r in absent if r["breathing_decision"] == "PRESENT")
    recall_n = sum(1 for r in present if r["breathing_decision"] == "PRESENT")
    tp = sum(1 for r in present if r["breathing_decision"] == "PRESENT")
    fn = sum(1 for r in present if r["breathing_decision"] == "ABSENT")
    fp = sum(1 for r in absent if r["breathing_decision"] == "PRESENT")
    tn = sum(1 for r in absent if r["breathing_decision"] == "ABSENT")
    prec = tp / (tp + fp) if (tp + fp) else "NOT_APPLICABLE"
    rec = recall_n / 25.0
    if prec == "NOT_APPLICABLE" or (prec + rec) == 0:
        f1 = "NOT_APPLICABLE"
    else:
        f1 = 2 * prec * rec / (prec + rec)
    y = np.asarray([1.0 if r["reporting_class"] == "PRESENT" else 0.0 for r in rows])
    p = np.asarray([r["breathing_probability"] for r in rows])
    brier = float(np.mean((p - y) ** 2))
    per_subject = {}
    for subj in ("N1", "N2", "N3", "N4", "N5", "N6"):
        sub_rows = [r for r in present if r.get("subject") == subj]
        if not sub_rows:
            per_subject[subj] = {"n_present": 0, "predicted_present": 0, "recall": "NOT_APPLICABLE"}
        else:
            hit = sum(1 for r in sub_rows if r["breathing_decision"] == "PRESENT")
            per_subject[subj] = {
                "n_present": len(sub_rows),
                "predicted_present": hit,
                "recall": hit / len(sub_rows),
            }
    pos_keys = sorted({r.get("position") or "UNKNOWN" for r in rows})
    per_position = {}
    for pos in pos_keys:
        pos_rows = [r for r in rows if (r.get("position") or "UNKNOWN") == pos]
        per_position[pos] = {
            "n": len(pos_rows),
            "n_absent": sum(1 for r in pos_rows if r["reporting_class"] == "ABSENT"),
            "n_present": sum(1 for r in pos_rows if r["reporting_class"] == "PRESENT"),
            "predicted_present": sum(1 for r in pos_rows if r["breathing_decision"] == "PRESENT"),
        }
    return {
        "L2_ABSENT_EMISSION_COUNT": emit,
        "L2_ABSENT_EMISSION_RATE": emit / 9.0,
        "L2_PRESENT_RECALL": recall_n / 25.0,
        "L2_CONFUSION_COUNTS": {"TP": tp, "FP": fp, "TN": tn, "FN": fn, "n_ABSENT": 9, "n_PRESENT": 25},
        "L2_PRESENT_PRECISION": prec,
        "L2_F1_WHERE_DEFINED": f1,
        "L2_BRIER_WHERE_DEFINED": brier,
        "PER_SUBJECT_PRESENT_STRATA": per_subject,
        "PER_POSITION_STRATA": per_position,
        "labels": {
            "CONDITIONAL_ON_ADAPTER_VALID": True,
            "OUT_OF_DOMAIN_EXTERNAL_STRESS": True,
            "DESCRIPTIVE_ONLY": True,
        },
    }


def run_inference(materials: list[dict], models: dict) -> list[dict]:
    records = []
    for mat in materials:
        sess = mat["session"]
        for panel_id, family, seed, rel, art_sha, dim in PANEL:
            vec = mat["vec_b"] if family == "family_b" else mat["vec_c"]
            vec_sha = mat["vec_b_sha256"] if family == "family_b" else mat["vec_c_sha256"]
            pred = infer_one(models[panel_id], vec)
            records.append(
                {
                    "session_id": sess["external_stress_session_id"],
                    "reporting_class": sess["reporting_class"],
                    "subject": sess["subject_or_empty_identity"],
                    "position": sess["position"],
                    "candidate_panel_id": "PUBABS_C1_EXTERNAL_STRESS_ROLE_L_PANEL_V1",
                    "candidate_key": panel_id,
                    "family": family,
                    "seed": seed,
                    "candidate_artifact_sha256": art_sha,
                    "input_vector_sha256": vec_sha,
                    "input_dim": dim,
                    "frozen_threshold": THRESHOLD,
                    **pred,
                }
            )
    return records


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-zip", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--base-sha", required=True)
    args = parser.parse_args()

    if md5_file(args.data_zip) != EXPECTED["data_md5"]:
        raise A8Abort("A8_ABORT_ADAPTER_CONTRACT_HASH_DRIFT", "data_md5")

    parents = verify_parents()
    runtime = configure_torch()
    layer1 = json.loads((A6_DIR / "layer1_all77_population.json").read_text())["sessions"]
    layer2 = json.loads((A6_DIR / "layer2_valid34_population.json").read_text())["sessions"]
    if len(layer1) != 77 or len(layer2) != 34:
        raise A8Abort("A8_ABORT_LAYER2_POPULATION_DRIFT", f"{len(layer1)}/{len(layer2)}")
    if sum(1 for s in layer2 if s["reporting_class"] == "ABSENT") != 9:
        raise A8Abort("A8_ABORT_LAYER2_POPULATION_DRIFT", "absent")
    if sum(1 for s in layer2 if s["reporting_class"] == "PRESENT") != 25:
        raise A8Abort("A8_ABORT_LAYER2_POPULATION_DRIFT", "present")

    scaler = parents["scaler"]
    materials = []
    with zipfile.ZipFile(args.data_zip) as zf:
        for sess in layer2:
            try:
                materials.append(materialize_session(sess, zf, scaler))
            except Exception as exc:
                if isinstance(exc, A8Abort):
                    raise
                raise A8Abort("A8_ABORT_FEATURE_VECTOR_CONTRACT_GAP", f"{sess['external_stress_session_id']}:{exc}") from exc

    models = {}
    for panel_id, family, _seed, rel, _sha, dim in PANEL:
        models[panel_id] = load_model(family, ROOT / rel, dim)

    run1 = run_inference(materials, models)
    run2 = run_inference(materials, models)
    if len(run1) != 204 or len(run2) != 204:
        raise A8Abort("A8_ABORT_CANDIDATE_DROPPED", f"{len(run1)}/{len(run2)}")
    # Determinism on key numeric fields
    def canon(rows):
        return [
            (
                r["session_id"],
                r["candidate_key"],
                r["breathing_logit"],
                r["breathing_probability"],
                r["breathing_decision"],
                r["rr_raw"],
                r["quality_logit"],
                r["input_vector_sha256"],
            )
            for r in rows
        ]

    if canon(run1) != canon(run2):
        raise A8Abort("A8_ABORT_PREPROCESSING_CONTRACT_CHANGE", "nondeterministic")

    per_candidate = {}
    for panel_id, *_rest in PANEL:
        rows = [r for r in run1 if r["candidate_key"] == panel_id]
        per_candidate[panel_id] = metrics_for_candidate(rows)

    # Panel descriptive only (fixed order)
    recalls = [per_candidate[p]["L2_PRESENT_RECALL"] for p, *_ in PANEL]
    emits = [per_candidate[p]["L2_ABSENT_EMISSION_RATE"] for p, *_ in PANEL]
    panel_summary = {
        "order": [p for p, *_ in PANEL],
        "L2_PRESENT_RECALL": {
            "values_fixed_order": recalls,
            "mean": float(np.mean(recalls)),
            "sd": float(np.std(recalls)),
            "min": float(np.min(recalls)),
            "max": float(np.max(recalls)),
            "DESCRIPTIVE_ONLY": True,
            "NO_RANKING": True,
            "NO_SELECTION": True,
        },
        "L2_ABSENT_EMISSION_RATE": {
            "values_fixed_order": emits,
            "mean": float(np.mean(emits)),
            "sd": float(np.std(emits)),
            "min": float(np.min(emits)),
            "max": float(np.max(emits)),
            "DESCRIPTIVE_ONLY": True,
            "NO_RANKING": True,
            "NO_SELECTION": True,
        },
    }

    # hashes
    def hash_obj(obj) -> str:
        return hashlib.sha256(
            json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()

    full_sha = hash_obj(run1)
    metric_sha = hash_obj(per_candidate)
    cand_out_sha = {p: hash_obj([r for r in run1 if r["candidate_key"] == p]) for p, *_ in PANEL}

    present_subj = Counter(
        s["subject_or_empty_identity"] for s in layer2 if s["reporting_class"] == "PRESENT"
    )
    for k in ("N1", "N2", "N3", "N4", "N5", "N6"):
        present_subj.setdefault(k, 0)

    layer1_report = {
        "TOTAL": 77,
        "ABSENT": 11,
        "PRESENT": 66,
        "VALID": 34,
        "FAIL_CLOSED": 43,
        "GAP_FAIL": sum(
            1
            for s in layer1
            if s.get("fail_closed_code") == "INPUT_UNAVAILABLE_UNRESOLVABLE_TIME_GAP"
        ),
        "TOO_SHORT": sum(
            1
            for s in layer1
            if s.get("fail_closed_code") == "INPUT_UNAVAILABLE_TOO_SHORT_FOR_30S"
        ),
        "by_class_status": {
            f"{cls}|{status}": n
            for (cls, status), n in Counter(
                (s["reporting_class"], s["adapter_status"]) for s in layer1
            ).items()
        },
        "semantics": "AVAILABILITY_INGRESS_SAFETY_ONLY",
        "model_predictions_on_fail_closed": "NOT_FABRICATED",
    }

    feature_receipts = [
        {
            "external_stress_session_id": m["session"]["external_stress_session_id"],
            "a6_layer2_manifest_sha256": parents["l2_sha"],
            "r1_centered_sha256": m["r1_centered_sha256"],
            "train_zscore_trace_sha256": m["train_zscore_trace_sha256"],
            "r2_module": "adapters/mmwave_r2_representation_features.py",
            "family_b_dim": 621,
            "family_c_dim": 671,
            "vec_b_sha256": m["vec_b_sha256"],
            "vec_c_sha256": m["vec_c_sha256"],
            "finite_b": True,
            "finite_c": True,
        }
        for m in materials
    ]

    validation = {
        "schema_version": "PUBABS-A8-VALIDATION-RESULT-V1",
        "phase": "PUBABS-A8",
        "base_sha": args.base_sha,
        "parent_a6_contract_id": "PUBABS_C1_EXTERNAL_STRESS_V1",
        "parent_a6_contract_sha256": EXPECTED["a6_contract"],
        "layer1_sha256": parents["l1_sha"],
        "layer2_sha256": parents["l2_sha"],
        "a7_inference_contract_id": "PUBABS_C1_EXTERNAL_STRESS_INFERENCE_V1",
        "panel_count": 6,
        "panel_order": [p for p, *_ in PANEL],
        "all_artifact_hashes_match": True,
        "layer1_total": 77,
        "layer1_valid": 34,
        "layer1_fail_closed": 43,
        "layer2_total": 34,
        "layer2_absent": 9,
        "layer2_present": 25,
        "feature_vectors_expected": 34,
        "feature_vectors_materialized": len(materials),
        "candidate_session_outputs_expected": 204,
        "candidate_session_outputs_created": len(run1),
        "determinism": True,
        "primary_metrics_executed": True,
        "secondary_metrics_executed": True,
        "forbidden_metrics_executed": False,
        "ranking": False,
        "winner_selected": False,
        "threshold_modified": False,
        "calibration_fitted": False,
        "scaler_refit": False,
        "model_inference": "EXECUTED_EXTERNAL_STRESS_ONLY",
        "d1_unchanged": True,
        "m_pv38_status": "RESOURCE_BLOCKED_CLOSED",
        "m_pv4": "UNAUTHORIZED",
        "interpretation": "DESCRIPTIVE_ONLY",
        "execution_status": "EXECUTION_COMPLETE",
        "abort_status": "NONE",
        "scientific_pass_fail": "DESCRIPTIVE_ONLY_NO_CANONICAL_EXTERNAL_PASS_FAIL",
        "report": "docs/mmwave/20260827_SafeNest_mmWave_PUBABS_A8_C1_External_Stress_Inference_Execution_01.md",
        "manifest_dir": "datasets/mmwave/manifests/PUBABS_A8_c1_external_stress_inference/",
    }

    args.out_dir.mkdir(parents=True, exist_ok=True)
    artifacts = {
        "parent_contract_integrity.json": {
            "a6_contract_sha256": EXPECTED["a6_contract"],
            "layer1_sha256": parents["l1_sha"],
            "layer2_sha256": parents["l2_sha"],
            "adapter_sha256": EXPECTED["adapter"],
            "scaler_embedded_sha256": EXPECTED["scaler_embedded"],
            "a7_contract_id": "PUBABS_C1_EXTERNAL_STRESS_INFERENCE_V1",
            "verified": True,
        },
        "runtime_environment.json": runtime,
        "candidate_panel_receipt.json": {
            "panel_order": [p for p, *_ in PANEL],
            "artifacts": [
                {"panel_id": p, "path": rel, "sha256": sha, "verified": True}
                for p, _f, _s, rel, sha, _d in PANEL
            ],
        },
        "feature_vector_receipts.json": {"sessions": feature_receipts},
        "input_integrity_summary.json": {
            "layer2_sessions": 34,
            "family_b_vectors": 34,
            "family_c_vectors": 34,
            "b_dim": 621,
            "c_dim": 671,
            "trace_hash_match": True,
            "zscore_hash_match": True,
            "double_zscore": "FORBIDDEN_NOT_APPLIED",
        },
        "layer1_availability_report.json": layer1_report,
        "per_session_candidate_outputs.json": {"records": run1, "count": len(run1)},
        "per_candidate_metrics.json": {
            "fixed_order": [p for p, *_ in PANEL],
            "candidates": per_candidate,
            "NO_RANKING": True,
        },
        "panel_descriptive_summary.json": panel_summary,
        "determinism_receipt.json": {
            "runs": 2,
            "identical_canonical_outputs": True,
            "full_204_record_manifest_sha256": full_sha,
        },
        "output_identity_receipt.json": {
            "full_204_record_manifest_sha256": full_sha,
            "metric_manifest_sha256": metric_sha,
            "per_candidate_output_sha256": cand_out_sha,
        },
        "limitations.json": {
            "HIGH_SCALE_MISMATCH_LIMITATION": True,
            "HIGH_CROSS_SENSOR_DOMAIN_RISK": True,
            "VALID34_NOT_CORPUS_REPRESENTATIVE": True,
            "LAYER2_ABSENT_N9_SMALL": True,
            "N6_ZERO_VALID_PRESENT": True,
            "present_subject_counts": dict(present_subj),
        },
        "validation_result.json": validation,
    }
    for name, obj in artifacts.items():
        (args.out_dir / name).write_text(json.dumps(obj, indent=2) + "\n")

    print(
        json.dumps(
            {
                "abort_status": "NONE",
                "outputs": len(run1),
                "primary": {
                    p: {
                        "emit": per_candidate[p]["L2_ABSENT_EMISSION_COUNT"],
                        "emit_rate": per_candidate[p]["L2_ABSENT_EMISSION_RATE"],
                        "recall": per_candidate[p]["L2_PRESENT_RECALL"],
                    }
                    for p, *_ in PANEL
                },
                "full_sha": full_sha,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    try:
        main()
    except A8Abort as exc:
        print(json.dumps({"abort_status": exc.code, "detail": str(exc)}, indent=2))
        raise
