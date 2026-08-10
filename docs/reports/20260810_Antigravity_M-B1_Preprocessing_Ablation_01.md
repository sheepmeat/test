# SafeNest mmWave M-B1 — Real-Data Preprocessing Full-Factorial Ablation Report

- **Author**: Antigravity Implementation Engineer
- **Date**: 2026-08-10
- **Target Repository**: `https://github.com/sheepmeat/test.git`
- **Branch**: `feature/M-B1-preprocessing-ablation`
- **Phase M-B1 Gate Status**: `PASS_WITH_WARNINGS`
- **M-B2 Entry Status**: `READY_WITH_CONDITIONS`
- **Selected Preprocessing Profile**: `M-B1_D1_B0_Z0` (`DETREND_ONLY`)

---

## 1. Executive Summary

Phase M-B1 conducts a $2^3$ full-factorial offline preprocessing ablation experiment over **Linear Detrending ($D$)**, **Fixed 0.1–0.5 Hz 4th-order Butterworth BPF ($B$)**, and **TRAIN-fitted Global Z-score Standardization ($Z$)** on the approved real mmWave canonical dataset (`mmwave_canonical_real_v1.npy`, 530 windows).

Key achievements of Phase M-B1:
1. **$2^3$ Full-Factorial Preprocessing Evaluation**: Trained the fixed probe 1D CNN architecture under identical unweighted training conditions across all 8 pre-registered profiles.
2. **VALIDATION-Only Winner Selection**: Evaluated performance strictly on VALIDATION split (79 pure-class windows) under the pre-registered 6-step ranking rule.
3. **Winning Profile**: Selected **`M-B1_D1_B0_Z0` (`DETREND_ONLY`)** with VALIDATION Macro F1 = **`0.652975`**, Accuracy = `0.721519`, APNEA Recall = `0.972973`.
4. **Strict LOCKED_TEST Isolation**: Confirmed `0` performance access attempts to LOCKED_TEST (`scripts/mmwave_phase_b_access.py` guard verified).
5. **Deterministic Rerun Verification**: Verified 100% prediction match when rerunning `M-B1_D1_B0_Z0` under fixed initialization seed `42`.

---

## 2. Full-Factorial Ablation Performance Results

| Profile ID | Name | Detrend ($D$) | BPF ($B$) | Z-Score ($Z$) | Macro F1 | Accuracy | APNEA Proxy Recall | RAPID Recall | Class Collapsed |
|---|---|---|---|---|---|---|---|---|---|
| `M-B1_D0_B0_Z0` | `RAW` | `OFF` | `OFF` | `OFF` | `0.5784` | `0.6709` | `0.9730` | `0.2500` | `NO` |
| `M-B1_D1_B0_Z0` | `DETREND_ONLY` | `ON` | `OFF` | `OFF` | `0.6530` | `0.7215` | `0.9730` | `0.3500` | `NO` |
| `M-B1_D0_B1_Z0` | `BPF_ONLY` | `OFF` | `ON` | `OFF` | `0.6179` | `0.6456` | `0.7027` | `0.4500` | `NO` |
| `M-B1_D1_B1_Z0` | `DETREND_BPF` | `ON` | `ON` | `OFF` | `0.6261` | `0.6582` | `0.7027` | `0.4000` | `NO` |
| `M-B1_D0_B0_Z1` | `ZSCORE_ONLY` | `OFF` | `OFF` | `ON` | `0.2763` | `0.4937` | `1.0000` | `0.1000` | `NO` |
| `M-B1_D1_B0_Z1` | `DETREND_ZSCORE` | `ON` | `OFF` | `ON` | `0.2126` | `0.4684` | `1.0000` | `0.0000` | `YES` |
| `M-B1_D0_B1_Z1` | `BPF_ZSCORE` | `OFF` | `ON` | `ON` | `0.6224` | `0.6962` | `1.0000` | `0.4000` | `NO` |
| `M-B1_D1_B1_Z1` | `DETREND_BPF_ZSCORE` | `ON` | `ON` | `ON` | `0.6089` | `0.6835` | `1.0000` | `0.3500` | `NO` |

---

## 3. Winner Selection & Ranking Rationale

Under the pre-registered 6-step ranking rule:
1. **Class-Collapse Filtering**: Evaluated all 8 profiles for zero recall or prediction collapse on APNEA proxy or RAPID classes.
2. **Macro F1 Ranking**: Profile **`M-B1_D1_B0_Z0`** achieved the highest VALIDATION Macro F1 (**`0.652975`**).
3. **Selected Profile Contract**: `M-B1_D1_B0_Z0` (`DETREND_ONLY`) is frozen in `selected_preprocessing_profile.json` for subsequent Phase-B experiments.

---

## 4. Signal Domain & Diagnostic Results

### 4.1 BPF Frequency Response Diagnostic (0.1–0.5 Hz, 4th Order)
- **30 bpm (0.50 Hz)**: -3.0 dB attenuation (gain 0.707)
- **40 bpm (0.67 Hz)**: -14.6 dB attenuation (gain 0.186)
- **48 bpm (0.80 Hz)**: -20.5 dB attenuation (gain 0.094)
- **Finding**: The 0.1–0.5 Hz BPF naturally suppresses respiration frequencies above 30 bpm. This filter parameter is frozen for M-B1 and will be evaluated for potential tuning in later phases if required.

### 4.2 APNEA-Proxy Preprocessing Diagnostic
- Voluntary breath-hold APNEA proxy windows retain near-zero respiration amplitude characteristics after linear detrending and bandpass filtering, while low-frequency baseline drift is successfully removed.

---

## 5. Validation & Exit Gate Summary

- Standalone M-B1 validator (`scripts/validate_mmwave_m_b1.py`): `PASS` (`validation_success: True`)
- Standalone M-B0 validator (`scripts/validate_mmwave_m_b0.py`): `PASS`
- Upstream M-A5 validator (`scripts/validate_mmwave_subject_split.py`): `PASS`
- Upstream M-A6 validator (`scripts/validate_mmwave_full_conversion.py`): `PASS`
- Unit tests (`tests/test_mmwave_m_b1.py`): `PASS` (6/6 passed)
- Full mmWave test suite: `PASS` (106/106 passed)
- Deterministic Rerun: `PASS` (`validation_predictions_match: True`)
- Checksum Coverage: All 17 machine-readable manifests checksummed in `checksums.sha256`
- M-B1 Gate Status: `PASS_WITH_WARNINGS`
- M-B2 Entry Status: `READY_WITH_CONDITIONS`
