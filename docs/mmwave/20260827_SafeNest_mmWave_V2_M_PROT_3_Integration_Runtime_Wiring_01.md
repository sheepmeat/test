# SafeNest mmWave V2 — M-PROT-3 Integration Runtime Wiring

- Phase: **M-PROT-3**
- Date: 2026-08-27
- Base SHA (post-PR #176 / M-PROT-2): `97b742dbc9c23d02cf3a74e0d4134ab76b2d0eaa`
- Branch: `research/mmwave-m-prot-3-integration-runtime-wiring`
- Worker terminal: **`M_PROT_3_INTEGRATION_RUNTIME_WIRING_COMPLETE`**
- Corrective round 1: **worker CLOSED / Sol review PENDING**
- Sol review: **required** (`M-PROT-4 = NOT_AUTHORIZED_PENDING_M_PROT_3_SOL_REVIEW`)
- Manifest: `datasets/mmwave/manifests/M_PROT_3_integration_runtime_wiring/`
- Previous Sol-reviewed head: `f6101abb76e2f6980565daf845b56804980978c6`

## Provisional freeze ≠ final scientific selection

```text
PROVISIONAL INTEGRATION / DEPLOYMENT FREEZE
!=
FINAL SCIENTIFIC MODEL SELECTION
```

B23 remains:

```text
PROTOTYPE_INTEGRATION_ONLY
NOT_FINAL_SELECTED_MODEL
NOT_DEPLOYMENT_VALIDATED
NOT_SAFETY_VALIDATED
NOT_CLINICAL_VALIDATION
SUBJECT_TO_REPLACEMENT
PROVISIONAL_INTEGRATION_FREEZE = true
REPLACEMENT_REQUIRES_CONTROL_TOWER_DECISION = true
```

No winner / best-model / M-PV3.8-selected language.

## What was wired

```mermaid
flowchart LR
    SRC["SW-01 Source"]
    VAL["SW-01 Validation PASS"]
    WIN["M-PROT-3 Temporal Composer<br/>causal TIME coverage ≥ 29.9 s"]
    R1["R1 Common Trace<br/>owns resampling → exactly 300 @ 10 Hz"]
    R2["R2 Features"]
    IN["621-d B23 Input"]
    B23["B23 Frozen Prototype"]
    OUT["WiringReceipt V2"]

    SRC --> VAL
    VAL --> WIN
    WIN --> R1
    R1 --> R2
    R2 --> IN
    IN --> B23
    B23 --> OUT

    VAL -.->|fail / no admit| FC1["SOURCE_VALIDATION_FAILED / SW01_ADMISSION_REQUIRED"]
    WIN -.->|insufficient time| FC2["WINDOW_NOT_READY"]
    WIN -.->|presence gate closed| FC3["PRESENCE_UNAVAILABLE"]
    R1 -.->|rate/gap/count| FC4["R1_* / R1_SAMPLE_COUNT_MISMATCH"]
```

Module: `adapters/mmwave_m_prot_3_integration_runtime.py`

Reuses:

- SW-01 `evaluate_stream` / `Sample` / `StreamBundle` (PASS required before admission)
- R1 `adapt_native_trace` (`R1-A_NATIVE_CENTERED_RELATIVE_MOTION_10HZ_V1`) — **only** resampler
- M-PROT-2 `run_prototype_inference` / `resolve_verified_runtime` (R2 → Stage0/1 → B23), loaded **after** non-model gates

Does **not** reimplement B23, R1 resampling, R2 formulas, or invent MR60 UART framing.

## Window contract

| Field | Value |
|---|---|
| Readiness basis | **CAUSAL_TIME_COVERAGE** (not `source_count >= 300`) |
| Target span | 29.9 s indexed grid (`(300-1)/10`) for conceptual 30 s / 300 @ 10 Hz |
| Source domain | full causal suffix covering `[T_end-29.9, T_end]` passed to R1 |
| R1 | owns downsampling; output must be **exactly** 300 (no trim/pad) |
| Causal | past-only |
| Session change | flush |
| Reset | flush |
| Large gap | flush, no bridge / no silent interpolation |
| Insufficient history | `WINDOW_NOT_READY` (not ABSENT/APNEA) |
| Production cadence | `NOT_GOVERNED_IN_M_PROT_3` (caller-triggered) |

**10 Hz vs 20 Hz:** at 10 Hz, 300 samples happen to span 29.9 s. At 20 Hz, ~599–600 source samples covering ~30 s are required before R1 downsamples to 300. Counting 300 source samples at 20 Hz is only ~15 s and must remain `WINDOW_NOT_READY`.

## Presence

SW-01 does not provide a governed human-presence signal. M-PROT-3 therefore:

- does **not** infer presence from breathing/RR/amplitude,
- defaults to `PRESENCE_UNAVAILABLE`,
- requires an **explicit** caller `presence_gate_satisfied=True` (alias: `presence_available`) for physiology.

## Fail-closed precedence

```text
SW-01 validated admission
→ WINDOW readiness (time coverage)
→ PRESENCE gate (explicit)
→ R1 admissibility + exact 300
→ runtime/model/scaler dependency
→ M-PROT-2 QUALITY / PHYSIOLOGY
```

`scalar_rr` is never a B23 waveform substitute. No M-N9 fallback.

## Sol Corrective Closure

Previous Sol-reviewed head: `f6101abb76e2f6980565daf845b56804980978c6`

| # | Finding | Problem | Correction | Evidence | Worker |
|---|---|---|---|---|---|
| 1 | SW-01 validation bypass | `push_sample` / `require_sw01_pass=False` / forged `_last_source_status` | Production path = `ingest_bundle` after `STATUS_PASS` only; binding stamps buffer; public bypass removed | `test_d_*`, `test_e_*`, `test_p_*` | CLOSED |
| 2 | Source-count windowing | `ready` when count≥300; post-R1 trim | Time-coverage suffix; R1 owns resampling; mismatch → `R1_SAMPLE_COUNT_MISMATCH` | `test_a_*`, `test_b_*`, `test_c_*`, `test_k_*` | CLOSED |
| 3 | Eager model load | `ensure_runtime()` before window/presence | Load only after SW-01 + window + presence + R1 exact-300 | `test_m_*`, `test_n_*` | CLOSED |
| 4 | Stale AGENTS pointer | M-PROT-2 still said Sol review of #176 / M-PROT-3 not authorized | AGENTS: M-PROT-2 COMPLETE/MERGED; current gate = M-PROT-3 pending Sol; M-PROT-4 not authorized | `AGENTS.md` | CLOSED |
| 5 | Provenance (recommended) | Receipt lacked SW-01 identities | WiringReceipt V2 binds device/interface/config/observation/receipt SHA | `test_q_*` | CLOSED |

```text
WORKER_CLAIM = CLOSED
SOL_REVIEW = PENDING
```

Do **not** treat worker closure as Sol PASS / merge / M-PROT-4 authorization.

## Integration-repo read-only audit

| Field | Value |
|---|---|
| Repo | `https://github.com/yuname121/integration.git` |
| Branch | `main` |
| Commit | `c759205bfae0adbbd3a33235718801a8e476b28c` |
| Modified | **NO** |

Future seam documented; Pi torch remains **not live verified**.

## Frozen identities

| Item | Value |
|---|---|
| B23 artifact SHA-256 | `8f7de6f50d6ff62ff9b0ebfaed0b1fccd8d194c7e33781bc5b93366fae251a2c` |
| Parameter SHA-256 | `6db949c242e25888dd20c3fc8e2305af03448aa229e3ca73e4159216a266d78e` |
| Scaler content SHA-256 | `5a2583b5b5064be5480b0cf56f2a2c12d40a4a2d005eb087dc8e12106881159c` |
| Assembled dim | 621 |

## Not executed

- Live hardware / MR60 UART capture
- M-PROT-4 system smoke
- Training / threshold retune / TFLite / INT8
- Final selection / M-PV3.8 reopen / M-PV4
- Model replacement

## Known limitations

- `MR60_UART_PROTOCOL_UNPROVEN`
- Pi torch / latency not live verified
- Live presence source not proven
- Production inference cadence not governed
- Fixture lineage only (`FIXTURE_NON_CAMPAIGN`)

## Track F unchanged

```text
D1 PRESENT=57 ABSENT=0
MEMBERSHIP=BLOCKED_INVALID_FINAL_MEMBERSHIP
M-PV3.8=RESOURCE_BLOCKED_CLOSED
M-PV4=UNAUTHORIZED
D2=LOCKED
```

ROLE_L panel unchanged: B11 B23 B47 C11 C23 C47.

## Next

Sol exact-head review of PR #177 corrective. **Do not merge. Do not start M-PROT-4** until authorized.
