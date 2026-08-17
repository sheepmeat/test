# SafeNest mmWave 110-Subject Public Dataset Reuse Readiness

- Date: 2026-08-17
- Task: **PUBLIC-P0** (parallel preparation; not a canonical M-N phase)
- Parallel with: M-N0 Team MR60 physical-data inventory (not duplicated here)
- Status: `PUBLIC_P0_READY_WITH_LIMITATIONS`
- Base SHA: `2574fbc4abba7988565dd1fd013b1698fe4ecf49`
- Scope: public mmWave lineage only. No training, no M-N2 execution, no MR60 comparison, no historical A/B mutation.

One-line answer:

```text
Highest reusable public radar source = local Zenodo range-FFT archive
(complex [frames, 8 virtual channels, 64 range bins]).
Highest persisted pre-B signal = A6 unfiltered unnormalized phase windows.
Recommended M-N2 branch = native-rate unwrapped phase re-derived via A1+A2,
before A3 30 s / 300-sample windowing and before historical BPF_ZSCORE.
```

---

## A. Source identity

| Field | Evidence |
|---|---|
| Dataset | Extensive Age-Balanced and Subject-Varied mmWave Radar Dataset of Referenced Records for Vital Signs |
| DOI / URL | `10.5281/zenodo.18599983` / https://zenodo.org/records/18599983 |
| SafeNest dataset_id | `dataset-10_5281_zenodo_18599983` |
| License | CC BY 4.0 |
| Acquisition | 60 GHz FMCW radar (`START_FREQ` 60.25 GHz, 2 TX × 4 RX → 8 virtual channels, 64 range bins) |
| Source radar form | **range FFT already**, not raw ADC. Member: `radar_rFFTs.zlib` |
| Reference sensors | Movesense chest accelerometer and ECG CSVs in every recording |
| Original annotations | `non_breathing_ts.csv` on Rest recordings only (220 / 440) |
| Official companion files not in local workspace | `ParticipantsInfo.xlsx`, `ExampleCode.ipynb`, `helper_fns.py` |
| Local archive | `datasets/raw_archives/external_datasets/db_records.zip` |
| Local status | `LOCAL_ONLY_EXPECTED` (gitignored). Present in this workspace: 246,597,320 bytes, SHA-256 `f0bcfdac94f88b43bb34d3da8e8f071a787291f86c97798059b8dbf4d4be08b0` |
| Official vs local container | `LIKELY_REPACKAGED_NOT_FULLY_VERIFIED` (local zip includes macOS `._*` resource forks; official container MD5 differs; 110 subjects / 440 recordings present, 0 CRC failures) |
| Canonical manifests | `datasets/MANIFEST.json`; `datasets/mmwave/manifests/a0_raw_inventory/` |

Do not confuse with `datasets/mmwave/processed/mmwave_respiration_v1.npz` (`SYNTHETIC_SMOKE_AND_RETRAINING_ASSET`). That file is not the 110-subject public corpus.

---

## B. Subject / session structure

- Unique subjects: **110** (`P001`–`P110`; canonical IDs `dataset-10_5281_zenodo_18599983-pNNN`)
- Source-explicit sessions: **0**. A0 derived one normalized session per subject.
- Recordings: **440** = 110 × 4 (`Lying`/`Sitting` × `Rest`/`Post-exercise`)
- Canonical windows: **530** from all 110 subjects (no recording failed A6)
- Windows per subject: 4 (87 subjects), 7 (2), or 8 (21). Extra windows come from 90 recordings with 600 frames (60 s → two non-overlapping 30 s windows)
- Frame-count strata: 348 × 500 frames, 90 × 600, 2 × 400
- Multiple recordings belong to the same subject: **yes**, always four. Split unit is subject, so all four stay together.

---

## C. Label / reference structure

Historical B classes are **derived SafeNest mappings**, not source-native class names.

