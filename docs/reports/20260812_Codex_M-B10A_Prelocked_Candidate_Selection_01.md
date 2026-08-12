# SafeNest mmWave M-B10A — Pre-LOCKED_TEST Real-Data Candidate Selection Setup

## Execution identity

- Track: mmWave M-B10A; branch: `feature/M-B10A-candidate-selection-setup`; base `origin/main`: `4e3c2e6957a3142f0ff3da8ec50f3bc0b4c94602`.
- M-B9 predecessor: closure `8fe4b2b38a0faa7b4cf87628f769c07763c6c91d` merged by PR #42 and present in the base.
- Worktree isolation: fresh branch from `origin/main`; no CO₂, Thermal, Integration, shared-contract, config, risk, or raw-data files are in scope.

## Scope and gate

This report records a deterministic pre-LOCKED_TEST candidate-selection setup from frozen real-data VALIDATION evidence. It is not a final LOCKED_TEST result, MR60 result, real-sensor validation, production claim, or clinical apnea claim.

- Base branch evidence: `origin/main` predecessor M-B9 closure is present; input identity rows: 73.
- Model trainings: 0; model conversions/reconversions: 0; no threshold tuning or retuning; no formal M-B8 latency rerun.
- LOCKED_TEST performance/label/prediction/tensor accesses: all 0; M-B10B started: NO.

## Frozen candidate pool

The candidate pool contains three frozen real-data strict-INT8 variants; hard gates decide which remain eligible:

| seed | bytes | clean Macro F1 | min recall | APNEA P/R | worst subject Macro F1 | hard gates |
|---:|---:|---:|---:|---:|---:|---|
| 42 | 22080 | 0.666231 | 0.454545 | 0.698113 / 1.000000 | 0.222222 | E1=PASS, E2=PASS, E3=PASS, E4=PASS, E5=PASS, E6=PASS, E7=PASS, E8=PASS, E9=PASS, E10=PASS, E11=PASS; E11 PASS |
| 43 | 22136 | 0.441240 | 0.272727 | 0.857143 / 0.486486 | 0.000000 | E1=PASS, E2=PASS, E3=PASS, E4=PASS, E5=PASS, E6=PASS, E7=PASS, E8=PASS, E9=PASS, E10=PASS, E11=PASS; E11 PASS |
| 44 | 22136 | 0.329107 | 0.050000 | 0.521127 / 1.000000 | 0.166667 | E1=PASS, E2=PASS, E3=PASS, E4=PASS, E5=PASS, E6=PASS, E7=PASS, E8=PASS, E9=PASS, E10=PASS, E11=FAIL; E11 FAIL: M-B7_AMP_X0_75, M-B7_COMBINED_MODERATE |

Pool identity is fixed to M-B3_CONV1D_GAP_BASELINE + M-B1 BPF_ZSCORE + M-B2 CE_UNWEIGHTED + M-B5 class-balanced calibration, seeds 42/43/44. Historical v0.1.0 and synthetic v0.2.0 artifacts are registered as baselines only and are excluded from the pool.
- Seed 42 artifact: `models/mmwave/experiments/M-B6_stage_equivalence/M-B3_CONV1D_GAP_BASELINE_seed42_M-B5_CAL_CLASS_BALANCED_120_int8.tflite`, SHA-256 `6dff6aaa72c79d76715d40cf7e32bb1e6cd9b2c2e3ac78eaf2fda737561430c5`.
- Seed 43 artifact: `models/mmwave/experiments/M-B6_stage_equivalence/M-B3_CONV1D_GAP_BASELINE_seed43_M-B5_CAL_CLASS_BALANCED_120_int8.tflite`, SHA-256 `cf39c5ce28b4e495d2d721ec5456713618a8f19c3dbe55c600ca222d0228d8f6`.
- Seed 44 artifact: `models/mmwave/experiments/M-B6_stage_equivalence/M-B3_CONV1D_GAP_BASELINE_seed44_M-B5_CAL_CLASS_BALANCED_120_int8.tflite`, SHA-256 `30a487f73239078e9e22ce09b530750ac16f4850e33cce5af11e6feced98d08d`.

