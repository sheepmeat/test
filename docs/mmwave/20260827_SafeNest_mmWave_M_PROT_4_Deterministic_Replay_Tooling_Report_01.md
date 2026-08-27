# SafeNest mmWave V2 — M-PROT-4 Deterministic Replay / Fixture Tooling

## Gate and ownership

- Phase: `M-PROT-4`
- Lane: `DETERMINISTIC_REPLAY_TOOLING`
- Write gate: `OPEN`
- PR #178: `MERGED`
- Base: `origin/main` at `31a4ab6803266a9bdf4a1645a4408a9d29f7333f`
- Branch: `tooling/mmwave-m-prot-4-deterministic-replay`
- Scope: fixture specification, deterministic materialisation, validator, and focused tests only

The M-PROT-3 runtime, SW-01 checker, Grok1 system-smoke harness, `AGENTS.md`, Track F, B23, model, and scaler were not modified.

## Implementation

`tests/helpers/mmwave_m_prot_4_replay.py` imports the canonical SW-01 `Sample` and `StreamBundle` classes from `adapters/mmwave_sw01_interface_checker`. It does not define replacement runtime types and does not call around SW-01.

The compact catalog at `tests/fixtures/mmwave/m_prot_4/fixture_catalog.json` records explicit:

- sample rate, duration, waveform profile, frequency, amplitude, and integer seed;
- semantic start timestamp and sequence number;
- session, device, interface, configuration, observation-kind, and health metadata;
- bundle partitioning; and
- ordered mutations.

Materialisation uses a sine waveform with a seed-derived phase offset. It uses no PRNG, wall-clock value, sleep, transport simulation, or machine path. Every generated item is a real SW-01 `Sample`/`StreamBundle` object. `ReplayFixture.replay_into()` calls `ingest_bundle()` once per bundle and then calls the caller-owned runtime's `try_infer()`; it never imports or changes the M-PROT-3 runtime.

## Supported fixture cases

| Case | Fixture | Coverage |
|---|---|---|
| `VALID_10HZ_30S` | `valid_10hz_30s` | 301 samples, one bundle, 10 Hz, 30 s |
| `VALID_20HZ_30S_MULTIBUNDLE` | `valid_20hz_30s_multibundle` | 601 samples, 20 Hz, three bundles |
| `VALID_LONGER_THAN_WINDOW` | `valid_longer_than_window_40s` | 401 samples, 10 Hz, early receipt ages out of a 30 s window |
| `INSUFFICIENT_DURATION` | `insufficient_duration` | 21 samples, 10 Hz, 2 s effective duration |
| `SEQ_GAP` | `seq_gap_multibundle` | second bundle begins with a +2 sequence offset |
| `SEQ_REGRESSION` | `seq_regression_multibundle` | second bundle begins one sequence before its predecessor |
| `TIMESTAMP_REGRESSION` | `timestamp_regression_multibundle` | second bundle begins 0.2 s behind its predecessor |
| `LARGE_TIMESTAMP_GAP` | `large_timestamp_gap_multibundle` | second bundle begins with a 1.0 s gap |
| `SESSION_TRANSITION` | `session_transition_multibundle` | session ID changes at the second bundle |
| `RESET` | `reset_multibundle` | reset flag is set on the second bundle's first sample |
| `HEALTH_FAILURE` | `health_failure_10hz` | explicit false health and `FIXTURE_HEALTH_DOWN` fault |
| `MISSING_PHASE` | `missing_phase_10hz` | one phase value is `None`; no replacement value is inserted |
| `SCALAR_RR_ONLY` | `scalar_rr_only_10hz` | all phase values are absent; scalar RR is explicit |
| `IDENTITY_CHANGE` | `identity_change_multibundle` | device identity changes at a bundle boundary |
| `CONFIGURATION_CHANGE` | `configuration_change_multibundle` | configuration identity changes at a bundle boundary |
| `BELOW_10HZ` | `below_10hz_5hz` | 151 samples at 5 Hz; no upsampling is performed |

Boundary mutations are intentionally applied to the suffix beginning at a bundle boundary. This lets SW-01 validate each bundle independently while the real M-PROT-3 cross-bundle cursor observes and refuses an invalid continuation.

## Determinism and checksums

The fixture SHA-256 is computed over canonical JSON containing the materialisation version, original spec, effective timing, bundle partition, bundle metadata, and every sample field. JSON keys are sorted and separators are fixed.

- Same spec: identical canonical bytes and identical fixture SHA-256.
- Semantic change (for example, changing the explicit seed): different fixture SHA-256.
- JSON key insertion order only: unchanged spec SHA-256 and fixture SHA-256.
- No absolute paths or `file://` values are present in the materialised payload.

The generated registry is `tests/fixtures/mmwave/m_prot_4/fixture_checksums.json`. It records each compact spec SHA-256 and materialised fixture SHA-256. `tests/fixtures/mmwave/m_prot_4/checksums.sha256` covers both committed fixture artifacts.

## Validation evidence

The focused suite passed: 12 tests covering catalog coverage, timing, bundle partitioning, mutation preservation, SW-01 type identity, real M-PROT-3 replay, fail-closed invalid inputs, long-window ageing, deterministic bytes, SHA changes, and path leakage.

The standalone validator passed all 16 catalog entries:

```text
python3 scripts/validate_mmwave_m_prot_4_replay.py --pretty
status: PASS
fixture_count: 16
determinism: PASS_SAME_SPEC_SAME_BYTES_AND_SHA256
fixture_registry: PASS
sw01_checksum_file: PASS
sw01_types: PASS_CANONICAL_SAMPLE_AND_STREAMBUNDLE
```

The validation lane does not load a model, access D2, use MR60 supervised physiology, or assert B23 science metrics.

## Grok1 integration instructions

From the repository root, Grok1 can replay a catalog entry through the real runtime as follows:

```python
from pathlib import Path

from adapters.mmwave_m_prot_3_integration_runtime import MProt3IntegrationRuntime
from tests.helpers.mmwave_m_prot_4_replay import load_fixture

fixture = load_fixture(
    Path("tests/fixtures/mmwave/m_prot_4/fixture_catalog.json"),
    fixture_id="valid_20hz_30s_multibundle",
)
runtime = MProt3IntegrationRuntime(root=Path.cwd())
result = fixture.replay_into(
    runtime,
    infer_kwargs={
        "presence_gate_satisfied": False,
        "lineage_class": "FIXTURE_NON_CAMPAIGN",
    },
)
```

`result.sw01_receipts` is ordered by bundle. `result.inference_receipt` is the receipt returned by the runtime after all bundles have been ingested. Use `presence_gate_satisfied=True` only in a caller-owned test that is explicitly authorized to load the frozen prototype artifact. For health-failure and scalar-RR fixtures, catch the runtime's fail-closed exception and assert that no ready state is retained. For sequence, timestamp, session/reset, identity, and configuration boundary fixtures, ingest every bundle and assert that the composer does not bridge the boundary. No fixture helper should be used to infer transport latency or hardware timing.

## Result

`M-PROT-4` deterministic replay / fixture tooling is standalone and ready for Grok1's system-smoke harness. No M-PROT-3 runtime behavior or model artifact was changed.
