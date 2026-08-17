# SafeNest M-N5 — Small Candidate Model Training

- Date: 2026-08-18
- Phase: **M-N5 only**. No final model selection. No M-N6 heldout evaluation.
- Frozen input contract: `MMWAVE_MR60_COMPAT_INPUT_DATASET_V1`
- Authoritative contract: `config/mmwave/m_n4_canonical_input_dataset_contract.json`
- Training recipe: `config/mmwave/m_n5_training_recipe.json`
- Executable: `scripts/mmwave_m_n5_train_candidates.py`
- Candidate manifest: `datasets/mmwave/manifests/m_n5_candidate_runs.json`
- Float artifacts (gitignored): `tmp/mmwave_m_n5/models/`

M-N5 trains a small reproducible candidate set under the frozen M-N4 input/data contract. It does not reopen representation, timing, window, rate, scale, labels, or the subject split.

---

## 1. Frozen M-N4 input used

```text
Contract:        MMWAVE_MR60_COMPAT_INPUT_DATASET_V1
Representation:  R2 time-aware first derivative
Timing:          phase-update-aware
Window:          30 s
Rate:            8 Hz
Samples:         240
Input shape:     [1,240,1]  (training tensors [N,240,1] float32)
Scale:           WINDOW_LOCAL_MAD (divide-only, no centering)
Smoothing:       NONE
```

Canonical windows were formed with `canonical_from_public_native` in `scripts/mmwave_m_n4_canonical.py`. Historical B `[1,300,1]` / `BPF_ZSCORE` / 0.1–0.5 Hz was not substituted. The M-N4 contract JSON was not modified.

`APNEA` remains the voluntary breath-hold / Movesense-reference-derived proxy target. It is not clinical apnea diagnosis.

---

## 2. TRAIN / VAL counts

Public subject-wise split `MMWAVE_MR60_COMPAT_SUBJECT_SPLIT_V1` was reused unchanged.

| Split | Subjects | Supervised windows | NORMAL | RAPID_OR_ABNORMAL | APNEA proxy |
|---|---:|---:|---:|---:|---:|
| TRAIN | 77 | 337 | 106 | 82 | 149 |
| VAL | 17 | 70 | 18 | 20 | 32 |

- Tensor shape: TRAIN `[337,240,1]`, VAL `[70,240,1]`, dtype `float32`, finite fraction `1.0`
- Subject overlap: **0**
- Canonical transform failures: **0**
- AMBIGUOUS windows: excluded from supervised TRAIN and VAL metrics
- Team MR60: not used as supervised TRAIN or VAL
- `NEW_MODEL_HELDOUT_TEST`: 16 subjects / 74 supervised windows **not materialized and not inferred**

---

## 3. Three primary candidate architectures

Same recipe, no architecture search.

| Candidate | Graph | Trainable params |
|---|---|---:|
| `M-N5_SMALL_MLP_BASELINE` | Flatten → Dense(32, ReLU) → Dropout(0.20) → Dense(3, Softmax) | 7,811 |
| `M-N5_CONV1D_GAP_TINY` | Conv1D(16,k7) → Conv1D(24,k5,s2) → Conv1D(24,k5) → GAP → Dense(3) | 5,051 |
| `M-N5_DILATED_CONV1D_GAP_TINY` | Conv1D(16,k5,d1) → Conv1D(24,k5,d2) → Conv1D(24,k5,d4) → GAP → Dense(3) | 5,019 |

All three are below the 50,000-parameter budget. Dilated Conv1D used standard TFLite-friendly `Conv1D(dilation_rate=...)`; no operator substitution was required.

Optional diagnostic only (not a production candidate): `M-N5_LINEAR_DIAGNOSTIC` = Flatten → Dense(3, Softmax), 723 params, seed 42.

---

## 4. Fixed training recipe

Applied identically to all three primary families:

```text
optimizer:       Adam
learning_rate:   1e-3
loss:            SparseCategoricalCrossentropy
class weighting: UNWEIGHTED
batch_size:      32
maximum_epochs:  120
early_stopping:  val_loss, patience=15, restore_best_weights=true
thresholds:      none (argmax softmax)
```

No learning-rate, batch-size, scheduler, oversampling, class-weight, or focal-loss search.

---

## 5. Two fixed seeds

Seeds **42** and **2026** only. Six primary runs. No extra seeds.

Python / NumPy / TensorFlow seeds were set. `tf.config.experimental.enable_op_determinism()` succeeded on this machine (`TF 2.20.0`). Bitwise identity across platforms is not claimed.

---

## 6. VAL results

VAL is a development set used for early stopping and candidate diagnostics. It is not a final test set.

