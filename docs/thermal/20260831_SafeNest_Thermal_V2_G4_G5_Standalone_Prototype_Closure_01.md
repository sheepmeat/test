# SafeNest Thermal V2 — G4/G5 Standalone Prototype Closure

- Date: 2026-08-31
- Repository: `sheepmeat/test`
- Base: `3847a38b4229cb7e5fe0c28bb45ede8263bf2f3c` (`#196` Candidate B / C1 matched experiment)
- Branch: `thermal-v2/g4-g5-standalone-prototype-closure`
- Model ID: `thermal_tv2_candidate_a_a0_fp32_v1`
- Status: `OFFLINE_STANDALONE_PROTOTYPE`
- `LOCKED_PUBLIC_TEST_ACCESS`: 0
- Device-domain validation: DEFERRED
- Production selector: UNCHANGED
- No training in this task

## 1. Family decision (already merged)

Candidate A A0 is `A_PREFERRED` from the merged 3-seed family JSON, not from this serialized artifact score.

| Family | Params | N→F mean | FALL rec mean | Macro F1 mean | Status |
|---|---:|---:|---:|---:|---|
| C1 matched pooled MLP | 2691 | 107.67 | 0.9472 | 0.9687 | CONTROL_COMPLETE |
| Candidate A A0 | 64387 | 17.00 | 0.9920 | 0.9949 | A_PREFERRED |
| Candidate B depthwise | 4387 | 120.33 | 0.9253 | 0.9593 | B_NOT_COMPETITIVE |

Under the same PUBLIC_SDT membership, representation, normalization, training policy, and seeds, the spatial-retaining Candidate A architecture substantially outperformed the matched pooled-MLP control and the tested compact depthwise-separable Candidate B **in this offline experiment**. That is not a universal architecture proof and not a device/clinical claim.

## 2. Serialized artifact identity

Lineage: `SAME_POLICY_SEED42_REEXPORT_AFTER_NOMINATION`. `exact_final_9run_weight_instance = false`.

| Artifact | bytes | SHA-256 |
|---|---:|---|
| `models/thermal/candidates/tv2_candidate_a/A0_hn000_FRAME_ROBUST_P2_P98_V1_COARSE_SPATIAL_RETAIN_FLATTEN_V1_seed42.keras` | 820623 | `6a8fd53c815bb29ac42b25fd45c0fe5e0cdad86e4caf359ae37a752d2e2e20ee` |
| `models/thermal/candidates/tv2_candidate_a/A0_hn000_FRAME_ROBUST_P2_P98_V1_COARSE_SPATIAL_RETAIN_FLATTEN_V1_seed42_fp32.tflite` | 264704 | `a158a70c4735e28eec70b5a996f82c91f452b94bcc24c040838143f4a55b1985` |

Input `[1,62,80,1]` float32. Output `[1,3]` float32. Classes `(NOT_HUMAN, HUMAN_NORMAL, HUMAN_FALL_PROXY)`.

## 3. Exact serialized artifact DEVELOPMENT (this task)

Committed FP32 TFLite, frozen `RELATIVE_THERMAL_APPEARANCE_V1` / `FRAME_ROBUST_P2_P98_V1`, PUBLIC_SDT DEVELOPMENT n=8000.

| Metric | TFLite | Keras |
|---|---:|---:|
| sample count | 8000 | 8000 |
| N→F | 14 / 4000 (0.35%) | 14 / 4000 |
| FALL→NORMAL | 17 / 2000 | 17 / 2000 |
| NH→FALL | 0 | 0 |
| FALL recall | 0.9915 | 0.9915 |
| macro F1 | 0.995623 | 0.995623 |
| nonfinite | 0 | 0 |
| inference failures | 0 | 0 |

Confusion (`rows=true, cols=pred`): `[[2000,0,0],[4,3982,14],[0,17,1983]]`

This block characterizes the committed binary. It is **not** a substitute for the 3-seed family mean (17 / 4000).

## 4. Keras ↔ TFLite full DEVELOPMENT parity

| Item | Value |
|---|---|
| samples | 8000 |
| argmax agreement | 8000 / 8000 (100%) |
| max abs diff | 6.258e-06 |
| mean abs diff | 1.202e-08 |
| status | PASS |

## 5. Standalone preprocessing / inference

- Contract: `config/thermal/tv2_a0_relative_appearance_preprocessing.json`
- Adapter: `inference/thermal_tv2_a0.py`
- CLI: `python scripts/run_thermal_tv2_a0_standalone.py --canonical-root <PATH> --evaluate-development --parity-with-keras`
- Tests: `tests/test_thermal_tv2_a0_standalone.py` (10 tests, PASS)

Adapter input is a canonical finite `[62,80]` frame. Wrong shape, NaN/Inf, empty, non-numeric, and unknown source profiles are rejected. MI48 raw / UDP / Thermal-44 are **not** supported here.

## 6. Gates

**G4 = PASS_WITH_LIMITATIONS**

Family A, C1, and B evidence is merged; A_PREFERRED recorded; exact TFLite evaluates; Keras/TFLite parity is 100% argmax; locked test unopened.

**G5 = PASS_WITH_LIMITATIONS**

Stable IDs, TFLite load/invoke, preprocessing contract, inference adapter, manifest, full DEVELOPMENT characterization, hashes locked, limitations explicit.

**STANDALONE_PROTOTYPE_READY = YES** — ready for controlled Team application work only.

Not production-ready, not Pi-validated, not clinical, not scientific final selection.

## 7. Downstream Team handoff (do not apply in this PR)

Import later, in a separate Team-repo task:

- FP32 TFLite path and SHA above
- input `[1,62,80,1]` float32 / output `[1,3]` float32
- class mapping `NOT_HUMAN`, `HUMAN_NORMAL`, `HUMAN_FALL_PROXY`
- `FRAME_ROBUST_P2_P98_V1` via `inference.thermal_tv2_a0.preprocess_canonical_frame`
- canonical `[62,80]` boundary only
- lineage `SAME_POLICY_SEED42_REEXPORT_AFTER_NOMINATION`

Do **not** infer: MI48 raw compatibility, production selector authorization, emergency authority, or actual-fall semantics. `HUMAN_FALL_PROXY` remains static lying posture proxy.

Team repo, Integration, Pi, live sensor, INT8, and production selector were not modified.

## 8. Deferred

- DEVICE_DOMAIN_VALIDATION
- INT8
- LOCKED_PUBLIC_TEST
- execution-map edit (separate worker / PR #190)

Manifest: `config/thermal/tv2_a0_standalone_prototype_manifest.json`