| Target | Original source | How derived | Direct or generated | Thresholds | Granularity | Regenerable? |
|---|---|---|---|---|---|---|
| `NORMAL` | Movesense chest ACC magnitude spectrum | SafeNest peak RR in 0.1–0.7 Hz; 10 ≤ RR < 25 bpm and no non-breathing overlap | Generated | 10 / 25 bpm | window | YES from zip ACC + A4 mapper |
| `RAPID_OR_ABNORMAL` | same ACC RR | RR ≥ 25 or RR < 10 | Generated | 10 / 25 bpm | window | YES |
| `APNEA` (proxy, not clinical) | `non_breathing_ts.csv` | voluntary breath-hold overlap ≥ 6 s (event duration ≥ 8 s) | Generated from source intervals | 6 s / 8 s | window | YES from zip annotations |
| `AMBIGUOUS` | transition / partial overlap | A4 transition rule; excluded from pure-class training | Generated | A4 profile | window | YES |
| Window RR (`rr_bpm`) | Movesense ACC waveform | SafeNest spectral peak; stored on every A6 window | Generated | search band 0.1–0.7 Hz | window | YES; values already in `full_window_manifest.jsonl` |
| Non-breathing intervals | source CSV | ISO-8601 begin/end vs radar start | Direct source | n/a | event | YES in zip |
| Posture / activity | path (`Lying`/`Sitting`, `Rest`/`Post-exercise`) | inferred | Direct path evidence | n/a | recording | YES |
| ECG | `movesense_ecg.csv` in all 440 recordings | unused by A4/A6 | Direct source, unused | n/a | recording | YES in zip; no SafeNest ECG target exists |
| Demographics | official `ParticipantsInfo.xlsx` | not local | n/a | n/a | subject | NOT locally verifiable |

A6 window counts: APNEA 213, NORMAL 149, RAPID_OR_ABNORMAL 119, AMBIGUOUS 49. Mapping rules: 213 apnea-proxy, 149 normal, 99 tachypnea, 20 bradypnea, 49 transition. Pure-class eligible: TRAIN 327 / VAL 79 / LOCKED_TEST 75.

RR on all 530 windows: 6.0–42.0 bpm. A future non-3-class target (RR regression, event detection, quality gate) can start from ACC waveforms, stored RR, and non-breathing intervals without using B model outputs.

---

## D. Signal representation inventory

| Asset / signal level | Location | Available? | Subject identity | Labels / reference | Timing | New-track reuse |
|---|---|---|---|---|---|---|
| Official Zenodo record | DOI `10.5281/zenodo.18599983` | AVAILABLE (remote identity verified in A0) | P001–P110 | companion xlsx remote-only | n/a | re-download official zip if container identity must match Zenodo |
| Local source archive | `datasets/raw_archives/external_datasets/db_records.zip` | AVAILABLE, `LOCAL_ONLY_EXPECTED` | yes | ACC, ECG, non-breathing CSV | ISO-8601 `radar_timestamps.csv` | **highest upstream radar payload** |
| Raw ADC / IF samples | not in archive | NOT_AVAILABLE | n/a | n/a | n/a | cannot reconstruct pre-FFT radar |
| Complex range-FFT | `radar_rFFTs.zlib` inside zip; decode `scripts/mmwave_rfft_reader.py` | AVAILABLE in zip; not persisted decoded | yes | n/a | aligned 1:1 with timestamps | rerun A1; shape `[frames, 8, 64]` complex128 |
| Selected complex range-bin series | A2/A6 provenance only | DERIVABLE | yes | n/a | native frames | reuse `selected_range_bin_index` + `selected_virtual_channel` or re-select |
| Wrapped phase | not persisted | DERIVABLE (`np.angle`) | yes | n/a | native | intermediate only |
| Unwrapped full-recording phase | computed in A2/A6, **not saved** as an array | DERIVABLE | yes | n/a | native 10 Hz, 40/50/60 s | **recommended M-N2 branch** |
| Canonical respiration phase windows | `datasets/mmwave/processed/mmwave_canonical_real_v1.npy` (530×300 float64) | AVAILABLE, tracked | yes via JSONL | A6 window labels + RR | 10 Hz / 30 s after tail drop | pre-BPF fallback if new window policy is not required |
| Window / provenance manifests | `datasets/mmwave/manifests/a6_full_conversion/full_window_manifest.jsonl`, `full_provenance_manifest.jsonl` | AVAILABLE | yes | yes | start/end timestamps | identity, RR, bin/channel, split |
| Historical BPF output | generated on the fly by `scripts/mmwave_m_b1_preprocessing.py` | DERIVABLE from canonical npy; no standalone BPF dataset | via A6 | B classes | locked 300 samples | HISTORICAL_B_SPECIFIC |
| B-stage 300-sample BPF_ZSCORE tensors | not a canonical file; scaler in M-B11 lock | DERIVABLE | via A5/A6 | B 3-class | 10 Hz / 300 | do not define the new contract |
| Synthetic smoke NPZ | `datasets/mmwave/processed/mmwave_respiration_v1.npz` | AVAILABLE | synthetic groups | synthetic 3-class | 10 Hz / 300 | **not public data** |
| Subject split | `datasets/mmwave/splits/mmwave_real_subject_split_v1.json` | AVAILABLE | yes | n/a | n/a | historical grouping evidence |
| Reference ACC / ECG / events | inside zip | AVAILABLE | yes | yes | sensor clocks vs radar t0 | independent targets |

