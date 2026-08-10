# SafeNest mmWave M-B5 — Representative Calibration Dataset Comparison Report

- **Author**: Antigravity Implementation Engineer
- **Date**: 2026-08-10
- **Target Repository**: `https://github.com/sheepmeat/test.git`
- **Branch**: `feature/M-B5-representative-calibration`
- **Phase M-B5 Gate Status**: `PASS_WITH_WARNINGS`
- **M-B6 Entry Status**: `READY_WITH_CONDITIONS`
- **Pinned Environment**: Python 3.9.6 / TensorFlow 2.20.0 / NumPy 1.26.4 / SciPy 1.13.1 (`requirements-mac.txt` compliant)
- **Frozen Primary Architecture**: `M-B3_CONV1D_GAP_BASELINE`
- **Frozen Weight Seeds**: `[42, 43, 44]`
- **TRAIN Population**: 327 pure-class windows (77 subjects)
- **VALIDATION Population**: 79 pure-class windows (17 subjects)
- **Selected Calibration Profile**: `M-B5_CAL_CLASS_BALANCED_120`

---

## 1. Executive Summary

Phase M-B5 compares four pre-registered TRAIN-only representative calibration dataset profiles (**`M-B5_CAL_TRAIN_ORDER_120`**, **`M-B5_CAL_RANDOM_PROPORTIONAL_120`**, **`M-B5_CAL_CLASS_BALANCED_120`**, and **`M-B5_CAL_DISTRIBUTION_AWARE_120`**) across all three frozen M-B4 model seed weight sets (`42`, `43`, `44`) to select exactly one calibration profile for formal M-B6 Float Keras → Float TFLite → INT8 equivalence testing.

Key findings of Phase M-B5:
1. **Cross-Seed INT8 Evaluation**: All 12 strict INT8 conversions (4 profiles × 3 seeds) succeeded with 0 Flex/Select ops and zero new class collapses.
2. **Selected Profile**: Applying the pre-registered 8-criterion ranking rule, **`M-B5_CAL_CLASS_BALANCED_120`** was selected as the optimal calibration profile.
3. **LOCKED_TEST Isolation**: Confirmed `0` performance access attempts to LOCKED_TEST (`scripts/mmwave_phase_b_access.py` guard verified).

---

## 2. Cross-Seed Calibration Profile Performance Matrix (VALIDATION Set)

| Profile ID | Eligibility | Worst F1 Deg. | Worst Rec Deg. | Min Top-1 | Max Output MAE | Max Input Sat. | Max End. Ratio |
|---|---|---|---|---|---|---|---|
| `M-B5_CAL_TRAIN_ORDER_120` | `ELIGIBLE` | `0.009770` | `0.081082` | `0.936709` | `0.008551` | `0.000000` | `0.000000` |
| `M-B5_CAL_RANDOM_PROPORTIONAL_120` | `ELIGIBLE` | `0.016925` | `0.054054` | `0.962025` | `0.008554` | `0.000000` | `0.000000` |
| `M-B5_CAL_CLASS_BALANCED_120` | `ELIGIBLE` | `0.009770` | `0.081082` | `0.936709` | `0.008439` | `0.000000` | `0.000000` |
| `M-B5_CAL_DISTRIBUTION_AWARE_120` | `ELIGIBLE` | `0.009770` | `0.081082` | `0.936709` | `0.009259` | `0.000000` | `0.000000` |

---

## 3. Selected Profile Details

Selected Calibration Profile: **`M-B5_CAL_CLASS_BALANCED_120`**
- Worst Positive Macro F1 Degradation: `0.009770`
- Worst Positive Recall Degradation: `0.081082`
- Minimum Top-1 Agreement: `0.936709`
- Maximum Output Probability MAE: `0.008439`
- Maximum Input Saturation Ratio: `0.000000`
- Maximum Output Endpoint Ratio: `0.000000`

---

## 4. Limitations & Scope

- **Fixed Subject Split**: Inherited immutable A5 subject split (TRAIN=77 subjects, VALIDATION=17 subjects).
- **LOCKED_TEST Preserved**: LOCKED_TEST (20 subjects) remained strictly un-accessed (0 access attempts).
- **No Clinical Claims**: Voluntary breath-hold labels remain APNEA proxies, not clinical apnea.
- **Stage Equivalence Pending**: Chosen calibration profile requires formal M-B6 stage-equivalence testing.
- **Hardware Validation Unverified**: Hardware performance on MR60 real sensor and Raspberry Pi remains unverified until hardware testing.

---

## 5. Validation & Exit Gate Summary

- Standalone M-B5 validator (`scripts/validate_mmwave_m_b5.py`): `PASS`
- Checksum Coverage: All 19 machine-readable manifests checksummed in `checksums.sha256`
- M-B5 Gate Status: `PASS_WITH_WARNINGS`
- M-B6 Entry Status: `READY_WITH_CONDITIONS`
