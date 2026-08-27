# SafeNest mmWave V2 — Deployable Artifact / Runtime Contract (M-PROT-2)

- Phase: **M-PROT-2**
- Date: 2026-08-27
- Base (`origin/main`): `0def5c7cb22cc6a15866ac5737fc5865bb016974`
- Branch: `research/mmwave-m-prot-2-deployable-contract`
- Previous Sol reviewed head: `ed3741776b3719f51ba6cafa908251ea2d99fabd` (`CORRECTIVE_REQUIRED`)
- Terminal verdict after corrective: **`M_PROT_2_DEPLOYABLE_CONTRACT_FROZEN`**
- Manifest: `datasets/mmwave/manifests/M_PROT_2_deployable_artifact_runtime_contract/`

This freezes a **prototype packaging/runtime contract** for M-PROT-1 nominated **B23**. It is not final model selection, not M-PV3.8 evaluation, not deployment validation, and not safety/clinical validation.

```text
PROTOTYPE_INTEGRATION_ONLY
NOT_FINAL_SELECTED_MODEL
NOT_DEPLOYMENT_VALIDATED
NOT_SAFETY_VALIDATED
NOT_CLINICAL_VALIDATION
SUBJECT_TO_REPLACEMENT
```

---

## Sol corrective closure

| Blocker | Status |
|---|---|
| Model/scaler injection integrity | **CLOSED** — injected objects are independently verified; canonical receipt fields require `identities_verified` |
| R1→R2 F3/scale→621 preprocessing | **CLOSED** — reuses `_feature_arrays` / `extract_feature_candidates`; bit-exact parity vs `_feature_matrix` for finite fixtures |
| Admissibility vs canonical preprocess | **CLOSED** — Stage 0 gate vs Stage 1 preprocess; runtime is stricter than historical training non-finite fill |
| Synthetic fixture provenance | **CLOSED** — reference fixtures emit `FIXTURE_NON_CAMPAIGN`, not `DEBUG_CAPTURE` |

## Sol Additional Corrective Closure

| Item | Status |
|---|---|
| Executable committed negative fixtures | **CLOSED** — harness resolves `base+overrides` (`M-PROT-2-FIXTURE-OVERLAY-V1`); direct `fail_*.json` execution matches named fail codes |
| Cross-runtime numerical determinism contract | **CLOSED** — reference receipt bound to Python 3.9.6 / torch 2.8.0 / numpy 1.26.4 / CPU; cross-version bit-exact `NOT_GUARANTEED`; semantic match descriptive only |
| AGENTS current-state / M-PROT-3 authorization pointer | **CLOSED** — M-PROT-1 historical; M-PROT-2 awaiting Sol exact-head review; `M-PROT-3=NOT_AUTHORIZED_PENDING_M_PROT_2_SOL_REVIEW` |

Worker evidence may record `worker_terminal_result=M_PROT_2_DEPLOYABLE_CONTRACT_FROZEN` while `sol_review_status=PENDING_REVIEW` and `m_prot_3_authorized=false`.

---

## Representation selected

```text
PRIMARY_PROTOTYPE_DEPLOYABLE_REPRESENTATION = PYTORCH_FLOAT32_STATE_DICT
SOURCE_OF_TRUTH = models/mmwave/m_pv2/family_b/candidate_seed_23.pt
SHA256 = 8f7de6f50d6ff62ff9b0ebfaed0b1fccd8d194c7e33781bc5b93366fae251a2c
```

The existing B23 checkpoint is frozen **by identity + SHA**. It is not copied under a new filename. No TFLite/INT8 conversion was introduced in this corrective.

---

## Preprocessing identity

```text
R1 CommonTraceOutput (R1-A_NATIVE_CENTERED_RELATIVE_MOTION_10HZ_V1)
        ↓
adapters.mmwave_r2_representation_features.extract_feature_candidates
        ↓
scripts.mmwave_m_pv2_candidate_training._feature_arrays
        ↓
scale[12] + quality[9]
        ↓
STAGE 0 admissibility (finite / dims / mask / availability)
        ↓
STAGE 1 TRAIN scaler once → 621-d float32
```

