# SafeNest Thermal — T-C0 MI48 Device-Domain Acquisition and Evaluation Contract

## Decision and boundary

`THERMAL_MI48_DEVICE_DOMAIN_ACQUISITION_READINESS = PASS_WITH_LIMITATIONS`.

This phase freezes the evidence contract and prepares offline tooling.  The
MI48 sensor is not available, so no new frames or labels were collected.  The
existing `TRAIN_DOMAIN_RANGE_GAP` finding is retained, but it does not decide
whether the frozen Float model fails on MI48.  That question remains
`FLOAT_RETRAINING_REQUIRED = UNRESOLVED` until independently labelled,
group-aware MI48 evidence exists.

```text
NEW_MI48_DATA_COLLECTED = NO
REAL_SENSOR_REQUIRED_FOR_NEXT_PHASE = YES
NEW_FLOAT_MODEL_CREATED = NO
NEW_INT8_MODEL_CREATED = NO
EXISTING_T_B5_MODIFIED = NO
PI_O3_AUTHORIZED = NO
THERMAL_PRODUCTION_ACTIVATION = NO
```

The work is deliberately limited to the standalone SafeNest Thermal
repository.  It does not modify the Pi snapshot, the integration repository,
firmware, thresholds, the frozen Float model, or the historical FULL_INT8.

## What is already known

T-A0 through T-A6 established the SDT source and its limitations.  T-B1
through T-B5 froze the `SMALL_CNN_BASELINE_V1_P1` Float/TFLite/INT8 lineage.
T-B5Q1 recovered the canonical TRAIN payload and proved
`TRAIN_DOMAIN_RANGE_GAP`: approximately 40.56% of the fixed RP-X0 O2.6 MI48
pixels were below the complete TRAIN P1 minimum.  Those frames have no
independent ground truth, so this is a domain observation, not a model
accuracy result and not a retraining authorization.

The future Float evaluation must use this immutable artifact identity:

| Field | Frozen value |
| --- | --- |
| artifact | `models/thermal/candidates/SMALL_CNN_BASELINE_V1_P1_float32.tflite` |
| SHA-256 | `fbe891520f07e0534b1a7074dc819d8ed44bca58b27e35c78916c3ddae73a779` |
| input | float32 `[1,62,80,1]` Celsius after P1 |
| output | float32 `[1,3]` |
| P1 | `(Celsius - 22.769290618485442) / 2.8684523405441222` |
| class order | `NOT_HUMAN`, `HUMAN_NORMAL`, `HUMAN_FALL` |

The binary is not copied into this readiness PR.  The evaluation harness
fails closed if the future artifact is missing or its SHA differs.

## Raw MI48 acquisition contract

Every future capture must retain the native raw frame before resize, crop,
rotation, normalization, quantization, colorization, or model inference:

- native shape: `62 × 80`;
- native dtype: `uint16`;
- physical unit contract: `0.1 K`;
- Celsius conversion: `raw_uint16 / 10.0 - 273.15`;
- raw packet bytes when available, plus decoded native values;
- native byte order and orientation recorded as device evidence, never guessed;
- invalid, partial, duplicate, dropped, or corrupt frames retained as rows with
  explicit validity/error fields.

The session manifest records sensor identity, firmware and collector
provenance, wall and monotonic clocks, timestamps and units, geometry,
orientation, distance, environment, scenario, operator notes, and storage
references.  Subject IDs are stable pseudonyms (`SUBJ-###`); empty-room
sessions use `NONE`.  Names, student numbers, and contact information are
prohibited.

The existing `safenest.thermal.real_capture.v1` session/frame/annotation
contract remains the capture-facing schema.  T-C0 adds the MI48-specific
native-unit, sample-ID, split, builder, and evaluation requirements in
`datasets/thermal/manifests/T-C0_mi48_device_domain_acquisition/`.

## Label and safety contract

Presence and posture are independent dimensions:

| Source evidence | SafeNest compatibility target | Meaning |
| --- | --- | --- |
| `ABSENT` | `NOT_HUMAN` | frame-level absence only |
| `PRESENT + STANDING` | `HUMAN_NORMAL` | posture proxy |
| `PRESENT + SITTING` | `HUMAN_NORMAL` | posture proxy |
| `PRESENT + CROUCHING` | `HUMAN_NORMAL` | controlled low-posture proxy |
| `PRESENT + LYING` | `HUMAN_FALL` | lying-derived posture proxy only |

`HUMAN_FALL` is never temporal fall ground truth.  A controlled transition,
if separately approved as safe, must carry an event ID and ordered
`PRE_EVENT → FALL_TRANSITION → POST_FALL_LYING → RECOVERY` phase ranges.
Uncontrolled free-fall experiments are prohibited.  Unknown, ambiguous, and
unannotated frames remain provenance evidence but are not silently converted
to a pure class.

Ground truth must come from an independent session/scenario log or operator
annotation.  A Float or INT8 prediction, thermal intensity heuristic, or
another model output can never supply the evaluation label.

## Planned acquisition matrix

