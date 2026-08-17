# SafeNest M-N7 — Existing MR60 device-domain check

- Date: 2026-08-18
- Phase: **M-N7 only**. No M-N8 adaptation. No M-N9 INT8/Pi work.
- Check type: `EXISTING_MR60_DEVICE_DOMAIN_CHECK`
- Evidence class: `SAME_SUBJECT_LIMITED_DEVICE_REFERENCE`
- Contract: `MMWAVE_MR60_COMPAT_INPUT_DATASET_V1`
- Selected model: `MMWAVE_M_N6_SELECTED_FLOAT_V1`
- Result: `datasets/mmwave/manifests/m_n7_device_domain_result.json`

This is not supervised Team-MR60 accuracy validation, not unseen-person
validation, and not formal real-device release evidence. `APNEA` remains a
voluntary breath-hold / reference-derived proxy class from public training,
not clinical apnea and not an empty-room label.

---

## 1. Why M-N7 is not an accuracy test

The reserved Team MR60 evidence comes from **one physical participant** and has
**no independent respiratory ground truth**. Occupied recordings show that a
person was present. They do not prove NORMAL, RAPID, APNEA, or a true
respiration rate. Empty-room recordings show no person / device baseline.
They do not mean APNEA.

Therefore this phase does not compute Accuracy, Macro F1, recall, or a
confusion matrix on Team MR60. It asks a narrower engineering question:

> Does the exact M-N6-selected public-trained float model accept real MR60
> data through the frozen M-N4 contract and produce technically coherent,
> non-collapsed outputs in the actual device domain?

---

## 2. Exact model used

```text
selection_id:  MMWAVE_M_N6_SELECTED_FLOAT_V1
architecture:  M-N5_DILATED_CONV1D_GAP_TINY
seed:          2026
input:         [1, 240, 1]
SHA-256:       9de3818c0f4854f8512c9d390d290938b6e562d590e0775cb1dab885cc72e2ab
artifact:      models/mmwave/m_n6/MMWAVE_M_N6_SELECTED_FLOAT_V1.keras
contract:      MMWAVE_MR60_COMPAT_INPUT_DATASET_V1
```

The binary SHA-256 was recalculated and matches the M-N6 lock. No retrain,
fine-tune, seed change, architecture change, threshold change, or runner-up
candidate was evaluated. Public `NEW_MODEL_HELDOUT_TEST` was not rerun.

Historical M-N6 heldout context only: RAPID_OR_ABNORMAL recall ≈ 0.412 on
public heldout. M-N7 cannot claim that RAPID improved or worsened on MR60.

---

## 3. Reserved recordings used

Primary evidence is exactly the M-N4 reserved set, not the M-N2/M-N3
development recordings:

| Session | Role | Source resolution |
|---|---|---|
| `LEGACY_2026-07-28_empty_v2_360s` | empty / no-person | M-N0 git blob `2d0eaf10…`; local cache `tmp/mmwave_m_n7/sources/2026-07-28_empty_v2_360s.jsonl` |
| `LEGACY_2026-07-25_occupied_d09_60s` | occupied D09 | M-N0 git blob `959817ff…`; hardware JSONL under `firmware/esp_wroom32_mr60_monitor/logs/diagnostics/` |
| `LEGACY_2026-07-25_occupied_front_d06_60s` | occupied front D06 | M-N0 git blob `eaac565d…`; same diagnostics tree |

Inventory `current_path` values under `archive/legacy_main_repo/` are not
present in this worktree. Sources were accepted only when the git blob SHA
matched the committed M-N0 inventory. No substitute session and no processed
delivery CSV was used.

Development recordings were not used for the primary pass/fail decision.

---

## 4. Canonical timing eligibility

All three reserved recordings provide `breath_phase`, `ts_monotonic_ms`, and
`phase_age_ms` on every flattened telemetry row.

```text
empty_v2_360s:              CANONICAL_TIMING_ELIGIBLE  (3599/3599 rows)
occupied_d09_60s:           CANONICAL_TIMING_ELIGIBLE  (600/600 rows)
occupied_front_d06_60s:     CANONICAL_TIMING_ELIGIBLE  (599/599 rows)
```

Production `accept_phase_events(..., production=True)` was used. There was
no fallback to “one JSON row = one new phase sample”.

---

## 5. Evaluation windows

Policy: `M_N7_EVALUATION_WINDOWING_ONLY` — 30 s non-overlapping candidate
windows anchored to each recording’s first `ts_monotonic_ms`. This does
**not** freeze a production inference stride. No stride sweep.