Finite accepted fixtures: runtime vs training `_feature_matrix` max abs difference = **0.0**.

Do not claim runtime == training end-to-end: training historically filled non-finite assembled values with zeros; Stage 0 rejects those inputs.

---

## Integrity rule

Canonical B23/scaler receipt fields are emitted only after verification.

- Injected `TraceModel` must match canonical parameter SHA `6db949c2…`
- Injected scaler must match content SHA `5a2583b5…` and frozen feature order
- Alternate or mutated objects fail closed with `identities_verified=false` and no canonical SHA on the receipt

---

## Provenance

| Scope | Use |
|---|---|
| `FIXTURE_NON_CAMPAIGN` | M-PROT-2 reference/test fixtures |
| `DEBUG_CAPTURE` | future live debug when caller provenance supports it |
| `DEVICE_DOMAIN_DEVELOPMENT` / `FINAL_GOVERNED_EVALUATION` | not M-PROT-2 caller values |

Prototype receipts always keep `PROTOTYPE_INTEGRATION_ONLY=true` and `FINAL_GOVERNED_EVALUATION=false`.

---

## Frozen I/O

| Item | Value |
|---|---|
| Window | 30 s causal, 10 Hz, 300 samples |
| Assembled input | 621 float32 |
| Scaler | TRAIN-only, apply once; refit forbidden |
| F2 model features | `NOT_REQUIRED` for B23 (scale descriptors still come from R2 F2-map names) |
| Breathing | sigmoid; PRESENT if `>= 0.5` else ABSENT |
| RR | `rr_bpm = rr_raw * 8.948729232744911 + 17.12899193548387` |
| Quality | sigmoid; `< 0.5` suppresses RR |
| Precedence | PRESENCE → QUALITY/AVAILABILITY → PHYSIOLOGY |

---

## What was not proven

- TFLite/TorchScript conversion of B23
- Raspberry Pi package install of torch
- Pi latency
- Live MR60 windowing/resampling to 10 Hz
- Device-domain or safety performance
- Bit-exact floating outputs across different torch/numpy/Python versions

Cross-runtime semantic status is descriptive only. Do not invent an absolute float tolerance as a scientific PASS criterion.

---

## Reference receipt environment

Canonical positive-path receipt is environment-bound:

```text
python 3.9.6
torch 2.8.0
numpy 1.26.4
device CPU
platform macOS arm64 (see reference_receipt_environment.json)
```

Same frozen runtime environment → deterministic result expected.
Different torch versions → bit-exact identity `NOT_GUARANTEED`.

---

## Handoff to M-PROT-3

M-PROT-3 is **not authorized** until Sol approves and merges the reviewed exact head of PR #176.

After authorization, M-PROT-3 should wire:

sensor/transport → SW-01 validated source → 30 s / 10 Hz R1 window → this R2/Stage0/Stage1/model/decode → prototype output → LIVE_DEBUG_NON_CAMPAIGN evidence → SW-03/SW-04.

Do not call `MMWaveInterpreter` or M-N9.

---

## Governance unchanged

```text
D1 PRESENT = 57
D1 ABSENT  = 0
D1 MEMBERSHIP = BLOCKED_INVALID_FINAL_MEMBERSHIP
M-PV3.8 = RESOURCE_BLOCKED_CLOSED
M-PV3.8 evaluation = NOT_EXECUTED
M-PV4 = UNAUTHORIZED
D2 = LOCKED
M_PV38_PANEL_CHANGED = false
```

```text
worker_terminal_result = M_PROT_2_DEPLOYABLE_CONTRACT_FROZEN
sol_review_status      = PENDING_REVIEW
m_prot_3_authorized    = false
SOL_REVIEW_REQUIRED    = YES
```