The machine-readable matrix marks every cell
`PLANNED_NOT_YET_COLLECTED`.  It covers empty-room controls; standing,
sitting, crouching, and lying posture-proxy sessions; partial visibility hard
conditions; and natural variation in room, background, time, distance,
position, and orientation.  The minimum planning target is three independent
pseudonymous subjects, two sessions per subject, two empty-room sessions, and
one session per core posture cell.  This is a minimum design for independent
groups, not a claim that a particular frame count is statistically sufficient.
Adjacent frames are not inflated into independent examples.

No environment is manipulated merely to force a quantizer range.  Naturally
available room/background/ambient variation is recorded as metadata.

## Lineage and deterministic sample identity

The future lineage is:

```text
MI48 native uint16
  → immutable raw capture
  → session/frames/annotation manifests
  → independent label
  → Celsius conversion
  → deterministic sample ID
  → frozen group split
  → frozen P1
  → existing Float evaluation
  → separately authorized retraining decision
```

`sample_id` is the full SHA-256 of
`safenest.thermal.mi48.sample.v1|collection_id|session_id|frame_id`, prefixed
with `MI48S1_`.  Array position is never identity.  The builder writes only
derived outputs to a separate destination and records the raw logical path,
raw checksum, frame identity, label provenance, split, conversion, and P1
profile for every included sample.

## Split and leakage policy

The split is frozen before model inspection.  Subject isolation is preferred;
session is the explicit fallback when subject diversity is insufficient.  An
event cannot cross roles.  Frame-random splitting, frame-hash splitting, and
output-dependent allocation are rejected.  `REAL_LOCKED_TEST` is reserved for
new untouched groups and cannot be used for fitting, calibration, threshold
tuning, or repeated debugging.

The builder accepts a separate deterministic split map and fails when
`--require-split` is requested without one.  Its validator rejects a subject
appearing in multiple roles and rejects missing raw-to-canonical lineage.
When adjacent-frame reduction is needed, `--sample-stride N` selects frames by
the recorded sequence index modulo `N`; it never uses per-run random sampling.

## Offline tooling prepared

The following tools are implemented without requiring a physical sensor:

1. `scripts/validate_thermal_real_capture.py` — existing capture structure,
   timing, annotation, integrity, and role validator.
2. `scripts/build_thermal_mi48_dataset.py` — read-only capture intake,
   uint16/native-shape validation, Celsius derivation, deterministic samples,
   optional frozen P1 derivation, split inheritance, and checksums.
3. `scripts/thermal_mi48_device_domain.py validate` — derived dataset
   lineage, shape/dtype, finite conversion, label, ID, and group-leakage
   validation.
4. `scripts/compare_thermal_mi48_domain.py` — Celsius/P1 percentiles and
   fractions below/above/outside the historical TRAIN range and percentile
   envelope.  These are domain diagnostics, not quality thresholds.
5. `scripts/evaluate_thermal_mi48_float.py` — exact Float SHA, tensor contract,
   frozen P1 preprocessing, confusion matrix, per-class metrics, Macro F1,
   balanced accuracy, support, and session/subject-ready sample accounting.
6. `scripts/dry_run_thermal_mi48_legacy_snapshot.py` — read-only inventory of
   the legacy RP-X0 snapshot with no copying, labels, training, or evaluation.

The builder, comparator, and evaluator do not write raw inputs.  Missing
native byte order, missing labels, missing split assignments, model SHA drift,
or absent arrays fail closed.

## Retraining decision gate

The machine-readable gate freezes three possible future outcomes:

- `EXISTING_FLOAT_DEVICE_DOMAIN_ACCEPTABLE` →
  `FLOAT_RETRAINING_REQUIRED = NO`;
- `EXISTING_FLOAT_DEVICE_DOMAIN_INADEQUATE` →
  `FLOAT_RETRAINING_REQUIRED = YES` in a separate authorized phase;
- `INCONCLUSIVE_DEVICE_DOMAIN_EVIDENCE` →
  `FLOAT_RETRAINING_REQUIRED = UNRESOLVED` and more controlled evidence.

No canonical absolute device-domain accuracy threshold currently exists in
the Thermal policy.  The future report must therefore provide confusion
matrix, per-class precision/recall/F1, Macro F1, balanced accuracy, support,
subject/session breakdowns, data quality, and confidence intervals where
justified, then obtain a separately authorized engineering acceptance gate.

## Legacy snapshot dry-run

The existing RP-X0 snapshot was inspected read-only.  It contains thermal
integration `.npz` logs but does not expose the new collection/session/sample
contract.  It is recorded as `LEGACY_SNAPSHOT_SCHEMA_COMPATIBILITY = PARTIAL`.
No files were copied or changed; no synthetic labels were assigned; no model
evaluation was run; and no snapshot frame was promoted to training or locked
test evidence.

## Exact next action when MI48 is available

Collect one safety-approved pilot collection using the frozen checklist,
finalize raw/session/annotation/checksum manifests, run the capture validator,
review every error and limitation, and stop for T-C review before any
canonical promotion, model evaluation, calibration, or training.

## Evidence and validation

The compact contract and readiness evidence are under
`datasets/thermal/manifests/T-C0_mi48_device_domain_acquisition/`.
`scripts/validate_thermal_t_c0.py` is the standalone readiness validator.
This phase is complete only when it reports `PASS_WITH_LIMITATIONS`; that
status means tooling is ready while physical hardware remains the one
non-blocking prerequisite for the next phase.  It does not authorize
acquisition, retraining, quantization, Pi O3, or production.
