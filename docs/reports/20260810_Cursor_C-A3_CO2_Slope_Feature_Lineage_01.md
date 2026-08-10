# SafeNest CO₂ Phase C-A3 — Slope Feature Reconstruction and Source-Row Feature Lineage

- Document Version: `01`
- Author: `Cursor` (CO₂ Track Implementation Agent)
- Execution Date: `2026-08-10`
- Phase: `C-A3 — CO₂ Slope Feature Reconstruction and Source-Row Feature Lineage`
- Target Dataset: UCI Occupancy Detection Dataset (C-A1/C-A2 lineage)
- Status: `PASS_WITH_WARNINGS`
- C-A4 Authorization: `YES`

---

## 1. Executive Summary

Phase **C-A3** locks a deterministic, causal `CO2_slope` feature contract in `ppm/min` for all **20,560** C-A1 source rows under the C-A2 temporal acquisition blocks. The selected method is **endpoint difference** over a **150-second** source-clock history duration, aligned with the active SCD40 adapter (`sensors/co2/co2_adapter.py`) and documented sensor contract.

Every source row is preserved: **20,551** eligible finite slopes and **9** explicit warm-up rows (`FEATURE_UNAVAILABLE_WARMUP`, `co2_slope=null`). No scaler was fit, no model was trained, and the synthetic NPZ was not used as real-data evidence.

---

## 2. Predecessor Gate

| Gate | Result |
|---|---|
| Canonical base | `origin/main` @ `4df8284` |
| C-A2 PR #16 | MERGED (`9b3f21a`) |
| C-A0 validator | `PASS_WITH_WARNINGS` |
| C-A1 validator | `PASS_WITH_WARNINGS` |
| C-A2 validator | `PASS_WITH_WARNINGS` |
| Fresh branch | `feature/C-A3-co2-slope-feature-lineage` from updated `main` (not from old C-A2 branch tip alone) |

---

## 3. Historical Slope Evidence Examined

Evidence inspected (priority order):

1. Active `AGENTS.md` and multisensor roadmap C-A3 section.
2. Validator-approved C-A0/C-A1/C-A2 manifests.
3. `sensors/co2/co2_adapter.py` — `calculate_co2_slope`: `(current - first_in_window) / elapsed_min`, `window_seconds=150.0`, `window_samples=30`.
4. `docs/reports/SENSOR_DATA_CONTRACT.md` — documents endpoint difference over 30-sample history as `VERIFIED_CODE`.
5. `docs/reports/sensor_model_data_contract.json` — `history_maxlen: 30`, 0.2 Hz sampling.
6. `models/co2/co2_scaling_metadata_v0.1.0.json` — proves feature name `CO2_slope` and historical mean/scale values, **not** formula proof.
7. Synthetic `datasets/co2/processed/co2_occupancy_v1.npz` — explicitly **not** used as ground truth.

---

## 4. Candidate Methods Considered

| Candidate | Concept | Decision |
|---|---|---|
| A | Previous-sample rate `(now - previous) / elapsed_min` | Rejected — contradicts multi-sample adapter window |
| B | Endpoint difference over history duration | **Selected** |
| C | Linear regression slope over window | Rejected — no active code evidence |

Selection used active code/temporal evidence only. Occupancy labels, classifier accuracy, and LOCKED_TEST metrics were not used. TRAIN-only descriptive comparison to historical scaler mean was a **secondary** diagnostic after formula freeze.

---

## 5. Final Selected Slope Contract

| Field | Value |
|---|---|
| Feature name | `CO2_slope` |
| Profile ID | `CO2_SLOPE_FEATURE_PROFILE_001` |
| Method | `ENDPOINT_DIFFERENCE` |
| Formula | `(co2_now - co2_history_start) / (elapsed_source_clock_seconds / 60.0)` |
| Unit | `ppm/min` |
| History duration | `150.0` seconds (`2.5` minutes) |
| Minimum samples | `2` |
| Minimum elapsed | `150.0` seconds |
| Causality | `PAST_ONLY` |
| Timestamp basis | `SOURCE_ACQUISITION_CLOCK` (no UTC conversion, no `Z`) |
| Precision | `float64` |
| Comparison tolerance | `1e-12` absolute |

### Justification

1. Matches active adapter endpoint-difference method.
2. Locks temporal duration `window_seconds=150.0` as the primary semantic (UCI cadence ~60s ⇒ typical span ~179–181s / 4 samples).
3. Uses actual source-clock deltas (handles 59–61s jitter correctly).
4. Causal, deterministic, and block-isolated.

---

## 6. Warm-Up, Gap, and Block-Boundary Behavior

