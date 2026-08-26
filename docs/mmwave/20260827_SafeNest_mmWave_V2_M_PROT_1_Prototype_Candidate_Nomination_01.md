# SafeNest mmWave V2 — Prototype Candidate Nomination (M-PROT-1)

- Phase: **M-PROT-1**
- Date: 2026-08-27
- Post-#172 `origin/main`: `7659a988fad7ab92f6a2a09f42da74544cbe0f52`
- Branch: `research/mmwave-m-prot-1-prototype-nomination`
- Role: **provisional engineering baseline nomination only** — no training, no fine-tune, no threshold retune, no TFLite conversion, no runtime wiring
- Terminal verdict: **`M_PROT_1_PROTOTYPE_NOMINATED`**
- Nominated identity: **B23** / `family_b` / seed `23` / `PROTOTYPE_NOMINATED` / `INTEGRATION_BASELINE` / `PROVISIONAL`
- Manifest: `datasets/mmwave/manifests/M_PROT_1_prototype_candidate_nomination/`

Mandatory semantics:

```text
PROTOTYPE_INTEGRATION_ONLY
NOT_FINAL_SELECTED_MODEL
NOT_DEPLOYMENT_VALIDATED
NOT_SAFETY_VALIDATED
NOT_CLINICAL_VALIDATION
SUBJECT_TO_REPLACEMENT
```

Forbidden labels **not** applied: `WINNER`, `BEST_MODEL`, `FINAL_SELECTED`, `M-PV3.8_SELECTED`, `DEPLOYMENT_READY`.

---

## 1. Why one candidate was nominated

The question was: which **existing** ROLE_L artifact is the most technically coherent first wire-in for the integrated runtime?

All six frozen ROLE_L members were inspected in panel order `B11 → B23 → B47 → C11 → C23 → C47`. No member was skipped.

Decision hierarchy from M-PROT-0 `nomination_rules.json` and the execution prompt:

1. ROLE / semantic compatibility
2. Complete artifact + reproducible lineage
3. Clear preprocessing / input / output contracts
4. Practical runtime integration feasibility
5. Existing non-final offline behavior / stability
6. Cross-seed architecture stability
7. Resource footprint / implementation simplicity

Steps 1–2 do not separate Family B from Family C. Both implement breathing / RR / quality, and all six checkpoints match registry SHA256, load strictly into `TraceModel`, and match canonical parameter hashes.

Steps 3–4 do separate the families. Family B consumes a 621-d vector `concat(trace[300], trace_mask[300], scale[12], quality[9])`. Family C adds frozen R2 F2 (25 features + 25-d mask) for 671-d input. The first integrated prototype therefore has a smaller, still ROLE-complete wiring surface if it starts on Family B: no live spectral/autocorr reconstruction is required.

Inside Family B, the seeds are not equivalent:

- **B11** is the Family B high-loss seed (best validation loss 0.470 vs 0.163 / 0.247) and has the highest D1_DEV_VAL Brier (0.099). That is treated as an obviously fragile provisional choice, not as C1 ranking and not as a scientific elimination from the M-PV3.8 panel.
- **B47** has one PRESENT false-negative on D1_DEV_VAL and a large negative RR minimum (−11.5 bpm).
- **B23** has no D1_DEV_VAL false-negative, the lower Family B Brier / RR MAE on the same non-final card, and a complete loadable artifact.

B23 is therefore the **provisional integration baseline**. This is an engineering-first-wire decision. It is not a claim that B23 is scientifically best, that Family C is worse, or that the other five are removed.

Panel-order tie-break (`B11` first) was **not** used. The Family B seeds were not genuinely equivalent after steps 5–6.

---

## 2. Why this is not a winner

M-PV3 already recorded `NO_SELECTION_READY`. M-PV3.6 populated ROLE_L cards with `selection_use=false` and produced no combined score. Governed eligible ABSENT remains 0. M-PV3.8 remains `RESOURCE_BLOCKED_CLOSED` with evaluation `NOT_EXECUTED`. M-PV4 remains `UNAUTHORIZED`. D2 remains `LOCKED`.

D1_DEV_VAL numbers used below are **VALIDATION** class development evidence (57 PRESENT / 0 eligible ABSENT). Unavailable ABSENT metrics are `NOT_APPLICABLE`, not zero. Frozen M-PV3 utility guards are historical context only; B23 failing `within_6` (0.702 vs 0.75) does not block prototype wiring and is not re-interpreted as a new selection gate.

C47’s lower D1_DEV_VAL Brier is acknowledged descriptively. Hierarchy steps 3–4 still prefer Family B’s smaller live feature surface. That comparison is **not** a winner table.

The other five remain valid frozen M-PV3.8 candidates:

```text
M_PV38_PANEL_CHANGED = false
FINAL_MODEL_SELECTED = false
```

---

## 3. Evidence used

