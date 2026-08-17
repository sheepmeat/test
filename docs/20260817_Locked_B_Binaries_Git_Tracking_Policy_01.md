# Locked B-binaries Git tracking policy

Date: 2026-08-17  
Repo: `sheepmeat/test` (local `embed2`)  
Classification: **POLICY AMENDMENT** — does not rewrite T-B5 offline lock evidence.

## Why this exists

T-B5 locked `FULL_INT8` with:

```text
binaries_tracked_in_git: false
binary_storage: EXTERNAL_SSD_ONLY
```

CO₂ C-B6 and mmWave B INT8 were already in Git under `models/`. Thermal B INT8 was not. Teammates cloning this repo could not run T-B5 without the external SSD.

That split is now treated as a packaging defect, not as a reason to substitute `thermal_fall_int8_v0.1.0.tflite`.

## New rule

1. **Locked B-stage deployable binaries live in Git** under `models/<sensor>/...`.
2. **SHA-256 in the lock/registry is still the identity.** A file in Git with the wrong hash is not the candidate.
3. **External SSD remains a backup / experiment dump**, not the only copy teammates must own.
4. **Do not change `models/model_manifest.json` production default** in this amendment. Historical v0.1.0 stays the default path until a later authorized switch.
5. **Do not substitute** `models/thermal/thermal_fall_int8_v0.1.0.tflite` for T-B5 `FULL_INT8`.
6. Keras checkpoints (`.h5`) and diagnostic-only `dynamic_range` TFLite stay SSD-optional unless a later amendment tracks them.

## Git paths (2026-08-17)

| Sensor | Candidate | Git path | SHA-256 |
|---|---|---|---|
| Thermal | `FULL_INT8` (selected) | `models/thermal/candidates/t_b5/SMALL_CNN_BASELINE_V1_P1_full_int8.tflite` | `fa9730c29535477a3994c11e664474a0ca0116afaaa172889f47446ab2ac46be` |
| Thermal | `TFLITE_FP32` (reference) | `models/thermal/candidates/t_b5/SMALL_CNN_BASELINE_V1_P1_float32.tflite` | `fbe891520f07e0534b1a7074dc819d8ed44bca58b27e35c78916c3ddae73a779` |
| CO₂ | C-B6 INT8 | `models/co2/candidates/c_b6/full_integer_int8.tflite` | already tracked |
| mmWave | M-B3/M-B5 INT8 | `models/mmwave/experiments/M-B6_stage_equivalence/M-B3_CONV1D_GAP_BASELINE_seed42_M-B5_CAL_CLASS_BALANCED_120_int8.tflite` | already tracked |

## Historical T-B5 lock

The 2026-08-15 offline candidate lock (SHA, size, P1 preprocess, limitations, `thermal44_deployment_validated=false`) is unchanged. This amendment only changes **where teammates get the bytes**.
