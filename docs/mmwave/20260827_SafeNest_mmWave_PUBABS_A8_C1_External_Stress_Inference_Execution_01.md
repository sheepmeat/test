# SafeNest mmWave V2 — PUBABS-A8 C1 External Stress Inference Execution

- Phase: **PUBABS-A8**
- Date: 2026-08-27
- Base SHA (post-PR #166 `origin/main`): `aa4d55f8b2fcb49d17a03d229ead5c4dd638f475`
- Branch: `research/mmwave-pubabs-a8-external-stress-inference`
- Role: **bounded inference / evidence generation only**
- Parent A6 contract: **`PUBABS_C1_EXTERNAL_STRESS_V1`**
- Parent A7 inference contract: **`PUBABS_C1_EXTERNAL_STRESS_INFERENCE_V1`**
- Execution status: **`EXECUTION_COMPLETE`**
- Abort status: **`NONE`**
- Interpretation: **`EXTERNAL_SAFETY_DOMAIN_STRESS_ONLY` / `DESCRIPTIVE_ONLY` / `NO_CANONICAL_EXTERNAL_PASS_FAIL`**
- Manifest: `datasets/mmwave/manifests/PUBABS_A8_c1_external_stress_inference/`

This phase runs the frozen six ROLE_L candidates on A6 Layer-2 VALID34 under the A7 contract. It does **not** rank, select, drop, retune, calibrate, refit, reopen M-PV3.8, or authorize M-PV4.

---

## PR #166 merge receipt

| Field | Value |
|---|---|
| PR | https://github.com/sheepmeat/test/pull/166 |
| Reviewed head | `567cab338c00a003a2299e4fbf00b812dfa9cb90` — exact match |
| Reviewed base | `c25ea9bf8343fe1d382f2af781edf48a02398f4a` — exact match |
| `PR166_MERGE_COMMIT` | `aa4d55f8b2fcb49d17a03d229ead5c4dd638f475` |
| `POST_MERGE_ORIGIN_MAIN` | `aa4d55f8b2fcb49d17a03d229ead5c4dd638f475` |
| Head drift | none |

---

## Parent contract integrity

| Identity | SHA-256 |
|---|---|
| A6 `PUBABS_C1_EXTERNAL_STRESS_V1` | `d0353c9bf7837a2520364903b53075bde44cddf10b88c3fef58aa4054bbb3310` |
| Layer1 ALL77 | `cefc7a3820ebb644a9553b3eaad9f4ec600ea555bc25ed891f236cc50c6632f5` |
| Layer2 VALID34 | `01a1db3ef56e1071896f054a5baad397035ca6d989f42f2d1129d250b6867c7c` |
| Frozen adapter | `cfce866f659658e772e833f64e881549a4244b8c9daaa85423b343f34c424446` |
| Scaler embedded field | `5a2583b5b5064be5480b0cf56f2a2c12d40a4a2d005eb087dc8e12106881159c` |

A7 contract id used: `PUBABS_C1_EXTERNAL_STRESS_INFERENCE_V1`.

---

## Runtime

| Field | Value |
|---|---|
| Python | 3.9.6 |
| PyTorch | 2.8.0 |
| NumPy | 1.26.4 |
| Device | CPU |
| Deterministic algorithms | enabled |
| Threads | 1 |
| Format | float32 state_dict (no TFLite / INT8 / ONNX) |
| Threshold | frozen `0.5` |

---

## Feature reconstruction

Lineage used exactly:

```text
A6 VALID34 session
  → r1_centered (verified vs A6)
  → canonical R2 extract_feature_candidates()
  → M-PV2 _feature_matrix (single TRAIN trace z-score)
  → verify train_zscore_trace_sha256 vs A6
  → Family B 621 / Family C 671
```

- Layer2 sessions materialized: **34 / 34**
- Family B vectors: **34 × dim 621**
- Family C vectors: **34 × dim 671**
- Trace hash match: **true**
- Post-zscore hash match: **true**
- Double z-score: **FORBIDDEN_NOT_APPLIED**
- C1 scaler refit: **not executed**

---

## Layer 1 — availability only (ALL77)

| TOTAL | ABSENT | PRESENT | VALID | FAIL_CLOSED | GAP_FAIL | TOO_SHORT |
|---:|---:|---:|---:|---:|---:|---:|
| 77 | 11 | 66 | 34 | 43 | 42 | 1 |

No model predictions were fabricated for the 43 FAIL_CLOSED sessions.

---

## Layer 2 — VALID34 conditional stress population

| TOTAL | ABSENT | PRESENT | N1 | N2 | N3 | N4 | N5 | N6 |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 34 | 9 | 25 | 1 | 1 | 9 | 8 | 6 | 0 |

Semantics: `CONDITIONAL_ON_ADAPTER_VALID` / `OUT_OF_DOMAIN_EXTERNAL_STRESS` / `DESCRIPTIVE_ONLY`.

---

## Inference coverage

| Field | Value |
|---|---|
| Expected outputs | 204 (= 34 × 6) |
| Created outputs | 204 |
| Non-finite outputs | 0 |
| Model load failures | 0 |
| Determinism (2 full runs) | identical canonical fields |

Full 204-record manifest SHA-256: `13e4d85591300dda5619630608e49477cd989e05095925ac9d68706147aa626c`

---

## Candidate artifact verification (fixed order)

| Panel | Path | SHA-256 verified |
|---|---|---|
| B11 | `models/mmwave/m_pv2/family_b/candidate_seed_11.pt` | `5633a7eefa83544cd33a251b0016b40f37e28039f985b31c98bdcfa37aa8b1a6` |
| B23 | `models/mmwave/m_pv2/family_b/candidate_seed_23.pt` | `8f7de6f50d6ff62ff9b0ebfaed0b1fccd8d194c7e33781bc5b93366fae251a2c` |
| B47 | `models/mmwave/m_pv2/family_b/candidate_seed_47.pt` | `ed3da35adb0837426065cc575b7e4ff6f41ef9a8fb295bb29f7eb8bcff4db280` |
| C11 | `models/mmwave/m_pv2/family_c/candidate_seed_11.pt` | `539bd6021d10a9abd35a22b49c0db728a122b60356f59609fead9280d82f7768` |
| C23 | `models/mmwave/m_pv2/family_c/candidate_seed_23.pt` | `ce99a6534928138bc5e2d271123185f93aceb6386b8a24b0ecb3679c7d6d70de` |
| C47 | `models/mmwave/m_pv2/family_c/candidate_seed_47.pt` | `2f1b446c808cfb90d02dc6cce754311ade19cf2e3bb03b20814a1268934cb5a1` |

---

## Primary metrics (fixed order; no ranking)

Denominators always visible: ABSENT **9**, PRESENT **25**.

| Panel | L2_ABSENT_EMISSION_COUNT / 9 | L2_ABSENT_EMISSION_RATE | L2_PRESENT_RECALL / 25 |
|---|---:|---:|---:|
| B11 | 0 / 9 | 0.0 | 0.0 |
| B23 | 0 / 9 | 0.0 | 0.0 |
| B47 | 2 / 9 | 0.222… | 0.0 |
| C11 | 9 / 9 | 1.0 | 1.0 |
| C23 | 7 / 9 | 0.777… | 0.72 |
| C47 | 0 / 9 | 0.0 | 0.0 |

Labels on every primary metric: `CONDITIONAL_ON_ADAPTER_VALID`, `OUT_OF_DOMAIN_EXTERNAL_STRESS`, `DESCRIPTIVE_ONLY`.

ABSENT physiology emission means breathing-decision PRESENT at frozen 0.5 on no-human-target sessions — not RR error, apnea, or clinical false diagnosis.

---

## Registered secondary metrics

Computed only from the A7 registry (confusion, precision/F1 where defined, Brier diagnostic, per-subject PRESENT strata, per-position strata, Layer1 availability table, panel descriptive mean/sd/min/max with `NO_RANKING` / `NO_SELECTION`).

Brier is diagnostic only and is **not** compared to M-PV3.8 `Brier <= 0.05` as a pass/fail gate.

M-PV3.8 selection gates are **not applicable** to C1.

---

## RR / quality / apnea

| Metric family | Status |
|---|---|
| RR accuracy / MAE / within-bpm | `NOT_SCORED` |
| Quality accuracy | `NOT_SCORED` |
| Apnea / breath-hold metrics | `NOT_SCORED` |

RR values may exist only as deterministic raw-output audit fields under A7 inverse TRAIN transform. C1 ABSENT means **no human target**, not apnea.

---

## Limitations (unchanged by outputs)

- `HIGH_SCALE_MISMATCH_LIMITATION` / `TRAIN_ZSCORE_SCALE_RISK = HIGH`
- `HIGH_CROSS_SENSOR_DOMAIN_RISK`
- `VALID34_NOT_CORPUS_REPRESENTATIVE`
- `LAYER2_ABSENT_N9_SMALL`
- `N6_ZERO_VALID_PRESENT`

Good or poor external results authorize nothing: no model selection, no M-PV3.8 reopen, no M-PV4, no D1 substitution.

---

## Explicit non-actions

```text
CANDIDATE_RANKING   = NOT_EXECUTED
WINNER_SELECTION    = NOT_EXECUTED
CANDIDATE_DROP      = NOT_EXECUTED
THRESHOLD_TUNING    = NOT_EXECUTED
CALIBRATION_FIT     = NOT_EXECUTED
SCALER_REFIT        = NOT_EXECUTED
RR_SCORING          = NOT_EXECUTED
QUALITY_SCORING     = NOT_EXECUTED
APNEA_SCORING       = NOT_EXECUTED
D1                  = UNCHANGED
M-PV3.8             = RESOURCE_BLOCKED_CLOSED
M-PV4               = UNAUTHORIZED
D2                  = LOCKED
```

---

## Artifacts

- Script: `scripts/mmwave/pubabs_a8_external_stress_inference.py`
- Manifest dir: `datasets/mmwave/manifests/PUBABS_A8_c1_external_stress_inference/`
- Machine-readable gate: `validation_result.json` (`abort_status=NONE`, `forbidden_metrics_executed=false`, `ranking=false`, `winner_selected=false`)

Raw C1 `Data.zip` was verified (DOI `10.5281/zenodo.15032859`, MD5 `99067ac569e419fc122eef49635d72d0`) and **not** committed.
