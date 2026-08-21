# SafeNest D0 — V2 subject split and label eligibility audit

- Date: 2026-08-22
- Phase: **D0 only**. No training, R1 representation, D1/D2/D3, TFLite, INT8, or M-PV1.
- Manifest: `datasets/mmwave/manifests/M-PV0_D0_v2_split_label_audit/`
- Split identity: `MMWAVE_V2_D0_SUBJECT_SPLIT_V1`
- Parent freeze: M-PV0 commit `18e4a4e86d6bf95795d6749a91ce303ad3f1c417`
- Gate: **`PASS_WITH_LIMITATIONS`**

This audit answers whether the remaining eligible D0 subjects can be frozen into a deterministic, subject-disjoint V2 development split with trustworthy source-label provenance. SafeNest `APNEA` remains a voluntary breath-hold proxy, not a clinical diagnosis.

---

## 1. Why only 94 subjects are eligible

Canonical D0 is the Zenodo **v1.1** dataset `10.5281/zenodo.18599983` (110 subjects / 440 recordings). M-PV0 already forbade reusing the 16 subjects consumed as `NEW_MODEL_HELDOUT_TEST` in M-N6.

Independent A0 accounting:

```text
110 A0 subjects
− 16 M-N6 NEW_MODEL_HELDOUT_TEST
= 94 V2 eligible subjects / 376 recordings
```

The 16 were not reconstructed by hand. They are the canonical IDs in `datasets/mmwave/splits/mmwave_mr60_compat_subject_split_v1.json` and `datasets/mmwave/manifests/m_n6_heldout_result.json`, copied forward by M-PV0.

Historical Phase-B `LOCKED_TEST` remains visible in recording provenance. It is a different lineage and is **not** an extra V2 exclusion set.

---

## 2. Excluded M-N6 heldout subjects

These 16 IDs appear in **zero** V2 TRAIN / VAL / `D0_SUBJECT_HELDOUT` assignments:

```text
dataset-10_5281_zenodo_18599983-p002
dataset-10_5281_zenodo_18599983-p010
dataset-10_5281_zenodo_18599983-p012
dataset-10_5281_zenodo_18599983-p017
dataset-10_5281_zenodo_18599983-p018
dataset-10_5281_zenodo_18599983-p022
dataset-10_5281_zenodo_18599983-p024
dataset-10_5281_zenodo_18599983-p033
dataset-10_5281_zenodo_18599983-p045
dataset-10_5281_zenodo_18599983-p053
dataset-10_5281_zenodo_18599983-p058
dataset-10_5281_zenodo_18599983-p063
dataset-10_5281_zenodo_18599983-p072
dataset-10_5281_zenodo_18599983-p095
dataset-10_5281_zenodo_18599983-p096
dataset-10_5281_zenodo_18599983-p107
```

M-N6 TRAIN/VAL membership was **not** copied. Incidental overlap with the new hash assignment is recorded, not treated as inheritance.

---

## 3. New V2 D0 split

| Field | Value |
|---|---|
| Identity | `MMWAVE_V2_D0_SUBJECT_SPLIT_V1` |
| Algorithm | `SHA256(namespace:seed:subject_id)` then largest-remainder counts |
| Namespace | `MMWAVE_V2_D0_DEVELOPMENT_SPLIT_V1` |
| Seed | `20260822` |
| TRAIN | 66 subjects |
| VAL | 14 subjects |
| D0_SUBJECT_HELDOUT | 14 subjects |

`D0_SUBJECT_HELDOUT` is internal D0 subject-heldout evidence for later candidate comparison **before D2**. It is not `FINAL_TEST` and not `LOCKED_PUBLIC_CROSS_DEVICE_TEST`. D2 still owns the locked public cross-device test.

One subject maps to exactly one split. Leakage checks:

```text
TRAIN ∩ VAL = ∅
TRAIN ∩ D0_SUBJECT_HELDOUT = ∅
VAL ∩ D0_SUBJECT_HELDOUT = ∅
ALL_V2_D0 ∩ M_N6_HELDOUT = ∅
duplicate recording IDs across V2 splits = 0
```

---

## 4. Why 70/15/15

This ratio was not chosen as a fashionable default before looking at the source.

Inventory of the 94 eligible subjects showed a uniform 4-recording design: Lying/Sitting × Rest/Post-exercise. Every eligible rest recording has `non_breathing_ts.csv`. Both 60 GHz radar families are therefore present in every subject. A subject-level split cannot accidentally drop a posture, rest/post-exercise cell, or radar family from VAL or heldout.