| Source | Class | Use |
|---|---|---|
| `M-PV2_candidate_training/candidate_registry.json` | TRAIN | identity, SHA, parameter count, limitations |
| `M-PV2_candidate_training/contract_snapshot.json` | historical evaluation | heads, threshold 0.5, forbidden TFLite/calibration |
| `M-PV2_candidate_training/scaler_statistics.json` | TRAIN | TRAIN-only z-score + RR decode |
| `M-PV2_candidate_training/seed_sensitivity.json` | TRAIN | Family B vs C validation-loss spread |
| `M-PV1_public_multidomain_contract/model_input_contract.json` | historical evaluation | PROFILE_B / PROFILE_C tensors |
| `M-PV1 temporal_context_contract.json` | historical evaluation | 30 s / 10 Hz / last-5 s breathing anchor |
| `M-PV3_6_role_L_full_task_evaluation/` cards | VALIDATION | non-final D1_DEV_VAL / Q2 synthetic diagnostic |
| `M-PV3_candidate_selection/` | historical evaluation | `NO_SELECTION_READY`; B11 determinism replay |
| `PUBABS_A7` contracts | historical evaluation | runtime format, decode, frozen thresholds |
| Read-only `torch.load` of the six `.pt` files | structure only | SHA, strict load, parameter count; **no eval tensors** |

C1 A8 may be mentioned only as out-of-domain risk context. It was **not** used to rank or drop anyone.

---

## 4. Evidence forbidden and unused

- C1 A8 external-stress ranking / recall / “balanced on C1”
- D1 final-selection membership or scores (`D1_USED: NO`)
- D2 semantic access (`D2_ACCESSED: NO`)
- M-PV3.8 evaluation outputs (none exist)
- New training, fine-tune, architecture change, threshold retune, calibration fit
- A new benchmark run whose purpose was to obtain a preferred answer
- Treating missing ABSENT results as zero

Final-lane confirmation at completion (unchanged; M-PROT has zero authority here):

```text
D1 PRESENT = 57
D1 ABSENT  = 0
D1 MEMBERSHIP = BLOCKED_INVALID_FINAL_MEMBERSHIP
M-PV3.8 = RESOURCE_BLOCKED_CLOSED
M-PV3.8 evaluation = NOT_EXECUTED
M-PV4 = UNAUTHORIZED
D2 = LOCKED
```

---

## 5. Other existing mmWave artifacts

Reviewed and classified; none replaced ROLE_L:

| Artifact | Class | Why not nominated |
|---|---|---|
| Family A F2 MLP (3 seeds) | `ROLE_INCOMPATIBLE` | no breathing head |
| M-PV2 15 s short-context CNN | `ROLE_PARTIALLY_COMPATIBLE` | breathing only; 15 s; no RR/quality |
| M-PV3.5 isolation CNN | `ROLE_INCOMPATIBLE` | breathing-only isolation role |
| `MMWAVE_M_N9_FULL_INT8_V1.tflite` | `ROLE_INCOMPATIBLE` | V1 3-class NORMAL/RAPID/APNEA; I1 forbids this identity |
| M-B3/B5/B6/B11 TFLite family | `ROLE_INCOMPATIBLE` | same 3-class contract |
| `mmwave_resp_int8` v0.1.0 / v0.2.0 | `ROLE_INCOMPATIBLE` | same 3-class contract; collapse / synthetic smoke |

An existing TFLite file was not treated as a nomination advantage.

---

## 6. Nominated contract snapshot (handoff to M-PROT-2)

| Field | Value |
|---|---|
| panel_id | B23 |
| candidate_id | `M-PV2_FAMILY_B_TRACE_TCN_BREATHING_RR_QUALITY` |
| family / seed | `family_b` / 23 |
| artifact | `models/mmwave/m_pv2/family_b/candidate_seed_23.pt` |
| SHA256 | `8f7de6f50d6ff62ff9b0ebfaed0b1fccd8d194c7e33781bc5b93366fae251a2c` |
| construction | `TraceModel` in `scripts/mmwave_m_pv2_candidate_training.py` |
| current format | `PYTORCH_FLOAT32_STATE_DICT` |
| parameters | 17915 (float32 ≈ 71.7 KiB weights; checkpoint 76473 bytes) |
| window / rate | 30 s / 10 Hz / 300 samples |
| assembled input | 621 float32 |
| preprocessing | TRAIN scaler content SHA `5a2583b5…`; apply once |
| outputs | breathing sigmoid, RR inverse z-score, quality sigmoid |
| thresholds | breathing 0.5, quality 0.5 (already frozen; not retuned) |
| TFLite | `NOT_YET_PROVEN` |

PyTorch-first is the **current artifact format**, not a mandate that Raspberry Pi integration must stay on PyTorch. M-PROT-2 freezes the deployable representation.

---

## 7. Runtime work that remains

M-PROT-1 does not wire the model. Known gaps (see `integration_gap_registry.json`):

- Live 30 s / 10 Hz window from MR60
- 621-d feature assembly with frozen TRAIN scaler and no double z-score
- Torch-vs-converted runtime choice; Pi torch/operator/latency unmeasured
- I1 fail-closed wrapper (presence → quality → physiology)
- RR slightly-negative decode policy (D1_DEV_VAL min −0.34 bpm)
- Application temporal composer
- Packaging / TFLite if chosen later
- Live debug capture (M-PROT-5), which must not silently become final-test evidence

Next phase, not executed here:

```text
M-PROT-2  Deployable Artifact / Runtime Contract Freeze
```

---

## 8. Limitations that remain

- No both-class ABSENT evidence
- No Pi measurement, no live MR60 prototype evidence
- Quality head is Q2 synthetic diagnostic only
- Family C remains a valid later replacement if F2 reconstruction is worth the wiring cost
- Prototype is `SUBJECT_TO_REPLACEMENT`

SW-01..04 branches were not modified and were not required.

---

## 9. Verdict

```text
TERMINAL_VERDICT = M_PROT_1_PROTOTYPE_NOMINATED
NEXT_PHASE       = M-PROT-2
```
