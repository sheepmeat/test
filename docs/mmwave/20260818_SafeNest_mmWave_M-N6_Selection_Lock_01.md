# SafeNest M-N6 Stage A — VAL-only candidate lock

- Date: 2026-08-18
- Phase: **M-N6 Stage A only**. Heldout is not opened in this commit.
- Selection ID: `MMWAVE_M_N6_SELECTED_FLOAT_V1`
- Lock: `config/mmwave/m_n6_selected_candidate_lock.json`

This document records the pre-heldout selection. It does not contain
`NEW_MODEL_HELDOUT_TEST` metrics.

---

## Candidates considered

M-N5 primary families, seeds 42 and 2026, frozen contract
`MMWAVE_MR60_COMPAT_INPUT_DATASET_V1`. Linear diagnostic excluded.

Heldout inference before this lock: **0**.

## Selection rule

1. Family: mean VAL Macro F1 across the two fixed seeds, requiring both seeds
   non-degenerate. Tie-break: less RAPID weakness, less seed instability,
   smaller parameter count.
2. Exact run: highest VAL Macro F1 inside the selected family. Tie-break:
   higher RAPID recall, higher minimum class recall, lower parameter count.

VAL accuracy is not the ranking criterion. No new seed, ensemble, or
TRAIN+VAL retrain.

## Family comparison (committed M-N5 VAL)

| Family | Mean VAL Macro F1 | Seed F1 Δ | Mean RAPID recall | Params |
|---|---:|---:|---:|---:|
| DILATED_CONV1D_GAP_TINY | 0.696978 | 0.052759 | 0.350 | 5019 |
| CONV1D_GAP_TINY | 0.662842 | 0.026459 | 0.350 | 5051 |
| SMALL_MLP_BASELINE | 0.342800 | 0.078074 | 0.200 | 7811 |

Selected family: **`M-N5_DILATED_CONV1D_GAP_TINY`**.

Inside that family, seed **2026** (VAL Macro F1 0.723358, RAPID recall 0.400)
beats seed 42 (0.670599 / 0.300).

## Frozen exact artifact

```text
candidate_id:     M-N5_DILATED_CONV1D_GAP_TINY
seed:             2026
parameter_count:  5019
VAL accuracy:     0.771429
VAL Macro F1:     0.723358
NORMAL recall:    0.888889
RAPID recall:     0.400000
APNEA-proxy recall: 0.937500
SHA-256:          9de3818c0f4854f8512c9d390d290938b6e562d590e0775cb1dab885cc72e2ab
size:             96309
source:           tmp/mmwave_m_n5/models/M-N5_DILATED_CONV1D_GAP_TINY_seed2026.keras
locked copy:      models/mmwave/m_n6/MMWAVE_M_N6_SELECTED_FLOAT_V1.keras
```

After this commit, architecture, seed, and artifact SHA are immutable for the
M-N6 heldout evaluation. Stage B may evaluate only this identity.

This is `M_N6_SELECTED_FLOAT_CANDIDATE`, not a production or device-validated
model.
