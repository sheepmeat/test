# SafeNest mmWave V2 — PUBABS-A6 C1 External Stress Contract & Population Freeze

- Phase: **PUBABS-A6**
- Date: 2026-08-26
- Base SHA (post-PR #164): `e794c00cf8e13effc9ca89dbb1f6c34e5ddc397e`
- Branch: `research/mmwave-pubabs-a6-external-stress-freeze`
- Contract: **`PUBABS_C1_EXTERNAL_STRESS_V1`**
- Contract SHA-256: `d0353c9bf7837a2520364903b53075bde44cddf10b88c3fef58aa4054bbb3310`
- Frozen adapter SHA-256: `cfce866f659658e772e833f64e881549a4244b8c9daaa85423b343f34c424446`
- A6 gate: **`A6_EXTERNAL_STRESS_CONTRACT_FROZEN_WITH_LIMITATIONS`**
- Next-phase recommendation: **`RECOMMEND_EXTERNAL_STRESS_INFERENCE_DESIGN`**
- Manifest: `datasets/mmwave/manifests/PUBABS_A6_c1_external_stress_freeze/`

Membership construction for D1 / final-selection: **not** performed. Model inference: **not** executed. M-PV3.8 remains `RESOURCE_BLOCKED_CLOSED`.

---

## Objective

Freeze A5-governed external-stress identity into deterministic Layer-1 / Layer-2 populations so later Sol-gated phases cannot change eligibility without a hash change.

```text
PUBABS_C1_EXTERNAL_STRESS_V1
├── L1_AVAILABILITY_ALL77   (77)
└── L2_CONDITIONAL_VALID34  (34; CONDITIONAL_ON_ADAPTER_VALID)
```

---

## Layer 1 freeze

| Field | Value |
|---|---|
| Identity | `PUBABS_C1_EXTERNAL_STRESS_V1__L1_AVAILABILITY_ALL77` |
| TOTAL | 77 |
| ABSENT / PRESENT | 11 / 66 |
| VALID / FAIL_CLOSED | 34 / 43 |
| Manifest SHA-256 | `cefc7a3820ebb644a9553b3eaad9f4ec600ea555bc25ed891f236cc50c6632f5` |

Fail-closed codes retained: gap=42, too-short=1. Silent drop forbidden.

---

## Layer 2 freeze

| Field | Value |
|---|---|
| Identity | `PUBABS_C1_EXTERNAL_STRESS_V1__L2_CONDITIONAL_VALID34` |
| TOTAL | 34 |
| ABSENT / PRESENT | 9 / 25 |
| Semantics | `CONDITIONAL_ON_ADAPTER_VALID` |
| Manifest SHA-256 | `01a1db3ef56e1071896f054a5baad397035ca6d989f42f2d1129d250b6867c7c` |

PRESENT VALID subjects: N1=1, N2=1, N3=9, N4=8, N5=6, **N6=0** (exact A3R/A4/A5 evidence).

Eligibility rule: **only** `canonical A3R adapter_status == VALID`. No class/subject/position quality filters. No later-window rescue.

---

## Position composition (disclosure)

Layer-1 positions (−5…+5): `{'-5': 7, '-4': 7, '-3': 7, '-2': 7, '-1': 7, '0': 7, '1': 7, '2': 7, '3': 7, '4': 7, '5': 7}`  
Layer-2 positions (−5…+5): `{'-5': 3, '-4': 3, '-3': 4, '-2': 3, '-1': 4, '0': 1, '1': 3, '2': 2, '3': 3, '4': 3, '5': 5}`

No artificial balancing.

---

## Tensor / trace identity freeze (Layer 2)

Each VALID session freezes A3R receipts: `selected_bin`, `r1t_10hz_sha256`, `r1_centered_sha256`, `train_zscore_trace_sha256`. Future inference must consume these identities.

---

## Upstream reconciliation

```text
A3R TOTAL 77 = A6 Layer1 77
A3R VALID 34 = A6 Layer2 34
A3R FAIL_CLOSED 43 = A6 Layer1-only 43
ABSENT L2 9 / PRESENT L2 25
subject VALID counts match expected
```

Status: **EXACT**

---

## Determinism

Two rebuilds of Layer-1/Layer-2 manifests: identical ordering (`external_stress_session_id`), flags, fail codes, tensor hashes, and SHA-256.

---

## Terminal guards / future authority

Guards include `UNAVAILABLE_NEVER_CLASS_LABEL`, `NO_D1_SUBSTITUTION`, `NO_M_PV38_FINAL_SELECTION_USE`, `NO_LATER_WINDOW_RESCUE`, `FUTURE_MODEL_INFERENCE_REQUIRES_SOL`, etc.

```text
future_external_model_inference = REQUIRES_SEPARATE_SOL_AUTHORIZATION
eligible_for_D1 / M-PV3.8 final selection / model selection = false
domain_role = EXTERNAL_SAFETY_DOMAIN_STRESS_ONLY
scale_risk = HIGH
```

---

## A6 gate

```text
A6_EXTERNAL_STRESS_CONTRACT_FROZEN_WITH_LIMITATIONS
```

Limitations retained from A4/A5: availability class skew, VALID non-representativeness, HIGH scale/domain risk. Implementation itself is exact.

Next-phase recommendation:

```text
RECOMMEND_EXTERNAL_STRESS_INFERENCE_DESIGN
```

Does **not** authorize inference.

---

## Explicit non-actions

- MODEL_INFERENCE = NOT_EXECUTED
- D1 = UNCHANGED
- FINAL_MEMBERSHIP = NOT_CREATED
- M-PV3.8 = RESOURCE_BLOCKED_CLOSED
- M-PV4 = UNAUTHORIZED
- D2 = LOCKED
- ADAPTER_RULES = UNCHANGED
- HISTORICAL_R1 = UNCHANGED
- NEXT_PHASE = NOT_EXECUTED
