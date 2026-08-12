# M-B10B RESULT

Track / phase: mmWave / M-B10B

Canonical base: `de7effb1a5cc3a7a95483d9dc5d135500a8cefa9`

Branch: `feature/M-B10B-locked-test-final-evaluation`

Pre-access harness commit: `7073374`

Final evidence commit: NOT CREATED — incomplete execution evidence is preserved for review

Head commit: `c18e6c2`

PR: NOT CREATED — execution-integrity blocker

## M-B10A frozen contract

Selected candidate:
- ID: `M-B3_CONV1D_GAP_BASELINE_seed42_M-B5_CAL_CLASS_BALANCED_120`
- seed: `42`
- model path: `models/mmwave/experiments/M-B6_stage_equivalence/M-B3_CONV1D_GAP_BASELINE_seed42_M-B5_CAL_CLASS_BALANCED_120_int8.tflite`
- SHA: `6dff6aaa72c79d76715d40cf7e32bb1e6cd9b2c2e3ac78eaf2fda737561430c5`
- preprocessing: `BPF_ZSCORE`
- calibration: `M-B5_CAL_CLASS_BALANCED_120`
- class map: `0 NORMAL`, `1 RAPID_OR_ABNORMAL`, `2 APNEA`

M-B10A contract SHA: `ba6429ecfe685de1807ec85b55e697ee12e24138e6b96e94715b0a1a6b19e0f7`

Candidate changed after test:
- NO

## LOCKED_TEST access

Authorization:
- explicit M-B10B authorization present: YES

Accessor implementation: `scripts/mmwave_phase_b_access.py:PhaseBAccessGuard.get_locked_test_final_evaluation_dataset`

Pre-access accessor count: `0`

Formal accessor invocations: `1`

Second accessor invocation:
- NO

LOCKED_TEST consumed:
- YES — consumed by the single authorized accessor; no result rerun is permitted

Structural subjects: expected `16`; actual subject count was not recorded before abort

Structural windows: expected `88`; actual returned `75`

Actual registry subjects: NOT GENERATED

Actual registry windows: NOT GENERATED — structural gate failed before registry preservation

## Model execution

Expected models: seed42 selected candidate, v0.1.0 historical compatibility, v0.2.0 synthetic external compatibility

Actually evaluated models: none

Unexpected models: none

seed43 evaluated:
- NO

seed44 evaluated:
- NO

Model trainings: `0`

Model conversions: `0`

Recalibration: `0`

Threshold tuning: `0`

Post-test selection: `0`

Total formal model inference invocations: `0`

## Final result status

The one-time accessor returned `75` pure-class rows because the existing final accessor excludes `AMBIGUOUS` windows, while M-B10A preregistered structural identity is `88` windows. The structural identity gate therefore failed before model inference. No labels, tensors, predictions, or metrics were persisted from the returned payload.

The execution is invalid/incomplete as final performance evidence. The consumed split must not be reopened or reused in this experimental cycle.

Predefined numerical final-test threshold: `FINAL_LOCKED_TEST_NUMERICAL_ACCEPTANCE_THRESHOLD_NOT_PREDEFINED`

## One-time evidence gates

- Sample registry gate: NOT REACHED
- Same-test/same-order gate: NOT REACHED
- Model artifact gate: PASS before access
- Preprocessing contract gate: PASS before access
- Class-map gate: PASS before access
- Prediction-ledger gate: NOT REACHED
- Metric independent recomputation: NOT REACHED
- Subject-level recomputation: NOT REACHED
- Quantization audit: NOT REACHED
- No-retuning gate: PASS (`0` training/conversion/recalibration/tuning)
- Test-consumption gate: BLOCKED by structural identity mismatch
- Checksums: PASS for incomplete evidence directory

## Tests / regressions

- M-B10A validator: PASS before access
- M-B10B pre-access validator: PASS
- M-B10B pre-access focused tests: PASS (post-access corruption matrix not run because no successful result ledger exists)
- M-B9–M-B0 plus A5/A6 validators: PASS before access

## Git isolation

- Unique M-B10B commits before access: `2`
- Pre-access commit precedes incomplete evidence: YES
- Unrelated-track commits: `0`
- AGENTS.md: `0`
- models/model_manifest.json: `0`
- CO₂: `0`
- Thermal: `0`
- Integration/shared: `0`
- raw payload: `0`
- Working tree: pending incomplete-evidence commit

## Claim boundaries

- OFFLINE_REAL_DATA: NOT CLAIMED — final inference did not complete
- REAL_SUBJECT_GENERALIZATION: NOT CLAIMED
- MR60_VALIDATED: NO
- RASPBERRY_PI_VALIDATED: NO
- PRODUCTION_READY: NO
- CLINICAL_APNEA_VALIDATED: NO

## Warnings

- The authorized LOCKED_TEST split is consumed and cannot be reopened under this cycle's one-time policy.
- The accessor/contract structural identity mismatch requires independent review and a new holdout/reuse policy for any future attempt.

## Blockers

- `BLOCKER: M-B10B_LOCKED_SPLIT_IDENTITY_MISMATCH` — accessor returned `75` pure-class rows versus preregistered `88` structural windows.

## M-B11 authorization recommendation

NO — M-B10B execution integrity requires review; LOCKED_TEST must NOT be reopened

M-B10B_ONE_TIME_EVALUATION_INCOMPLETE_NO_RERUN
