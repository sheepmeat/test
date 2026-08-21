# SafeNest M-PV0 — Public multidomain V2 scope, baseline, and source-role freeze

- Date: 2026-08-22
- Phase: **M-PV0 only**. No V2 training, adapter, D0 split, D2 payload inspection, or INT8 work.
- Registry: `datasets/mmwave/manifests/M-PV0_public_multidomain_registry/`
- Parent roadmap: `docs/20260822_SafeNest_mmWave_Public_Multidomain_V2_Development_Roadmap_01.md`
- Gate: **`PASS_WITH_LIMITATIONS`**

This freeze keeps M-N9 V1 as a read-only `OBSERVE_ONLY` baseline and assigns each public radar source a role before any V2 developer can use it. SafeNest `APNEA` remains a voluntary breath-hold proxy, not a clinical diagnosis.

---

## 1. What V1 is, and why V2 must be a new identity

The preserved baseline is the locked M-N9 FULL_INT8 artifact, not the historical `mmwave_resp_int8` entries in `models/model_manifest.json`.

| Field | Value | Evidence |
|---|---|---|
| Identity | `MMWAVE_M_N9_FULL_INT8_V1` | `config/mmwave/m_n9_full_int8_artifact_lock.json` |
| Artifact | `models/mmwave/m_n9/MMWAVE_M_N9_FULL_INT8_V1.tflite` | same lock + file SHA |
| SHA-256 | `3b008af4be0facc4037c2afd3fe39292fb794208eb4370dbe6916b2d15aa38a4` | recalculated; matches lock/result |
| Float parent | `MMWAVE_M_N6_SELECTED_FLOAT_V1` / `M-N5_DILATED_CONV1D_GAP_TINY` seed 2026 | M-N6 lock |
| Float SHA-256 | `9de3818c0f4854f8512c9d390d290938b6e562d590e0775cb1dab885cc72e2ab` | recalculated |
| Contract | `MMWAVE_MR60_COMPAT_INPUT_DATASET_V1` | M-N4 freeze |
| Input | `[1, 240, 1]` INT8; 30 s at 8 Hz | M-N4 + M-N9 |
| Preprocessing | time-aware R2 derivative, then window-local MAD divide-only | M-N4 |
| Outputs | `NORMAL` / `RAPID_OR_ABNORMAL` / `APNEA` proxy softmax | M-N4 / M-N9 |
| Presence gate | required on `human_detected_raw`; not a fourth neural class | M-N9, inherited from M-N7 |
| Abstention class | absent in V1 (`INPUT_UNAVAILABLE` is a V2 policy requirement) | M-N4/M-N9 |

V2 cannot reuse this artifact ID, overwrite the binary, or patch V1 preprocessing to look MR60-compatible. The MAD divide-only contract is why quiet occupied MR60 windows and empty-room zeros both collapse toward high-confidence APNEA-proxy. That failure is the comparison baseline, not a license to retune V1.

Public held-out result (M-N6, 16 subjects / 74 supervised windows): accuracy 0.756757, Macro F1 0.70838, RAPID recall 0.411765. M-N9 did not rerun that held-out set (`NEW_MODEL_HELDOUT_TEST_INFERENCE_M_N9 = 0`).

---

## 2. Public source roles

| Source | Role | Lock |
|---|---|---|
| **D0** 110-subject 60 GHz Zenodo | `REQUIRED_PRIMARY_DEVELOPMENT_DOMAIN` | unlocked development; M-N6 heldout excluded |
| **D1** 24.17 GHz Six-Port (11 subjects) | `REQUIRED_AUXILIARY_DEVELOPMENT_DOMAIN` | metadata freeze only; no I/Q adapter yet |
| **D2** 120 GHz 24-subject VitalSense | `LOCKED_PUBLIC_CROSS_DEVICE_TEST` | locked before semantic use |
| **D3** BreathSense 77 GHz | `OPTIONAL_NON_BLOCKING_QUALITY_RR_DEVELOPMENT_DOMAIN` | may lag; must not block D0+D1 |

D0 canonical identity in this repository is **Zenodo v1.1** `10.5281/zenodo.18599983` (A0 / `datasets/MANIFEST.json` / M-N4). The V2 roadmap cites record `16760684` (v1.0). Both belong to concept `16760683` and publish the same official `db_records.zip` MD5. M-PV0 does not silently pick one: v1.1 remains the SafeNest D0 identity, and the roadmap pointer is recorded as a non-blocking discrepancy.

D2 is not a fourth training domain. If it entered representation, family, threshold, or candidate selection, there would be no unseen public radar left for a cross-device test.

---

## 3. Prior public subjects that cannot re-enter V2 selection

Authoritative held-out set: `datasets/mmwave/splits/mmwave_mr60_compat_subject_split_v1.json` field `NEW_MODEL_HELDOUT_TEST`, consumed once in `datasets/mmwave/manifests/m_n6_heldout_result.json`.

```text
V2_SELECTION_REUSE = FORBIDDEN
V2 TRAIN/VAL reuse of these 16 subjects = FORBIDDEN
```

Subjects:

`p002, p010, p012, p017, p018, p022, p024, p033, p045, p053, p058, p063, p072, p095, p096, p107`
(full IDs: `dataset-10_5281_zenodo_18599983-p…`)

M-N9 added no extra public test subjects. The remaining 94 D0 subjects (V1 TRAIN+VAL) may be re-split under a **new V2 split identity** in the D0 lane. M-PV0 does not create that split.

