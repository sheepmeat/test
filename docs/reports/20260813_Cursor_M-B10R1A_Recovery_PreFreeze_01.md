# M-B10R1-A — Limited Holdout-Reuse Recovery Harness Pre-Freeze

**RECOVERY HAS NOT BEEN EXECUTED**

**LOCKED_TEST HAS NOT BEEN REOPENED DURING M-B10R1-A**

## Status

| Field | Value |
|---|---|
| Phase | M-B10R1-A |
| Generated at (UTC) | 2026-08-12T15:31:49Z |
| Recovery execution authorized | false |
| Recovery payload release authorized | false |
| New recovery accessor invocations | 0 |
| New recovery payload releases | 0 |
| Recovery model inference | 0 |
| M-B10R1-B started | false |
| M-B11 started | false |

## Purpose

Freeze the limited-reuse recovery harness, access controller, metric engine,
future runner, validators, and pre-access contracts **without** releasing any
LOCKED_TEST recovery payload.

## Historical original access (preserved)

- Original M-B10B final accessor invocations: **1**
- Original rows returned: **75**
- Original model inference: **0**
- Original LOCKED_TEST consumed: **true**
- Original pristine status: **false**

## Frozen recovery population

- Structural windows: **88**
- Supervised eligible: **75**
- Excluded AMBIGUOUS: **13**
- Subjects: **16**
- Provenance: `PREEXISTING_A6_METADATA_VERIFIED`
- Positional truncation: **false**
- Eligibility: `assignment_status != AMBIGUOUS` (A6 semantics)

## Exact future model set (3)

1. `M-B3_CONV1D_GAP_BASELINE_seed42_M-B6_STRICT_INT8` SHA `6dff6aaa72c79d76715d40cf7e32bb1e6cd9b2c2e3ac78eaf2fda737561430c5`
2. `mmwave_resp_int8` SHA `43cdd6f321c2b645232162233e098c2b65549388cbc9e680a17a0eccdc8f0158`
3. `mmwave_resp_int8_v0.2.0_candidate` SHA `85c023d3eefca13ecbb72a841974e53a56d5f4173920645d46df49a9088452ff`

Forbidden: seed43, seed44, fourth model.

Expected future inferences (M-B10R1-B only): **225** (= 75 × 3).

## Access design

- Module: `scripts/mmwave_m_b10r1_recovery_access.py`
- Distinct token id: `M_B10R1_LIMITED_REUSE_RECOVERY_AUTHORIZATION_V1`
- Original final token rejected: `AUTHORIZED_FINAL_LOCKED_TEST_EVALUATION_TOKEN_V1`
- `mmwave_phase_b_access.py` unmodified (0 diff required)
- At-most-one recovery payload release
- Historical original counters never reset
- Result designation: `REUSED_LOCKED_TEST_AFTER_PREINFERENCE_STRUCTURAL_ABORT`

## Result limitation

Future recovery results (if independently authorized) are **not pristine** and
must carry designation `REUSED_LOCKED_TEST_AFTER_PREINFERENCE_STRUCTURAL_ABORT`.

## Explicit non-claims

- No recovery performance numbers
- No LOCKED_TEST reopen during this phase
- No M-B10R1-B authorization
- No M-B11 start
