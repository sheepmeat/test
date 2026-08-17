# SafeNest M-N4 — Canonical Input and Dataset Strategy Freeze

- Study ID: `MMWAVE_MR60_COMPAT_INPUT_DATASET_V1`
- Date: 2026-08-18
- Phase: **M-N4 only**. No training. No M-N5 architecture work.
- Authoritative contract: `config/mmwave/m_n4_canonical_input_dataset_contract.json`
- Executable transform/split: `scripts/mmwave_m_n4_canonical.py`
- Split: `datasets/mmwave/splits/mmwave_mr60_compat_subject_split_v1.json`
- Window index: `datasets/mmwave/manifests/m_n4_canonical/window_index.jsonl`

```text
PREDECESSOR_PUBLICATION_STATE:
LOCAL_COMMITTED_PENDING_GITHUB_PUBLICATION
```

M-N4 freezes M-N3. It does not reopen representation, filter, or peak-picker research.

---

## Exact frozen contract

```text
CONTRACT_ID:
MMWAVE_MR60_COMPAT_INPUT_DATASET_V1

SOURCE_PUBLIC:
A2_NATIVE_UNWRAPPED_PHASE

SOURCE_MR60:
0x0A13_BREATH_PHASE

MR60_PHASE_UPDATE_ESTIMATE:
ts_monotonic_ms - phase_age_ms

UPDATE_ADVANCE_TOLERANCE_MS:
8

REPRESENTATION:
TIME_AWARE_FIRST_DERIVATIVE

DERIVATIVE_FORMULA:
dt_s = (t_update_ms[i] - t_update_ms[i-1]) / 1000
r2[i] = (x[i] - x[i-1]) / dt_s
timestamp(r2[i]) = t_update[i]
first event in a segment: no sample
no derivative across a gap/reset

GAP_RULE:
reject window if any accepted interval in the completed 30 s window
> max(0.40 s, 4 × median_update_dt)
median_update_dt = median of those completed-window intervals
minimum 8 intervals or reject
not a whole-recording or future statistic

NOISE_HANDLING:
NONE

RESAMPLING:
LINEAR after R2, then S1

TARGET_RATE_HZ:
8

WINDOW_SECONDS:
30

SAMPLE_COUNT:
240

EDGE_HOLD_MAX_SECONDS:
0.250

SCALE:
WINDOW_LOCAL_MAD

MAD_FORMULA:
m = median(r)
MAD = median(abs(r - m))
normalized = r / MAD

MAD_EPSILON:
1e-6
comparison: MAD < 1e-6

MAD_NEAR_ZERO_BEHAVIOR:
ZERO_TENSOR

INPUT_SHAPE:
[1,240,1]

INPUT_CHANNELS:
1

INPUT_DTYPE_BEFORE_TRAINING:
float32

TARGET_POLICY:
MMWAVE_LABEL_MAPPING_PROFILE_001
0 NORMAL / 1 RAPID_OR_ABNORMAL / 2 APNEA-proxy

AMBIGUOUS_POLICY:
exclude from supervised TRAIN/VAL/NEW_MODEL_HELDOUT_TEST metrics
retain in lineage

PUBLIC_SPLIT_UNIT:
SUBJECT

TEAM_MR60_SUPERVISED_TRAINING:
DISALLOWED
```

8 ms is an update-estimate jitter tolerance. It is not an MR60 frame period.

Equal numeric `breath_phase` is not automatic republication.

Production inference without `phase_age_ms`: **WINDOW_UNAVAILABLE**. No silent row-count fallback.

M-N3 30 s × 10 Hz = 300 is `M_N3_FALLBACK_NOT_ACTIVE`. One active shape: `[1,240,1]`. Not historical B `[1,300,1]`.

---

## Specification closures vs M-N3

| Item | M-N3 | M-N4 freeze |
|---|---|---|
| MAD | `median(abs(r-median(r)))` then `r/MAD` | same; not `(r-m)/MAD` |
| epsilon | `MAD < 1e-6` → zeros | same |
| order | R2 → resample → S1 | same |
| gap median | whole-recording in the study script | **corrected** to completed-window intervals only |
| grid | `n = round(30*8)` | `t[k]=t_start+k/8`, k=0..239 |
| edge hold | ≤ 2 bins | 0.250 s |
| missing freshness | not production-frozen | WINDOW_UNAVAILABLE |

The M-N3 study script remains historical evidence. M-N5 must import `scripts/mmwave_m_n4_canonical.py`, not re-derive gap medians from a full recording.

---

## Public dataset strategy

Reuse A6 **30 s non-overlapping window identities and A4 labels**. Recompute the waveform. Do not reuse BPF_ZSCORE arrays.

New subject split, not a copy of historical A5:

- algorithm: `SHA256(MMWAVE_MR60_COMPAT_INPUT_DATASET_V1:20260818:subject_id)` then largest remainder
- TRAIN 77 / VAL 17 / NEW_MODEL_HELDOUT_TEST 16
- overlap 0
- all three supervised classes present in TRAIN and VAL

| Split | Subjects | Recordings | Windows | Supervised eligible | AMBIGUOUS |
|---|---:|---:|---:|---:|---:|
| TRAIN | 77 | 308 | 370 | 337 | 33 |
| VAL | 17 | 68 | 76 | 70 | 6 |
| NEW_MODEL_HELDOUT_TEST | 16 | 64 | 84 | 74 | 10 |

`NEW_MODEL_HELDOUT_TEST` is a **new-track frozen heldout**. It is not project-wide pristine. M-N5 must not use it for architecture, weighting, thresholds, seeds, or early stopping.

AMBIGUOUS windows stay in the index with `supervised_eligible=false`.

---

## Team MR60

Physical subjects: 1. Supervised Team recordings: 0.

M-N2/M-N3 development-reference sessions remain those ten occupied/empty/desk-work/paced files listed in the contract JSON.

Reserved `MR60_HELDOUT_REFERENCE` (same person, unused in M-N2/M-N3 selection, `phase_age_ms` present):

- `LEGACY_2026-07-28_empty_v2_360s`
- `LEGACY_2026-07-25_occupied_d09_60s`
- `LEGACY_2026-07-25_occupied_front_d06_60s`

Meaning: **SAME_SUBJECT_LIMITED_DEVICE_REFERENCE** for M-N7. Not unseen-person validation. Not independent respiratory GT.

Recent Pi remains `RECENT_PI_RUNTIME_REFERENCE` only.

---

## Canonical build

M-N5 entry point: `canonical_from_public_native` / `form_canonical_window` in `scripts/mmwave_m_n4_canonical.py` plus A1/A2 via existing readers and A6 provenance bin/channel.

TRAIN/VAL tensors are not committed. Policy: local `tmp/` or gitignored processed payloads. The freeze commits contract, split, window index, code, and this report.

---

## Focused validation

- `tests/test_mmwave_m_n4_canonical.py`
- 240-sample grid, MAD-zero, gap reject, boot reject, production missing-age, split isolation, JSON/code agreement
- optional one TRAIN public window through A1/A2 if `db_records.zip` is present
- no heldout RR/performance inspection

---

## Gate

```text
M-N4 = PASS_WITH_LIMITATIONS
M-N5 authorized = YES
Production model trained = NO
```

Limitations that do not block M-N5: one Team subject; no Team respiratory GT; new-track heldout is not project-pristine; high-RR model behavior is still M-N5/M-N6; some legacy Team files lack production freshness.

---

## GitHub recovery

Do not open one PR from `work/mmwave-m-n4-premerge`. Transplant only this M-N4 commit after M-N0..M-N3 are on canonical main.