Historical B `LOCKED_TEST` is a different lineage. It is recorded, not reopened, and is not used as V2 scores. Overlap with the M-N6 heldout set is already covered by the exclusion above.

---

## 4. D2 lock

M-PV0 accessed publication and landing-page metadata only. No zip, no `.mat`, no arrays, no plots, no features, no inference.

| Access | State |
|---|---|
| `PUBLIC_METADATA_ACCESS` | YES |
| `PAYLOAD_ACQUISITION` | NO |
| `PAYLOAD_SEMANTIC_INSPECTION` | NO |
| `FEATURE_EXTRACTION` | NO |
| `MODEL_INFERENCE` | NO |
| `MODEL_INFERENCE_COUNT` | 0 |

Until the roadmap authorizes the one final D2 evaluation after M-PV3:

```text
representation_selection = FORBIDDEN
feature_selection = FORBIDDEN
model_family_selection = FORBIDDEN
seed_selection = FORBIDDEN
threshold_selection = FORBIDDEN
calibration_selection = FORBIDDEN
augmentation_selection = FORBIDDEN
candidate_inference = FORBIDDEN
candidate_inference_count = 0
```

Pre-lock repo scan found D2 identifiers only in the V2 roadmap. No payload contamination.

A later D2 **acquisition/checksum** lane may download and hash the zip under this lock. That lane still must not inspect signals or run models.

---

## 5. Why MR60 logs are runtime references, not supervised ML data

M-N7 already showed the operational failure on reserved Team MR60 JSONL without treating those sessions as labels:

- occupied D09 MAD 0.343 → APNEA-proxy, confidence 0.835
- occupied front D06 MAD 0.017 → APNEA-proxy, confidence 0.999976
- empty-room zeros → APNEA-proxy, confidence ≈ 0.9976 (`NO_PERSON_INFERENCE_GATING_HAZARD`)

There is one physical subject and no independent respiratory ground truth. Current and historical SafeNest MR60 logs are therefore forbidden for V2 supervised TRAIN/VAL/TEST, representation or family selection, threshold/calibration/augmentation tuning, and label construction. They may later supply cadence/gap/freeze corruption profiles and application smoke only.

---

## 6. Unresolved source / license / count issues

These do **not** blur D0/D1/D2 roles or the D2 lock. They are why the gate is `PASS_WITH_LIMITATIONS` rather than `PASS`.

1. D0 Zenodo v1.0 vs v1.1 record pointer (same concept; repo stays on v1.1).
2. D0 local zip absent in this worktree; A0 still records a likely-repackaged local archive.
3. D2 IEEE DataPort login required; no published payload SHA-256; announced size 28.69 MB vs GitHub “about 31 MB”.
4. D3 BreathSense card conflicts: 108 participants / 432 recordings vs 90 / 360 vs 108-participant file-structure counts. Unresolved.
5. D3 license field unverified (Hugging Face API 403 during this audit). Non-blocking.
6. V1 has no `INPUT_UNAVAILABLE` neural class; later stages must still fail closed.

---

## 7. Exit gate

```text
D0_ROLE_UNAMBIGUOUS = YES
D1_ROLE_UNAMBIGUOUS = YES
D2_ROLE_LOCKED = YES
D3_NON_BLOCKING = YES
D2_PRELOCK_ACCESS_AUDIT_EXISTS = YES
D2_MODEL_INFERENCE_COUNT = 0
MR60_SUPERVISED_USE_FORBIDDEN = YES
OLD_HELDOUT_SELECTION_REUSE_FORBIDDEN = YES
PARALLEL_TRACK_BRANCH_CONTAMINATION = NO
```

**Gate: `PASS_WITH_LIMITATIONS`**

---

## 8. Next lanes now authorized

If this freeze is merged, these lanes may start in parallel. None of them were started here.

| Lane | Authorized |
|---|---|
| D0 V2 split / label audit on the remaining 94-subject pool | YES |
| D1 license/download/schema/I-Q adapter | YES |
| D2 acquisition + checksum under the existing lock | YES |
| D2 semantic inspection or model inference | NO |
| D3 processed-phase / license audit | YES (non-blocking) |
| R1 representation candidates | YES |
| Q1 MR60-like synthetic corruption profile | YES |
| I1 V2 I/O + replay skeleton | YES |
| M-PV1 / training / INT8 / Pi | NO |

---

## Appendix A — registry files

| File | Role |
|---|---|
| `source_registry.json` | D0–D3 identity, roles, consumed evidence |
| `role_lock_policy.json` | D2 lock, MR60 prohibition, heldout exclusion, gate |
| `license_access_audit.json` | license/access limitations |
| `v1_failure_baseline.json` | read-only V1 identity and MR60 failure evidence |
| `exception_registry.json` | non-blocking discrepancies |
| `checksums.json` | SHA-256 of the five JSON files above |
| `validation_result.json` | focused validator output |

## Appendix B — validation

```text
python3 scripts/mmwave_m_pv0_public_multidomain_registry.py
python3 scripts/validate_mmwave_m_pv0.py
python3 -m unittest tests.test_mmwave_m_pv0
```

Focused validator: `ok=true`, `gate=PASS_WITH_LIMITATIONS`, `errors=[]`.
Unit tests: 6 passed.

## Appendix C — checksums

See `datasets/mmwave/manifests/M-PV0_public_multidomain_registry/checksums.json`. Regenerating the registry produces the same hashes.
