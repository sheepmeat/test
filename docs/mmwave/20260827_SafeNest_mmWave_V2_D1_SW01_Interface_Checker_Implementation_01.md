# SafeNest mmWave V2 — D1 SW-01 Non-Campaign Interface Checker Implementation

- Phase: **MMWAVE-V2-D1-SWPREP-01**
- Date: 2026-08-27
- Base SHA (post-PR #170): `13a56b7e41e9519ad61238a74861ef4ad6ea16ab`
- Branch: `feature/mmwave-d1-sw01-interface-checker`
- Mode: **software-only** — no governed capture, no D1 membership, no model inference
- Terminal verdict: **`SW01_SOFTWARE_COMPLETE_LIVE_HARDWARE_PENDING`**
- Manifest: `datasets/mmwave/manifests/MMWAVE_V2_D1_sw01_interface_checker_01/`

---

## Objective

Implement frozen checklist **SW-01**: a non-campaign interface checker that verifies raw/near-raw observation availability, monotonic timestamps, continuity/dropout observability, and sensor-health telemetry — without creating campaign evidence.

Canonical parent: `datasets/mmwave/manifests/M-PV3_8_absent_resource_readiness_checklist/readiness_requirements.json` (`SW-01`).

---

## Implementation

| Artifact | Path |
|---|---|
| Library | `adapters/mmwave_sw01_interface_checker.py` |
| CLI | `scripts/mmwave/check_m_pv38_mmwave_interface.py` |
| Fixtures | `datasets/mmwave/manifests/MMWAVE_V2_D1_sw01_interface_checker_01/fixtures/` |

Modes:

1. **`FIXTURE_OFFLINE_VALIDATION`** — `--fixture PATH`
2. **`LIVE_NON_CAMPAIGN_CHECK`** — `--live` (optional `--port`)

Design constraints:

- Does **not** import `sensors.mmwave.mmwave_adapter` / `MMWaveInterpreter` (those construct model wiring).
- Reuses fail-closed stream semantics aligned with `adapters/mmwave_stream_adapter.py` (finite values, monotonic timestamps, gap threshold).
- Distinguishes **near-raw phase** vs **scalar vendor RR** (`FAIL_SCALAR_TELEMETRY_ONLY`).
- Packet received ≠ healthy: explicit `health.ok` required.
- Every receipt sets `campaign_data_created=false`, `d1_admissible=false`, `campaign_slot_consumed=false`.

---

## Fixture validation (offline)

| Fixture | overall_status |
|---|---|
| valid_stream | `PASS_NON_CAMPAIGN_INTERFACE_CHECK` |
| missing_raw | `FAIL_RAW_OR_NEAR_RAW_UNAVAILABLE` |
| missing_timestamp | `FAIL_REQUIRED_FIELD_MISSING` |
| non_monotonic | `FAIL_NON_MONOTONIC_TIMESTAMP` |
| dropout_sequence_gap | `FAIL_CONTINUITY_UNOBSERVABLE` |
| health_fault | `FAIL_HEALTH_UNAVAILABLE` |
| backend_unavailable | `BACKEND_UNAVAILABLE` |
| scalar_only | `FAIL_SCALAR_TELEMETRY_ONLY` |
| missing_identities | `FAIL_REQUIRED_FIELD_MISSING` |
| session_reset | PASS (reset events recorded) |

Identical fixture input → identical receipt (deterministic).

---

## Live status (this environment)

```text
LIVE_TARGET_AVAILABLE = false
LIVE_CHECK_EXECUTED   = true
LIVE_RESULT           = LIVE_TARGET_UNAVAILABLE  (or BACKEND_UNAVAILABLE if port hinted)
```

No live `PASS_NON_CAMPAIGN_INTERFACE_CHECK` claimed.

---

## Non-actions

- Governed 57-ABSENT capture: not executed
- D1 membership: not created
- ROLE_L load/inference: not executed
- Plan quotas/slots: unchanged

---

## Usage

```bash
python3 scripts/mmwave/check_m_pv38_mmwave_interface.py \
  --fixture datasets/mmwave/manifests/MMWAVE_V2_D1_sw01_interface_checker_01/fixtures/valid_stream.json

python3 scripts/mmwave/check_m_pv38_mmwave_interface.py --live
```


---

## Corrective 01C — live-source bridge

Sol review required completing the software acquisition→validation pipeline before hardware arrival.

### Source abstraction

```text
MR60 / ESP32 / Pi transport
        ↓
source-specific parser (future; UART binary parser NOT implemented here)
        ↓
versioned SW01 source records (`MMWAVE_V2_D1_SW01_SOURCE_RECORD_V1`)
        ↓
MMWaveSW01Source (`adapters/mmwave_sw01_source.py`)
        ↓
StreamBundle / Sample
        ↓
evaluate_stream()  (unchanged validation semantics)
```

### Backends

| Backend | Status |
|---|---|
| `JSONL_STREAM_SOURCE` (`--stream-jsonl`) | IMPLEMENTED |
| `STDIN_STREAM_SOURCE` (`--stdin-jsonl`) | IMPLEMENTED |
| `MR60_UART_SOURCE` | PLUGGABLE_NOT_IMPLEMENTED (`MR60_UART_PROTOCOL_UNPROVEN`) |

Why UART not implemented: repository mentions `0x0A13 breath_phase` semantics but does **not** contain a proven frame/CRC/command parser; inventing bytes would be unsafe.

### Modes

| Mode | Meaning |
|---|---|
| `FIXTURE_OFFLINE_VALIDATION` | Offline fixture only |
| `EXTERNAL_STREAM_NON_CAMPAIGN_CHECK` | Full source→receipt software pipeline |
| `LIVE_HARDWARE_NON_CAMPAIGN_CHECK` | Hardware probe; distinguishes transport vs parser |

`--live` with a present serial path reports `SERIAL_TRANSPORT_PRESENT` + `PARSER_BACKEND_UNAVAILABLE` rather than a single opaque failure.

### Software-complete claim

`validation_engine_status=COMPLETE`, `source_pipeline_status=COMPLETE`.
`hardware_backend_status=PENDING_PROVEN_PROTOCOL_OR_HARDWARE`, `hardware_validation_status=NOT_EXECUTED`.

External JSONL PASS proves **SOFTWARE_PIPELINE_VALIDATED**, not live hardware.
