# SafeNest M-N6 — Selection lock + controlled heldout evaluation

- Date: 2026-08-18
- Phase: **M-N6 only**. No M-N7 Team MR60 evaluation. No production release.
- Contract: `MMWAVE_MR60_COMPAT_INPUT_DATASET_V1`
- Selection ID: `MMWAVE_M_N6_SELECTED_FLOAT_V1`
- Stage A lock: `config/mmwave/m_n6_selected_candidate_lock.json`
- Stage A commit: `32840159e6a1ad90eda664117f7fea648cb369c8`
- Heldout result: `datasets/mmwave/manifests/m_n6_heldout_result.json`

This is `M_N6_SELECTED_FLOAT_CANDIDATE`. It is not a production, device-validated,
or release model. `APNEA` remains a voluntary breath-hold / reference-derived
proxy, not clinical apnea diagnosis.

---

## 1. Candidates that existed

M-N5 trained three primary families × seeds 42 and 2026 on PUBLIC TRAIN/VAL
only. Heldout inference in M-N5 was 0.

| Family | Mean VAL Macro F1 | Seed 42 / 2026 F1 | RAPID recall |
|---|---:|---|---|
| SMALL_MLP_BASELINE | 0.343 | 0.382 / 0.304 | 0.20 / 0.20 |
| CONV1D_GAP_TINY | 0.663 | 0.650 / 0.676 | 0.35 / 0.35 |
| DILATED_CONV1D_GAP_TINY | 0.697 | 0.671 / 0.723 | 0.30 / 0.40 |

---

## 2. Selection rule (fixed before heldout)

Family: **mean VAL Macro F1 across the two fixed seeds**, both seeds
non-degenerate. Secondary: RAPID weakness, seed instability, parameter count.

Exact run: **highest VAL Macro F1 inside that family**. Secondary: RAPID
recall, minimum class recall, parameter count.

No new seed, ensemble, weight averaging, or TRAIN+VAL retrain.

---

## 3. Family that won on VAL only

`M-N5_DILATED_CONV1D_GAP_TINY` (mean VAL Macro F1 0.697 vs Conv1D 0.663 vs MLP 0.343).

---

## 4. Exact seed / artifact selected

```text
candidate:   M-N5_DILATED_CONV1D_GAP_TINY
seed:        2026
params:      5019
VAL Acc:     0.771429
VAL Macro F1: 0.723358
NORMAL recall: 0.888889
RAPID recall:  0.400000
APNEA-proxy recall: 0.937500
SHA-256: 9de3818c0f4854f8512c9d390d290938b6e562d590e0775cb1dab885cc72e2ab
locked copy: models/mmwave/m_n6/MMWAVE_M_N6_SELECTED_FLOAT_V1.keras
```

---

## 5. Proof selection was locked before heldout

Git history on this branch:

1. `32840159e6a1ad90eda664117f7fea648cb369c8` — `mmwave: lock M-N6 candidate before heldout`
2. this report / heldout result commit — after first inference

The Stage A lock records `heldout_inference_before_lock = 0`. Stage B printed
that lock identity **before** materializing heldout tensors. Architecture, seed,
and SHA were not changed after seeing test metrics.

---

## 6. Heldout results

Exactly one candidate identity evaluated. 16 subjects, 74 supervised windows
(NORMAL 25 / RAPID 17 / APNEA-proxy 32). AMBIGUOUS excluded. Argmax softmax.
No threshold tuning.

| Metric | Heldout |
|---|---:|
| Loss | 0.569541 |
| Accuracy | 0.756757 |
| Macro F1 | 0.708380 |
| Balanced accuracy | 0.706005 |
| NORMAL P/R/F1 | 0.606 / 0.800 / 0.690 |
| RAPID_OR_ABNORMAL P/R/F1 | 0.636 / 0.412 / 0.500 |
| APNEA-proxy P/R/F1 | 0.967 / 0.906 / 0.935 |

Confusion (rows true NORMAL, RAPID, APNEA-proxy; columns predicted):

```text
[[20, 4, 1],
 [10, 7, 0],
 [ 3, 0, 29]]
```

Predicted counts: NORMAL 33, RAPID 11, APNEA-proxy 30. Status: NON_DEGENERATE.

Subject-aware: 16/16 subjects had ≥1 correct window; median accuracy 0.75;
minimum 0.50; maximum 1.00.

---

## 7. VAL → heldout generalization gap

| | VAL | Heldout | Δ |
|---|---:|---:|---:|
| Accuracy | 0.771 | 0.757 | −0.015 |
| Macro F1 | 0.723 | 0.708 | −0.015 |
| NORMAL recall | 0.889 | 0.800 | −0.089 |
| RAPID recall | 0.400 | 0.412 | +0.012 |
| APNEA-proxy recall | 0.938 | 0.906 | −0.031 |

Public-domain generalization is close on Macro F1. The selected artifact did
not collapse on unseen subjects. This gap was **not** used to switch candidates.

---

## 8. RAPID weakness

Heldout `RAPID_OR_ABNORMAL` recall is **0.412**. Ten of 17 RAPID windows were
predicted NORMAL. This is the same class weakness seen on VAL (0.40) and in
M-N2/M-N3 high-RR ambiguity. No class-weight, threshold, R2, MAD, or runner-up
test was applied in response.

---

## 9. Implications for M-N7

The locked float candidate remains credible for **device-domain checking** on
the reserved Team MR60 reference set. M-N7 asks whether this public-trained
model behaves sensibly on real `breath_phase` evidence. It cannot claim
unseen-person validation: Team MR60 is still one physical subject.

Do not consume the M-N7 reserved sessions in this phase.

---

## 10. Heldout is consumed

```text
NEW_MODEL_HELDOUT_TEST status:
CONSUMED_ONCE_FOR_M_N6_FINAL_EVALUATION
```

It must not be reused to select architecture, seed, preprocessing, threshold,
or adaptation. Do not evaluate Conv1D, MLP, or the other Dilated seed on this
split.

---

## Gate

```text
M-N6 = PASS_WITH_LIMITATIONS
M-N7 authorized = YES
Production-final model = NO
Device validated = NO
```

Limitation: RAPID_OR_ABNORMAL recall remains ~0.41. Procedure is valid;
heldout is non-degenerate; VAL→heldout Macro-F1 gap is small (−0.015).
