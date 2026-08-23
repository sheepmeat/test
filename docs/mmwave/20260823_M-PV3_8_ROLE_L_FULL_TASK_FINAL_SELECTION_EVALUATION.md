# SafeNest mmWave V2 — M-PV3.8 `ROLE_L_FULL_TASK` Final Selection Evaluation

## Decision

**`BLOCKED_INVALID_FINAL_MEMBERSHIP`**

The M-PV3.8 contract requires the one-time locked membership
`D1_FINAL_SELECTION_BOTH_CLASS_V1` before any of the six candidate outputs can
be opened. That lock is not present in the repository, and the governed source
membership does not contain the required 57 eligible `ABSENT` contexts. The
evaluation therefore stopped before checkpoint access. This is a membership
gate result, not `NO_SELECTION_READY` based on model metrics.

**Selected candidate: none.**

M-PV4 remains unauthorized.

## Scope and frozen roster

- Role: `ROLE_L_FULL_TASK`, 30-second input `[B,300,1]`
- Candidates: Family B/C × seeds 11, 23, 47 (exactly 6)
- Excluded: Family A, `ROLE_S_SHORT_CONTEXT` 15s, M-PV3.5 isolation CNN
- Contract: `MMWAVE_V2_M_PV38_MINIMAL_SELECTION_READINESS_GATE_V1`, schema `M-PV3.8.1`
- Candidate checkpoint outputs opened: **no**
- Candidate evaluation performed: **no**

The roster was checked against the existing candidate registry without opening
checkpoint files. No retraining, preprocessing change, threshold tuning,
ranking, combined score, post-hoc seed choice, D2 access, or MR60 supervised
physiology was performed.

## Membership audit

Required final lock:

- 57 eligible `PRESENT` contexts
- 57 eligible `ABSENT` contexts
- 19 eligible `ABSENT` contexts from each of `D1_PERSON_03`, `D1_PERSON_09`, and `D1_PERSON_11`
- subject-disjoint from candidate training
- ambiguous rows retained with provenance and excluded from pure-class metrics
- membership manifest, checksums, and ambiguous exception registry frozen before candidate output access

Observed governed source rows in the existing M-PV1 materialization:

| Subject | eligible PRESENT | eligible ABSENT | AMBIGUOUS | required ABSENT | deficit |
|---|---:|---:|---:|---:|---:|
| `D1_PERSON_03` | 19 | 0 | 1 | 19 | 19 |
| `D1_PERSON_09` | 24 | 0 | 1 | 19 | 19 |
| `D1_PERSON_11` | 14 | 0 | 0 | 19 | 19 |
| **Total** | **57** | **0** | **2** | **57** | **57** |

The existing 57 `PRESENT` contexts are available, but no governed eligible
`ABSENT` context is available in this final split. The two ambiguous contexts
were retained in the audit and were not relabeled. Candidate-training subject
disjointness itself is observed (`TRAIN` + `D1_DEV_TRAIN` has no overlap with
the three held-out subjects), but that does not repair the missing final lock.

No expected membership manifest was found at the governed candidate paths,
including:

- `datasets/mmwave/manifests/D1_FINAL_SELECTION_BOTH_CLASS_V1/membership_manifest.json`
- `datasets/mmwave/manifests/D1_FINAL_SELECTION_BOTH_CLASS_V1/manifest.json`
- `datasets/mmwave/manifests/M-PV3_8_minimal_selection_readiness_gate/D1_FINAL_SELECTION_BOTH_CLASS_V1_membership_manifest.json`
- `datasets/mmwave/manifests/M-PV3_8_minimal_selection_readiness_gate/d1_final_selection_membership_manifest.json`

The available source rows also do not expose `label_mapping` and
`quality_provenance` as explicit final-lock fields. No top-up, replacement,
resampling, relabeling, or second membership was created.

## Candidate decision table

| Candidate | Safety | Breathing | RR | Stability | Decision |
|---|---|---|---|---|---|
| Family B / seed 11 | Not evaluated | Not evaluated | Not evaluated | Not evaluated | `BLOCKED_INVALID_FINAL_MEMBERSHIP` |
| Family B / seed 23 | Not evaluated | Not evaluated | Not evaluated | Not evaluated | `BLOCKED_INVALID_FINAL_MEMBERSHIP` |
| Family B / seed 47 | Not evaluated | Not evaluated | Not evaluated | Not evaluated | `BLOCKED_INVALID_FINAL_MEMBERSHIP` |
| Family C / seed 11 | Not evaluated | Not evaluated | Not evaluated | Not evaluated | `BLOCKED_INVALID_FINAL_MEMBERSHIP` |
| Family C / seed 23 | Not evaluated | Not evaluated | Not evaluated | Not evaluated | `BLOCKED_INVALID_FINAL_MEMBERSHIP` |
| Family C / seed 47 | Not evaluated | Not evaluated | Not evaluated | Not evaluated | `BLOCKED_INVALID_FINAL_MEMBERSHIP` |

## Required cards

Cards A–D are present as explicit `NOT_EVALUATED` cards. They contain no
fabricated candidate metrics:

- **Card A — Safety:** Class A precedence and forbidden `INPUT_UNAVAILABLE`
  emissions are recorded as requirements; Q2 results are not run because the
  membership lock failed.
- **Card B — Breathing:** the frozen PRESENT/Brier guards and both-class count
  requirements are recorded; recall, precision, F1, Brier, and ABSENT recall
  remain unavailable.
- **Card C — RR:** the frozen MAE and ±2/±4/±6 guards are recorded; no RR
  metric is computed.
- **Card D — Stability:** all six seeds and all three held-out subjects are
  listed as required; no mean, population standard deviation, extrema, or
  subject metric is computed.

The contract requires `BLOCKED_INVALID_FINAL_MEMBERSHIP` rather than evaluating
with an incomplete class membership. Consequently, no candidate can satisfy
the selection logic and no ranking or winner determination is allowed.

## Evidence files

- Evidence manifest: `datasets/mmwave/manifests/M-PV3_8_role_L_full_task_final_selection_evaluation/evaluation_manifest.json`
- Membership audit: `datasets/mmwave/manifests/M-PV3_8_role_L_full_task_final_selection_evaluation/membership_audit.json`
- Candidate decision table: `datasets/mmwave/manifests/M-PV3_8_role_L_full_task_final_selection_evaluation/candidate_decision_table.json`
- Cards A–D: same directory, `card_a_safety.json`, `card_b_breathing.json`, `card_c_rr.json`, `card_d_stability.json`
- Validation result: same directory, `validation_result.json`
- Checksums: same directory, `checksums.json` and `checksums.sha256`
- Runner: `scripts/mmwave_m_pv38_role_l_full_task_final_selection_evaluation.py`
- Validator: `scripts/validate_mmwave_m_pv38_role_l_full_task_final_selection_evaluation.py`