Classification used above: AVAILABLE = present now; DERIVABLE = reconstructable with existing scripts; NOT_AVAILABLE = never preserved.

---

## E. Historical preprocessing lineage

```text
PUBLIC SOURCE (Zenodo 10.5281/zenodo.18599983)
    local zip: datasets/raw_archives/external_datasets/db_records.zip
        ↓  A0 inventory  (scripts/audit_mmwave_raw_inventory.py)
    radar_rFFTs.zlib + radar_timestamps.csv + radar_chirpConfig.json
        ↓  A1  scripts/mmwave_rfft_reader.py   (RFFT_DECODER_PROFILE_001)
    complex range-FFT  [frames, 8, 64]  native ~10 Hz
        ↓  A2  scripts/mmwave_phase_extractor.py
           bin/channel select → np.angle → np.unwrap
    unwrapped respiration phase (radians), unfiltered, unnormalized
        ↓  A3  scripts/mmwave_timeline.py
           native 10 Hz kept (A6 resampling_performed = 0 / 440)
           30 s non-overlap windows, drop incomplete tail
    canonical windows 530 × 300
        + A4  scripts/mmwave_label_mapper.py  (ACC RR + breath-hold proxy)
        + A5  scripts/mmwave_subject_split.py (immutable subject split)
        ↓  A6  scripts/mmwave_full_converter.py
    mmwave_canonical_real_v1.npy   ← UNFILTERED_UNNORMALIZED_PHASE
        ↓  B1  scripts/mmwave_m_b1_preprocessing.py  (selected BPF_ZSCORE)
    TRAIN-fitted z-score after 0.1–0.5 Hz Butterworth
        ↓  B3–B12 models
    historical B candidate  (immutable offline artifact)
```

| Transform | Script | Input | Output | Deterministic? | Parameters preserved? | Rerunnable? |
|---|---|---|---|---|---|---|
| A1 decode | `mmwave_rfft_reader.py` | zlib pickle-5 payload | complex tensor + rBins | yes (allowlisted pickletools VM) | `RFFT_DECODER_PROFILE_001` | yes from zip |
| A2 phase | `mmwave_phase_extractor.py` | complex rFFT | unwrapped phase + bin/channel | yes | `MMWAVE_PHASE_EXTRACTION_PROFILE_001`; A6 search 0.3–1.91 m | yes; full phase not persisted |
| A3 window | `mmwave_timeline.py` | phase + timestamps | 300-sample windows | yes | `MMWAVE_TIMELINE_PROFILE_001` | yes; tails dropped in canonical npy |
| A4 labels | `mmwave_label_mapper.py` | ACC + `non_breathing_ts.csv` | window class + RR | yes | `MMWAVE_LABEL_MAPPING_PROFILE_001` | yes |
| A5 split | `mmwave_subject_split.py` | subject IDs, seed 20260808 | TRAIN/VAL/LOCKED_TEST | yes | `MMWAVE_SUBJECT_SPLIT_PROFILE_001` | do not overwrite; new track gets a new profile if regrouped |
| A6 pack | `mmwave_full_converter.py` | A1–A5 | npy + JSONL | yes | `MMWAVE_FULL_CONVERSION_PROFILE_001` | yes |
| B1 BPF_ZSCORE | `mmwave_m_b1_preprocessing.py` | canonical npy | filtered/z-scored 300-vectors | yes | M-B11: mean `0.003116…`, std `2.955399…`, TRAIN 327 windows | historical only |

A6 quality: all 530 windows `TIMELINE_EXACT_NATIVE_10HZ`; interpolated samples 0; large gaps 0; failed recordings 0. Only warnings: 350 incomplete tails.

---

## F. New representation branch point

