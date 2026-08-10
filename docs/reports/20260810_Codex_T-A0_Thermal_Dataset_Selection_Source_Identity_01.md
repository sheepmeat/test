# SafeNest Thermal T-A0 Dataset Selection and Source Identity

- Phase: `T-A0`
- Audit date: `2026-08-10`
- Overall outcome: `BLOCKED`
- T-A1 authorized: `NO`

## Decision

No candidate satisfies all T-A0 selection gates. The local payload exists and is intentionally Git-ignored, correcting the roadmap wording to `NO_APPROVED_CANONICAL_REAL_THERMAL_EVALUATION_DATASET`; absence from Git is not absence from the owner workspace.

The SDT source is reproducibly identified, but it is a static pose dataset: source label 0 is **lying**, not fall. It has no subject/session/sequence/event identifiers. Family A is a 6,748-file RGB colorized rendering collection with unknown prefix meanings, identity, license and grouping. The additional tree contains presence polygons, not fall labels. The processed NPZ is legacy mixed-source evidence and is not canonical.

## Candidate comparison

| Candidate | Representation | Label/group evidence | Access/license | T-A0 status |
|---|---|---|---|---|
| Local Family A | RGB thermal colorized rendering | Unknown labels and grouping | Identity/license unknown | `REJECTED_PROVENANCE` |
| Local SDT | 16-bit thermal Kelvin encoding + depth; synthetic train/validation, real test | Pose labels only; no grouping IDs | Open, but official terms conflict | `REJECTED_LABEL_QUALITY` |
| Local human/not-human tree | RGB/RGBA thermal screenshots/exports | Presence polygons only | Identity/license unknown | `REJECTED_PROVENANCE` |
| eHomeSeniors | Numeric thermal temperature and raw fields | Six subjects and staged fall types; no documented normal sequences or explicit repeated-event boundaries | Open supplement; dataset-specific terms need review | `NEEDS_MANUAL_REVIEW` |
| MUVIM | Encoded thermal video plus other modalities | Strong publication-level subject/ADL/fall structure | Author request; terms unverified | `ACCESS_BLOCKED` |
| Thermal Fall 66 | Thermal representation not inspectable | Publication claims 66 participants | Author request; terms unverified | `ACCESS_BLOCKED` |

## Local inventory

- Family A: 6,748 PNG, 224,906,370 logical bytes; 3,723 readable RGB 230×226 files and 3,025 dataless placeholders.
- SDT: `test.zip` is materialized and byte-identical to official MD5; it contains 8,000 `image_t`, 8,000 `image_d`, and 8,000 five-field labels. Four train parts and validation are dataless placeholders. No large hydration was attempted.
- Processed NPZ: 330,777,971 bytes, SHA-256 `3d6ad1eb2ed0438f0faaf83abed8b6e2c175074dfa031dcb4a5739c45984d06e`; only `X` `(54218,62,80)` float32 and `y` `(54218,)` int32 survive.
- Additional tree: 410 images and 410 JSON annotations; all JSON and 213 images are readable, while 197 images are dataless placeholders.

## Processed NPZ lineage

Selected SDT test samples exactly match NPZ rows 40,000–47,999 under the current preparation transform. Code order, segment counts and local spot matches support a partial reconstruction of 32,000 SDT train + 8,000 SDT validation + 8,000 SDT test + 20 additional-tree images + 6,198 Family A images. Exact per-row source IDs, generation commit, skip reasons and original grouping are absent, so the artifact remains `PROCESSED_LINEAGE_PARTIALLY_RECONSTRUCTED` and `NOT_T_A_CANONICAL`.

`thermal_prep.py` merges original train/validation/test sources and silently swallows broad exceptions. `thermal_train.py` then defines a seeded frame-level 80:20 permutation. This is confirmed code risk; execution against the current TFLite artifact is not independently proven by an immutable training record.

## Contract boundaries preserved

Per-frame min-max normalization discards absolute Celsius context. Thermal-44 physical unit, dtype, endianness, raw-count conversion, invalid pixels, 9,920-versus-10,080 bytes, real driver and hardware/Pi evidence remain `NOT_VERIFIABLE` and deferred to `T-C`. No T-A1 split, tensor regeneration, training or model-performance claim was created.

## T-A1 gate

`T-A1 authorized: NO`. A later owner decision must either obtain and approve a candidate with explicit data terms, normal/hard-negative sequences, fall-event semantics/boundaries and subject/session/event grouping, or authorize a carefully separated multi-source design whose evaluation grouping cannot exploit source identity.