## Frozen rule and ranking

- Selection-rule SHA-256: `cddf98cbcf2231075bcfc02db2223fbc80fa33f7c52e23820609b5a273046f84`; EPS = `1e-05`.
- Lexicographic criteria are applied in preregistered order, with no composite score.
- Eligible candidates: M-B3_CONV1D_GAP_BASELINE_seed42_M-B5_CAL_CLASS_BALANCED_120, M-B3_CONV1D_GAP_BASELINE_seed43_M-B5_CAL_CLASS_BALANCED_120.
- Selected prelocked candidate: `M-B3_CONV1D_GAP_BASELINE_seed42_M-B5_CAL_CLASS_BALANCED_120`.
- Deciding criterion: {'criterion_rank': 1, 'metric': 'clean_strict_int8_macro_f1', 'direction': 'higher', 'description': 'Higher clean strict-INT8 VALIDATION Macro F1', 'winner_value': 0.666231, 'runner_up_value': 0.44124, 'absolute_difference': 0.224991}.

## Seed sensitivity and perturbation warnings

- M-B4 architecture-level seed sensitivity (mean/std/worst clean Float Macro F1): 0.481275 / 0.138266 / 0.329107 (worst seed 44).
- Seed 44 fails hard E11 on `M-B7_AMP_X0_75` and `M-B7_COMBINED_MODERATE`; severe profiles are diagnostic only.

## Historical baselines

- `mmwave_resp_int8`: `models/mmwave/mmwave_resp_int8_v0.1.0.tflite`, SHA-256 `43cdd6f321c2b645232162233e098c2b65549388cbc9e680a17a0eccdc8f0158`, pool eligible: NO (BLOCKED).
- `mmwave_resp_int8_v0.2.0_candidate`: `models/mmwave/mmwave_resp_int8_v0.2.0_candidate.tflite`, SHA-256 `85c023d3eefca13ecbb72a841974e53a56d5f4173920645d46df49a9088452ff`, pool eligible: NO (SYNTHETIC_SMOKE_ONLY).

## M-B10B contract and readiness

- Final contract is preregistered for one LOCKED_TEST pass with accuracy, Macro F1/precision/recall, per-class metrics, confusion matrix, APNEA proxy precision/recall, invalid/fallback count, and input saturation.
- No selection, tuning, retraining, recalibration, or threshold changes are allowed after access; readiness used: NO; independent review required.
- No final performance number is present in M-B10A artifacts.

## Warnings and authorization

- REQUIRED REFINEMENT: independent review must confirm the frozen rule, lineage, eligibility gates, and ranking before any M-B10B authorization.
- REQUIRED REFINEMENT: architecture-level initialization seed sensitivity remains visible (M-B4 mean/std/worst-seed evidence); selecting seed 42 does not erase that warning.
- NON-BLOCKING IMPROVEMENT: M-B7 severe profiles remain diagnostic warnings and are not hard-gated by the frozen rule.
- NON-BLOCKING IMPROVEMENT: M-B8 is macOS-only offline evidence and does not establish Raspberry Pi or MR60 performance.

## Final-test protocol status

The final LOCKED_TEST metrics contract is preregistered but unused. M-B10B authorization recommendation: NO until independent review is complete.

## Verification and artifacts

- M-B10A validator: PASS; focused unittest: 8 methods (7 negative corruption cases as subtests); upstream M-B0 through M-B9 plus A5/A6 validators: PASS.
- Evidence directory: `datasets/mmwave/manifests/M-B10A_candidate_selection_setup/` (16 machine-readable outputs plus checksums).
- Report: `docs/reports/20260812_Codex_M-B10A_Prelocked_Candidate_Selection_01.md`; LOCKED_TEST access readiness used: NO.