```text
PUBLIC SOURCE (range-FFT zip)
    ↓
COMPLEX RANGE-FFT          ← highest-quality reusable radar level
    ↓
UNWRAPPED NATIVE PHASE     ← NEW_REPRESENTATION_BRANCH_POINT
    ├── historical A3/A6 30 s windows → canonical npy → BPF_ZSCORE → B model
    │     (preserve as history; do not inherit automatically)
    └── future M-N2        (not executed in PUBLIC-P0)
```

**NEW_REPRESENTATION_BRANCH_POINT = native-rate unwrapped respiration phase (A2 output), re-derived from local `radar_rFFTs.zlib`.**

Reason:

- Complex range-FFT is the earliest preserved radar signal and can support a different bin/channel policy.
- A common PUBLIC↔MR60 respiratory representation cannot be range-FFT itself (MR60 runtime exposes vendor `breath_phase`, not complex rFFT). PUBLIC-P0 does not choose that common form.
- Full-length unwrapped phase is upstream of BPF, z-score, and the 30 s / 300-sample contract.
- If M-N2 accepts historical windowing, `mmwave_canonical_real_v1.npy` is a sufficient persisted pre-BPF fallback.

Can M-N2 bypass historical BPF_ZSCORE: **YES**. Canonical npy is unfiltered and unnormalized. B1 transforms are applied later and are not baked into the public source.

### Historical B assumptions vs new-track freedom

| Historical assumption | Can new pipeline avoid / recompute it? | Source available? |
|---|---|---|
| 10 Hz canonicalization | PARTIAL. Native radar frame rate is already 10 Hz (`PERIODICITY` 100 ms; all A6 windows exact native 10 Hz). Cannot recover ADC-rate timing. Can resample the 10 Hz series differently. | YES — `radar_timestamps.csv` |
| 300-sample window | YES if re-extracting A2 phase; NO if using only canonical npy | zip YES / npy locked |
| 30 s window | YES if re-extracting; NO if only npy. Canonical npy dropped 20 s tails on 348 recordings and 10 s on 2 recordings. | zip YES / npy locked |
| BPF 0.1–0.5 Hz | YES | canonical npy is pre-BPF |
| z-score / global TRAIN scaler | YES | canonical npy unnormalized; B scaler is historical |

---

## G. Timing reconstruction capability

**TIMING_RECONSTRUCTION = PARTIAL**

Present:

- Per-frame ISO-8601 timestamps in the zip (500/600/400 frames)
- Native median dt 0.1 s, empirical 10.0 Hz, no A6 interpolation or large-gap fill
- Recording start/end in A6 recording results
- Window start/end on every canonical row

Limits:

- Source timezone unverified; do not treat a trailing `Z` as proven UTC
- Two recordings are 40 s (400 frames)
- Canonical npy permanently drops incomplete tails
- No raw ADC clock exists above the 10 Hz frame grid

M-N2/M-N3 can rebuild a window policy from zip timestamps + re-derived A2 phase. They cannot claim a finer native radar sampling rate than 10 Hz.

---

## H. Historical split lineage

Machine-readable split: `datasets/mmwave/splits/mmwave_real_subject_split_v1.json`  
Profile: `MMWAVE_SUBJECT_SPLIT_PROFILE_001`, seed `20260808`, SHA-256 `a1996ea00a1d5066eae6d25f022d04137085434d4768e27cbebcdad4e0385baa`  
Grouping unit: **subject**. Adjacent non-overlapping windows from one 60 s recording stay in the same split. A6 leakage audit: 0 cross-split subject / recording / window-id / exact-signal overlap.

| Split | Subjects | Recordings | Structural windows | Pure-class eligible |
|---|---:|---:|---:|---:|
| TRAIN | 77 | 308 | 358 | 327 |
| VALIDATION | 17 | 68 | 84 | 79 |
| LOCKED_TEST | 16 | 64 | 88 | 75 |

LOCKED_TEST IDs (historical evidence only; do not use for new-model selection): p017, p019, p023, p029, p033, p039, p044, p046, p055, p059, p063, p067, p079, p086, p091, p101.

VALIDATION IDs: p009, p012, p013, p016, p024, p025, p027, p031, p036, p047, p050, p060, p073, p074, p075, p087, p104.

Held-out limitation (M-B10R0): **all 110 subjects are assigned**. `independent_existing_holdout_available: false`. Historical LOCKED_TEST was later consumed by M-B10B / M-B10R1B. A new `NEW_MODEL_HELDOUT_TEST` can still be created as a **new derived-track grouping**, but it cannot be described as project-wide unused subjects. PUBLIC-P0 does not design that split.