Given that structure:

- 70/15/15 reuses the established SafeNest development remainder convention without copying M-N6 IDs.
- 14 VAL and 14 heldout subjects keep independent D0 evidence for later comparison. A 10% heldout (9 subjects) would be thinner than needed for that internal role.
- Seed `20260822` was then generated once and inspected. VAL and heldout both have assigned APNEA-proxy windows, RR-mapped windows, Rest, Post-exercise, Lying, and Sitting. Subjects were **not** moved after that assignment.

Exact multi-factor demographic stratification was not possible: `ParticipantsInfo.xlsx` is listed on Zenodo v1.1 but is not in the local A0 recording inventory.

---

## 5. Condition and label coverage

Eligible-pool A6 windows (446):

| Label / mapping | Count |
|---|---|
| APNEA-proxy (`A4_RULE_APNEA_VOLUNTARY_PROXY`) | 181 |
| NORMAL (Movesense chest ACC RR) | 124 |
| RAPID_OR_ABNORMAL (ACC RR ≥ 25 or bradypnea) | 102 |
| AMBIGUOUS / transition (`A4_RULE_TRANSITION_WINDOW`) | 39 |

Frozen split window coverage:

| Split | Windows | APNEA-proxy | Rest / Post-exercise | Lying / Sitting |
|---|---|---|---|---|
| TRAIN | 318 | 126 | 159 / 159 | 160 / 158 |
| VAL | 60 | 27 | 30 / 30 | 30 / 30 |
| D0_SUBJECT_HELDOUT | 68 | 28 | 34 / 34 | 34 / 34 |

Three eligible subjects (`p026`, `p034`, `p040`) have source voluntary non-breathing timestamps but no assigned APNEA-proxy 30 s window (overlap below 6 s, or hold outside the canonical window). The hash placed all three in TRAIN. VAL and heldout still have assigned APNEA-proxy coverage.

---

## 6. What D0 can supervise later

From **source evidence**, not model predictions:

- Breathing-evidence windows: all processed A6 windows in the 94-subject pool (finite radar, valid 10 Hz timeline).
- RR supervision: Movesense chest-ACC RR is present on every A6 window. Post-exercise and non-overlapping rest windows can supervise RR without being APNEA-proxy labels.
- Voluntary breath-hold APNEA-proxy: rest recordings with `non_breathing_ts.csv` and window overlap ≥ 6 s under `MMWAVE_LABEL_MAPPING_PROFILE_001`.
- Internal D0 subject-heldout evaluation of later candidates, without touching D2 or the 16 consumed M-N6 subjects.

A window may be RR-eligible and not APNEA-proxy-eligible. Transition windows may retain provenance without entering pure-class hold supervision.

---

## 7. What D0 cannot supervise

- Clinical apnea.
- Unlabeled quiet regions or low radar amplitude as APNEA.
- The 16 M-N6 heldout subjects, for TRAIN, VAL, heldout selection, representation, family, seed, threshold, calibration, or augmentation.
- Team MR60 recordings as supervised labels.
- D2 as development or selection data.
- Final V2 feature contract: R1 representation, MAD alternatives, RR model structure, temporal-hold implementation, abstention thresholds, or architecture. Those belong to later R / M-PV stages.
- ECG-derived RR: ECG files exist on all 440 recordings but A4 labels use chest ACC.

---

## 8. Unresolved annotation / reference issues

Non-blocking, typed in `exception_registry.json`:

- Local `db_records.zip` is absent in this worktree. Lineage is A0 + A6 derived manifests, which is sufficient for this phase.
- A0 local archive remains `LIKELY_REPACKAGED_NOT_FULLY_VERIFIED`. Canonical identity is still v1.1.
- 350 recordings dropped incomplete tails after full 30 s windows; some annotated hold seconds can fall outside canonical windows.
- Three eligible subjects are transition-only for hold supervision.
- Demographic strata were not applied.
- ECG is unused for A4 RR.

No annotation parse failures. No invalid source recordings in A6 (`SUCCESS` or `SUCCESS_WITH_WARNINGS` only).

---

## 9. Ready for M-PV1 input?

**YES**, as split/label governance input. M-PV1 may inherit `MMWAVE_V2_D0_SUBJECT_SPLIT_V1` and the eligibility taxonomy. M-PV1 must not treat this freeze as an R1 feature contract or as permission to train.

D0 does not claim model performance. No model exists in this phase.