| Candidate | Seed | Params | Best epoch | VAL Acc | VAL Macro F1 | NORMAL recall | RAPID recall | APNEA-proxy recall | Status |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| SMALL_MLP_BASELINE | 42 | 7811 | 8 | 0.443 | 0.382 | 0.278 | 0.200 | 0.688 | NON_DEGENERATE |
| SMALL_MLP_BASELINE | 2026 | 7811 | 17 | 0.329 | 0.304 | 0.278 | 0.200 | 0.438 | NON_DEGENERATE |
| CONV1D_GAP_TINY | 42 | 5051 | 113 | 0.700 | 0.650 | 0.778 | 0.350 | 0.875 | NON_DEGENERATE |
| CONV1D_GAP_TINY | 2026 | 5051 | 87 | 0.729 | 0.676 | 0.833 | 0.350 | 0.906 | NON_DEGENERATE |
| DILATED_CONV1D_GAP_TINY | 42 | 5019 | 109 | 0.729 | 0.671 | 0.944 | 0.300 | 0.875 | NON_DEGENERATE |
| DILATED_CONV1D_GAP_TINY | 2026 | 5019 | 116 | 0.771 | 0.723 | 0.889 | 0.400 | 0.938 | NON_DEGENERATE |

Linear diagnostic (seed 42): VAL Macro F1 `0.265`, RAPID recall `0.050`. The frozen window is not trivially linearly separable.

Primary compact metric: **Macro F1**, not accuracy. VAL Macro F1 range across the six primary runs: **0.304 – 0.723**.

---

## 7. Seed sensitivity

- `SMALL_MLP_BASELINE`: Macro F1 0.382 vs 0.304 (Δ ≈ 0.078). Weak and seed-moved; still predicted all three VAL classes.
- `CONV1D_GAP_TINY`: 0.650 vs 0.676 (Δ ≈ 0.026). Stable.
- `DILATED_CONV1D_GAP_TINY`: 0.671 vs 0.723 (Δ ≈ 0.053). Directionally stable; seed 2026 higher on VAL.

No additional seeds were tried.

---

## 8. Class-wise weaknesses

`RAPID_OR_ABNORMAL` is the consistent weak class:

- MLP recall 0.20 on both seeds
- Conv1D-GAP recall 0.35 on both seeds
- Dilated Conv1D-GAP recall 0.30 / 0.40

This matches the M-N2/M-N3 high-RR spectral-ambiguity observation. No hand-coded RR estimator, filter, or FFT retune was added. APNEA-proxy and NORMAL are much stronger on the convolutional families (APNEA-proxy recall 0.875–0.938; NORMAL 0.778–0.944). Confusion is mainly RAPID → NORMAL.

---

## 9. Subject-aware VAL summary

| Candidate | Seed | Subjects with ≥1 correct | Median per-subject acc | Min per-subject acc |
|---|---:|---:|---:|---:|
| SMALL_MLP_BASELINE | 42 | 16 / 17 | 0.50 | 0.00 |
| SMALL_MLP_BASELINE | 2026 | 15 / 17 | 0.25 | 0.00 |
| CONV1D_GAP_TINY | 42 | 17 / 17 | 0.75 | 0.33 |
| CONV1D_GAP_TINY | 2026 | 17 / 17 | 0.75 | 0.25 |
| DILATED_CONV1D_GAP_TINY | 42 | 17 / 17 | 0.75 | 0.33 |
| DILATED_CONV1D_GAP_TINY | 2026 | 17 / 17 | 0.75 | 0.33 |

Per-subject Macro F1 was not invented for subjects that lack all three classes.

---

## 10. Candidate viability for M-N6

```text
VIABLE_FOR_M_N6:
  M-N5_CONV1D_GAP_TINY
  M-N5_DILATED_CONV1D_GAP_TINY
  M-N5_SMALL_MLP_BASELINE   (weak non-collapsed reference only)

NOT_VIABLE:
  (none of the six primary runs collapsed)

FINAL_SELECTED_MODEL:
  NO
```

The two convolutional families are the credible M-N6 candidates: non-degenerate, finite, Macro F1 0.65–0.72, all VAL subjects have at least one correct window. MLP is retained as a non-collapsed baseline so M-N6 can discard it on VAL without using heldout. Linear diagnostic is not a production candidate.

M-N6 owns VAL-based selection and the first `NEW_MODEL_HELDOUT_TEST` evaluation.

---

## Heldout non-use

```text
NEW_MODEL_HELDOUT_TEST_INFERENCE = 0
heldout tensors materialized = 0
heldout performance inspected = NO
heldout used for architecture / seed / threshold / class-weight selection = NO
```

Index identity counts for the 16 heldout subjects remain those frozen by M-N4. No heldout waveforms, predictions, or confusion matrices were produced.

---

## Focused validation

| Check | Result |
|---|---|
| Canonical TRAIN/VAL shape `[N,240,1]` | PASS |
| Finite tensors | PASS |
| Subject isolation (overlap 0; 77 / 17) | PASS |
| Three-class presence in TRAIN and VAL | PASS |
| Model I/O `(None,240,1)` → `(None,3)` and reload | PASS |
| Probability finite / row-sum ≈ 1 | PASS |
| Manifest ↔ code candidate IDs / contract | PASS |

---

## Gate

```text
M-N5 = PASS_WITH_LIMITATIONS
M-N6 authorized = YES
Production/final model selected = NO
```

Limitations that do not block M-N6: `RAPID_OR_ABNORMAL` recall remains low on every family; MLP is seed-moved and near chance on seed 2026; APNEA remains a breath-hold-derived proxy; Team MR60 is still unsupervised-ineligible; bitwise training determinism is not claimed across platforms.

Do not reopen M-N4 in response to the RAPID weakness.