---

## I. Reusable vs B-specific assets

### REUSABLE_FOR_NEW_TRACK

- Local zip range-FFT, timestamps, chirp config
- Subject/recording IDs (`P001`–`P110` and canonical forms)
- Movesense ACC waveforms, stored window RR, non-breathing intervals, unused ECG
- A1 reader, A2 phase extractor, A3 timeline utilities, A4 RR/event parsers, A5 grouping utilities
- Canonical unfiltered phase npy + A6 JSONL provenance
- Historical split file as **lineage evidence** (not automatically the new contract)
- Generic metrics in `scripts/evaluate_mmwave.py` (`compute_metrics`)
- Conv1D+GAP *pattern* in `scripts/mmwave_m_b3_architecture.py` (not the frozen B weights)

### HISTORICAL_B_SPECIFIC (immutable; do not define the new contract)

- Selected `BPF_ZSCORE` (`M-B1_D0_B1_Z1`) and TRAIN scaler mean/std
- 300-sample / 30 s / `[1,300,1]` runtime tensor contract
- Historical 3-class mapping and B models/TFLite under `models/mmwave/`
- `preprocessing/mmwave.py` experimental 7-stage path (includes synthetic-era scaler and ±5 clip)
- `inference/mmwave_interpreter.py` BPF_ZSCORE live path
- Synthetic `mmwave_respiration_v1.npz` and `mmwave_group_split_v1.json`
- B experiment prediction/weight npz files

### Generic code reuse (inspect-only classification)

Reusable later: `mmwave_rfft_reader.py`, `mmwave_phase_extractor.py`, `mmwave_timeline.py` (policy is profile-driven), `mmwave_label_mapper.py` (RR/event extractors more than the 3-class map), `mmwave_subject_split.py`, `evaluate_mmwave.py` metrics, TFLite load helpers if retargeted.

B-specific: hardcoded `[1,300,1]`, 10 Hz / BPF_ZSCORE contracts in M-B1–B12 and `inference/mmwave_interpreter.py`, old scaler constants, old class map, `train_mmwave.py` synthetic path.

---

## J. M-N2 readiness conclusion

M-N2 can construct new public-side representations from data **upstream of historical BPF_ZSCORE**. The public corpus is not merely an old B artifact.

Recommended public-data starting point:

1. Re-derive native-rate unwrapped phase from the local zip with A1+A2 (keep A2 bin/channel provenance unless a new selection policy is explicitly studied).
2. Keep canonical 530×300 windows as the pre-BPF fallback if a new window policy is out of scope.
3. Keep ACC RR, non-breathing intervals, and subject IDs as independent supervision resources.
4. Do not start from BPF_ZSCORE tensors, B scaler constants, or the synthetic NPZ.

Main limitations: no raw ADC; full-length phase is not persisted (must re-run A1+A2); native rate is already 10 Hz; local zip is a repackaged container vs official Zenodo hash; demographics xlsx is not local; no globally pristine unused subjects.

### Decision questions

| ID | Question | Answer |
|---|---|---|
| Q1 | Can M-N2 generate a NEW common representation from data upstream of historical BPF_ZSCORE? | **YES** |
| Q2 | Highest-quality reusable signal level? | Complex range-FFT in the local zip. Practical respiratory starting point: native unwrapped phase (A2). Persisted pre-BPF fallback: canonical 530×300 phase windows. |
| Q3 | Are subject identities sufficient for subject-wise grouping? | **YES** |
| Q4 | Are original/reference targets available independently of historical B class mapping? | **PARTIAL** (ACC waveforms + stored RR + event intervals + unused ECG; 3-class labels themselves are derived) |
| Q5 | Can timing/window assumptions be redefined? | **PARTIAL** (windows yes from zip; native 10 Hz is a source constraint) |
| Q6 | Can historical B-specific preprocessing be bypassed? | **YES** |
| Q7 | Most important public-data limitation for M-N2? | Full-length unwrapped phase is not persisted, and no source-level unused subjects remain; M-N2 must re-derive phase from the local zip and treat any new held-out grouping as a new derived track, not a pristine global holdout. |

Final status: **PUBLIC_P0_READY_WITH_LIMITATIONS**

M-N2 is not started by this document.
