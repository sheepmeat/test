# SafeNest mmWave V2 — PUBABS-A3R C1 Frozen Adapter Structural Re-Validation

- Phase: **PUBABS-A3R**
- Date: 2026-08-26
- Base SHA (post-PR #161): `cac5141d1ffe3b9204dd11ae295df8fedc940677`
- Branch: `research/mmwave-pubabs-a3r-c1-frozen-adapter`
- Frozen proposal SHA-256: `cfce866f659658e772e833f64e881549a4244b8c9daaa85423b343f34c424446`
- Timestamp contract: `R1T_MEASURED_TIMESTAMP_10HZ_V1`
- Range contract: `C1_ROI_EXCLUDE_NEARFIELD28_DYNENERGY_UNWRAP_V1` / `RG-S1`
- A3R gate: **`A3R_PASS_WITH_LIMITATIONS`**
- A4 recommendation: **`RECOMMEND_A4`**
- Manifest: `datasets/mmwave/manifests/PUBABS_A3R_c1_frozen_adapter_revalidation/`

M-PV3.8 remains `RESOURCE_BLOCKED_CLOSED`. No membership. No model inference. A4 not executed.

---

## Verdict

The Sol-frozen C1 adapter is implemented exactly and runs the **same code path** for all 77 sessions.  
**34 / 77** sessions emit exact 300-sample ROLE_L-shaped tensors under frozen R1T+RG-S1; **43** fail closed only under frozen timing rules (mostly `INPUT_UNAVAILABLE_UNRESOLVABLE_TIME_GAP` on the first 30 s). Dual-run determinism holds. Historical R1 is unchanged and, on valid sessions, applies **median centering only** (`NONE_SOURCE_ALREADY_AT_TARGET_RATE`).

This is **not** membership approval, domain equivalence, or model utility.

---

## Coverage (all 77)

| Cohort | Total | VALID | FAIL_CLOSED |
|---|---:|---:|---:|
| Empty_space (ABSENT report) | 11 | 9 | 2 |
| PRESENT N1–N6 | 66 | 25 | 41 |
| **All** | **77** | **34** | **43** |

Fail-closed codes: `{'INPUT_UNAVAILABLE_UNRESOLVABLE_TIME_GAP': 42, 'INPUT_UNAVAILABLE_TOO_SHORT_FOR_30S': 1}`

Data.zip MD5 verified: `99067ac569e419fc122eef49635d72d0` (not committed).

---

## Frozen flow (implemented)

C1 CSV → ROI bins [28,179] → RG-S1 first-30s dyn-energy argmax (lowest-tie) session lock → unwrap(angle) → R1T WINDOW_LOCAL → 20 Hz×599 linear interp (no extrapolation) → Butterworth N=4 fc=4 Hz filtfilt odd padlen=15 → even-index → 300@10 Hz → historical R1 median center → frozen TRAIN z-score (no C1 refit).

---

## Range selection (structural)

Selected bins among VALID sessions (counts): `{'122': 1, '157': 1, '28': 6, '30': 3, '32': 1, '33': 1, '34': 3, '35': 4, '36': 4, '38': 5, '39': 1, '40': 2, '62': 1, '65': 1}`  
Session lock confirmed in unit tests; late-record energy after t0+30 does not change the bin.

---

## Timing / R1T

Valid median source rate ≈ 18.8–19.6 Hz. Gap failures use exact frozen rule `gap > 2.5 * median_dt` (no `max(0.25s, …)`). One session fails `INPUT_UNAVAILABLE_TOO_SHORT_FOR_30S` (last obs slightly before t0+29.9).

---

## Historical R1 integrity

- File `adapters/mmwave_r1_sensor_independent_trace.py` **unchanged** on this branch (SHA-256 `2d5f34feef524e18f9b9e5b5d8c9ef4223fa133c55fb48ee4703f7e31a54e102`).
- Valid sessions: resampling method `NONE_SOURCE_ALREADY_AT_TARGET_RATE`.

---

## Frozen TRAIN preprocessing (structural)

All VALID sessions: finite z-score tensors, length 300.  
Observation: `SCALE_RISK_REMAINS` — absolute z magnitudes remain small vs TRAIN scale; no correction fitted; no class separation analysis.

---

## Determinism

Two full passes over 77 sessions: identical status, fail codes, selected bins, and SHA-256 receipts for r1t / R1-centered / z-score traces.

---

## Anti-contamination

Adapter API accepts only timestamps + complex frames (+ optional recording_id / contract hash). Class is inventory-only. Unit test proves recording_id change does not alter numeric outputs.

---

## A3R gate

```text
A3R_PASS_WITH_LIMITATIONS
```

Limitations: majority PRESENT sessions fail frozen first-30s gap rule; corpus coverage for both-class structural entry is partial. Failures are not silent repairs.

A4 recommendation:

```text
RECOMMEND_A4
```

A4 remains unauthorized to execute in this PR; Sol decides whether domain/leakage stress proceeds on the VALID subset under these coverage limits.

---

## Explicit non-actions

- MODEL_INFERENCE = NOT_EXECUTED
- MEMBERSHIP = NOT_CREATED
- M-PV3.8 = UNCHANGED (`RESOURCE_BLOCKED_CLOSED`)
- M-PV4 = UNAUTHORIZED
- D2 = LOCKED
- A4 = NOT_EXECUTED
- HISTORICAL_R1 = UNCHANGED
