# SafeNest mmWave V2 — M-PROT-4 System-Level Offline / Replay / Synthetic Smoke

- Phase: **M-PROT-4**
- Date: 2026-08-27
- Base SHA (post-PR #178): `31a4ab6803266a9bdf4a1645a4408a9d29f7333f`
- Branch: `research/mmwave-m-prot-4-system-smoke`
- Worker terminal: **`M_PROT_4_SYSTEM_SMOKE_IMPLEMENTED`**
- Sol review: **PENDING** (`M-PROT-5 = NOT_AUTHORIZED`)
- Manifest: `datasets/mmwave/manifests/M_PROT_4_system_smoke/`

## Purpose

Prove the merged M-PROT-3 integration path operates together under deterministic offline/replay fixtures.

Not model accuracy evaluation, not live MR60/Pi validation, not final scientific selection.

## Flow

```mermaid
flowchart LR
  FIX["Deterministic fixture<br/>StreamBundle"]
  ING["MProt3IntegrationRuntime<br/>ingest_bundle"]
  INF["try_infer"]
  WIR["WiringReceipt V3"]
  SMK["M-PROT-4 SmokeReceipt V1"]

  FIX --> ING --> INF --> WIR --> SMK
```

Module: `adapters/mmwave_m_prot_4_system_smoke.py`

Uses **only** the real M-PROT-3 public API. No direct B23 bypass. No M-N9.

## Coverage

| Case | Result class |
|---|---|
| Valid 10 Hz | physiology-eligible path / R1=300 |
| Valid 20 Hz | R1 downsample / R1=300 |
| Multi-bundle continuous | receipt chain preserved |
| Deterministic repeat | structural equality |
| SW-01 fail after ready | stale state invalidated |
| Scalar RR / missing phase | fail-closed |
| Seq gap / regression | no bridge / WINDOW_NOT_READY |
| Timestamp regression / large gap / session / reset | no bridge |
| WINDOW_NOT_READY | fail-closed |
| &lt;10 Hz | R1 fail-closed |
| PRESENCE_UNAVAILABLE | no physiology |
| R1 count mismatch inject | R1_SAMPLE_COUNT_MISMATCH |
| Artifact SHA mismatch inject | ARTIFACT_SHA_MISMATCH |

## Presence limitation

Fixtures may set `presence_gate_satisfied=True` solely to exercise the frozen path.

```text
LIVE_PRESENCE_SOURCE_NOT_PROVEN
```

## Parallel ownership

- Luna1 fixture tooling: not integrated; minimal local builders used
- Luna2 SmokeReceipt validator: not integrated; thin local `SmokeReceipt` used
- Primary branch remains independently functional

## Track F unchanged

```text
D1 57/0 BLOCKED_INVALID_FINAL_MEMBERSHIP
M-PV3.8 RESOURCE_BLOCKED_CLOSED
M-PV4 UNAUTHORIZED
D2 LOCKED
```

## Next

Sol exact-head review. Do not merge. Do not start M-PROT-5.