| Recording | Span | Candidates | Valid | Rejected |
|---|---:|---:|---:|---:|
| empty_v2_360s | 359.924 s | 11 | 11 | 0 |
| occupied_d09_60s | 59.925 s | 1 | 1 | 0 |
| occupied_front_d06_60s | 59.822 s | 1 | 1 | 0 |
| **total** | | **13** | **13** | **0** |

Each occupied file is slightly under 60 s of telemetry, so the second 30 s
candidate is not formed. That is reported rather than repaired. No window
crossed a boot boundary. No large gap was interpolated.

---

## 6. Occupied model behavior

Both occupied windows produced finite `[1,240,1]` tensors. Neither collapsed
to an all-zero tensor. Softmax rows were finite.

| Window | MAD | Predicted class | P(NORMAL) | P(RAPID) | P(APNEA) | Confidence | Entropy |
|---|---:|---|---:|---:|---:|---:|---:|
| occupied D09 0–30 s | 0.343 | APNEA | 0.034 | 0.131 | 0.835 | 0.835 | 0.532 |
| occupied front D06 0–30 s | 0.017 | APNEA | ~0 | ~0 | 1.000 | 1.000 | 0.000 |

`DEVICE_DOMAIN_MODEL_COLLAPSE = NO`.

Within-session consistency cannot be judged: each 60 s file yielded only one
valid 30 s window. Across D09 vs front/D06, both windows predicted APNEA, so
there is no catastrophic class flip from the device-condition change alone.
This remains one-person evidence and is not generalization.

Both occupied predictions being APNEA is **not** an accuracy result. There is
no independent target. It is consistent with the public model treating
lower-variance 30 s inputs as the APNEA-proxy class, and it is a limitation
of this reserved sample, not a license to retune.

---

## 7. Empty / no-person output

Empty-room canonical inputs are **ZERO** after the frozen MAD-near-zero rule
(`MAD = 0`, collapsed all-zero tensor) on all 11 valid windows.

The frozen model then emits the same high-confidence APNEA-proxy softmax on
every empty window:

```text
P(APNEA) ≈ 0.9976
P(NORMAL) ≈ 0.0011
P(RAPID_OR_ABNORMAL) ≈ 0.0014
confidence ≈ 0.9976
```

Empty was **not** treated as APNEA ground truth. The operational reading is
different: a no-person / near-zero MR60 input is currently classified as a
high-confidence respiratory-risk class.

---

## 8. Operational hazard

`NO_PERSON_INFERENCE_GATING_HAZARD = YES`.

Respiratory classification must not be interpreted as physiology when the
sensor indicates no valid person. M-N7 does not fix this by changing
weights, MAD, thresholds, or smoothing. Downstream presence/occupancy gating
belongs later; it is not M-N8 model adaptation.

---

## 9. Public → MR60 domain gap

```text
DEVICE_DOMAIN_GAP = LIMITED
```

Canonical preprocessing operates on the reserved JSONL. Occupied tensors are
valid and non-degenerate. The model returns finite three-class softmax.
That is enough to say the selected float candidate can run in this device
domain.

The gap is limited, not absent:

- one physical subject, no respiratory GT;
- only two occupied 30 s windows;
- empty-room zeros map to high-confidence APNEA-proxy;
- occupied windows also landed on APNEA-proxy without a target that could
  confirm or refute that.

`NOT_OBSERVED` would over-claim. `MATERIAL` would require a technical
incompatibility or pathological occupied collapse that was not seen.
`INCONCLUSIVE` would apply if reserved timing had failed or too few occupied
windows existed; two valid occupied tensors plus eleven empty tensors are
thin but usable for this engineering check.

---

## 10. Is M-N8 justified?

```text
M_N8_REQUIRED = NO
NEXT_RECOMMENDED_PHASE = M-N9
M-N7 gate = PASS_WITH_LIMITATIONS
```

M-N8 exists only for gap-driven adaptation. Adapting on one subject and two
occupied windows would not be a defensible response to this measurement.
The observed no-person hazard is a runtime gating issue, not a reason to
change the frozen M-N4 contract or the locked M-N6 weights.

M-N9 (INT8 / Pi preparation) is the next recommended phase. Formal
multi-subject real-device validation remains later and is not claimed here.

---

## Files

- `scripts/mmwave_m_n7_device_domain_check.py`
- `datasets/mmwave/manifests/m_n7_device_domain_result.json`
- `datasets/mmwave/manifests/m_n7_mr60_predictions.jsonl`
- `tests/test_mmwave_m_n7_device_domain.py`