- **Warm-up**: First rows of each block without ≥150s same-block past history retain the row with `FEATURE_UNAVAILABLE_WARMUP` and `co2_slope=null`. No silent deletion; no fill with 0/NaN/previous/future.
- **Block boundary**: History never crosses `BLOCK_01` / `BLOCK_02` / `BLOCK_03`. Inter-member multi-hour gaps are never bridged.
- **Gap policy**: Adjacent same-block delta `> 90.0s` restarts history (`FEATURE_UNAVAILABLE_GAP_RESTART`). No interpolation.
- **Nonfinite policy**: Fail-closed status; no canonical NaN/Inf slope persisted.

Observed on real UCI data: **0** internal forbidden gaps; warm-up exactly **3 rows × 3 blocks = 9**.

---

## 7. Source-Row Feature Lineage

Eligible slopes are reconstructable from:

```text
target source row
→ temporal_block_id / future_split_role
→ history_start … history_end source row identifiers
→ SOURCE_ACQUISITION_CLOCK timestamps
→ raw CO2 endpoints
→ ppm/min endpoint slope
```

Machine-readable contract: `datasets/co2/manifests/c_a3_slope_feature/source_row_feature_lineage_contract.json`.  
Compact evidence strategy: regenerable full lineage via `datasets.co2.slope_feature.reconstruct_all_slope_features` plus manual verification lineages (no giant redundant dump).

---

## 8. Manual Independent Verification

Ten cases passed with absolute error `0.0` (tolerance `1e-12`), including:

- first block row / warm-up / first eligible / interior
- 59s and 61s adjacent-delta eligible rows
- block-boundary restart
- one eligible row each from TRAIN, VALIDATION, and LOCKED_TEST (post-freeze integrity only)

Expected values were recomputed independently from raw timestamps/CO2 (not by calling production reconstruction twice).

---

## 9. Eligibility and Descriptive Audit

| Block / Role | Source rows | Eligible | Warm-up | Nonfinite outputs |
|---|---:|---:|---:|---:|
| BLOCK_01 / VALIDATION | 2665 | 2662 | 3 | 0 |
| BLOCK_02 / TRAIN | 8143 | 8140 | 3 | 0 |
| BLOCK_03 / LOCKED_TEST | 9752 | 9749 | 3 | 0 |
| **Total** | **20560** | **20551** | **9** | **0** |

TRAIN descriptive audit (not model performance): mean `0.011527`, stdev `5.661676`, min `-184.833`, max `250.167`.  
VALIDATION descriptive audit recorded after freeze.  
LOCKED_TEST: eligibility/count integrity only (value statistics omitted from feature-definition feedback).

---

## 10. Historical Scaler Comparison (Secondary)

| Metric | Historical scaler | Reconstructed TRAIN |
|---|---:|---:|
| mean(`CO2_slope`) | 0.011184 | 0.011527 |
| scale / stdev | 4.373409 | 5.661676 |

Diagnostic result: `CONSISTENT_WITH_HISTORICAL_SCALER` (mean alignment). This does **not** prove model training lineage.

Retained classifications:

- `MODEL_TRAINING_LINEAGE_UNVERIFIED`
- `SCALER_FIT_LINEAGE_UNVERIFIED`

---

## 11. Determinism

Evidence generator `scripts/audit_co2_slope_feature.py` was executed twice; `checksums.sha256` remained identical. No host-timezone, locale, randomness, or unordered-collection dependence in persisted artifacts.

---

## 12. Validation and Tests

| Check | Result |
|---|---|
| C-A0 validator | PASS_WITH_WARNINGS |
| C-A1 validator | PASS_WITH_WARNINGS |
| C-A2 validator | PASS_WITH_WARNINGS |
| C-A3 validator | PASS_WITH_WARNINGS |
| C-A3 focused tests | 16 passed |
| CO₂ focused suite (C-A0..C-A3) | 47 passed |
| Full `tests/` regression | 418 passed, 2 skipped, 0 failed |
| `git diff --check` | clean |
| Scaler metadata modified | NO |
| Synthetic NPZ used as real source | NO |

---

## 13. Parallel Git Isolation

C-A3 branch contains only CO₂ C-A3 files relative to `origin/main`. mmWave / Thermal / unauthorized shared / raw payload changes: **0**.

---

## 14. Deferred Work / C-A4 Authorization

Deferred:

- C-A4 label semantics and safety separation
- C-B scaler fit (TRAIN only) and model comparison
- Shared inventory updates (`DEFERRED_SHARED_INTEGRATION_UPDATE`)
- Device-domain sample-count alignment nuances under C-C

C-A4 authorization: **YES** (slope formula/unit/history/lineage/warm-up/validators satisfied; no blockers).

---

## 15. Generated Artifacts

- `datasets/co2/slope_feature.py`
- `scripts/audit_co2_slope_feature.py`
- `scripts/validate_co2_slope_feature.py`
- `tests/test_co2_slope_feature.py`
- `datasets/co2/manifests/c_a3_slope_feature/*`
- `docs/reports/20260810_Cursor_C-A3_CO2_Slope_Feature_Lineage_01.md`
