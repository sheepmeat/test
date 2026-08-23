# SafeNest mmWave V2 — M-PV3.8 ABSENT Capture Preflight Result 01

Date: 2026-08-23

Phase: `M-PV3.8`

Result: `CAPTURE_BLOCKED`

## Scope and conclusion

This is a preflight-only result for the bounded M-PV3.8 ABSENT acquisition campaign. No recording was started, no ABSENT sample or final membership was created, and no model or candidate output was accessed.

The approved M-PV3.8.4 checksum-lifecycle clarification remains intact. It permits capture authorization only after a real environment has established the required live sensor, authoritative empty-zone evidence, and fixed-slot identity conditions. The current workspace cannot establish those conditions: no target mmWave recording interface was detected, and therefore live sensor identity, raw data, timestamp, and health telemetry cannot be verified. An authoritative, time-synchronized occupancy reference and sealed-zone/access evidence are also not configured.

The result is `CAPTURE_BLOCKED`. This is a readiness result, not a failed acquisition campaign. No campaign identity or slot has been predeclared or consumed.

## Hardware and environment readiness

| Requirement | Result | Evidence / consequence |
| --- | --- | --- |
| Supported mmWave recording interface | `BLOCKED` | Read-only local interface inspection found no target mmWave serial interface. |
| Sensor serial/device identifier | `NOT_VERIFIED` | No connected target device was available for interrogation. |
| Firmware/configuration identity | `NOT_VERIFIED` | Cannot be read without the live designated device. |
| Raw sensor data | `NOT_VERIFIED` | Repository tooling does not prove a live stream. |
| Monotonic timestamps | `NOT_VERIFIED` | No live stream was available to verify timestamp fields or continuity. |
| Sensor-health telemetry | `NOT_VERIFIED` | No live stream was available to verify health, fault, dropout, or configuration fields. |
| Fixed mounting and target zone | `NOT_PREDECLARED` | Geometry and placement must be bound to the identified sensor before a campaign lock. |

The repository includes an existing serial-capture utility and historical capture protocol. Those are implementation references only; they do not establish current hardware availability or readiness and were not run.

## Empty-zone evidence readiness

Valid ABSENT evidence requires a continuous, time-synchronized, authoritative occupancy reference covering the complete target zone, plus sealed-zone/access evidence proving that no human, animal, respiration simulator, or other physiological source is present. An operator statement alone is not sufficient.

No such authoritative reference, target-zone geometry, immutable evidence receipt, or synchronization procedure was available for verification. This independently blocks capture authorization even if a sensor were connected.

## Fixed campaign structure and artifact flow

The approved design remains a fixed 3-by-3 structure: three lineage groups with three recording slots each, for nine slots total. No campaign ID, slot ID, planned recording ID, sensor identity, placement, or target-zone value has been frozen. Creating a partial `campaign_predeclaration.json` now would create an unsafe lock, so it was intentionally not created.

The authorized lifecycle after a passing preflight is:

1. Verify the live sensor, empty-zone evidence mechanism, time synchronization, and artifact generator without producing campaign evidence.
2. Freeze exactly one `campaign_predeclaration.json` containing all nine pre-capture identities.
3. Capture each fixed slot once under the 300-second uninterrupted-empty protocol.
4. Immediately bind each created recording to its planned ID with a SHA-256 post-capture receipt; do not run eligibility scanning before that receipt is locked.
5. Retain recording, occupancy/evidence, sensor-health, and rejection registries. A failed slot remains failed; no replacement, top-up, reallocation, alternate recording, or second attempt is permitted.
6. Only after a separately authorized later step may deterministic `CHRONOLOGICAL_FIRST_N_QUALIFYING_V1` scanning and membership construction be considered.

## Prerequisites that must be resolved

1. Connect the designated supported mmWave sensor and identify its active recording interface.
2. Record the sensor serial/device ID, firmware version, configuration identity, and interface settings.
3. Verify the live raw stream, monotonic timestamps, continuity, and health telemetry using a non-campaign interface check.
4. Define the rigid sensor placement and bounded target-zone geometry.
5. Configure an authorized continuous occupancy reference, sealed-zone/access procedure, immutable evidence receipt, independent review, and a resolvable clock-synchronization method.
6. Demonstrate the campaign artifact generator against a non-campaign fixture, including its ability to issue post-capture checksum receipts.
7. Repeat this preflight. Only a passing result permits the single nine-slot pre-capture identity lock.

## Validation and retained restrictions

The focused preflight validator confirms that the machine-readable result is internally consistent, preserves the M-PV3.8.4 lifecycle and all prohibitions, records a zero-slot predeclaration state, and treats the absent live prerequisites as a fail-closed `CAPTURE_BLOCKED` result.

No capture occurred. No ABSENT labels or samples were created. `D1_FINAL_SELECTION_BOTH_CLASS_V1` was not constructed. No model evaluation, candidate-output inspection, threshold change, candidate-roster change, D2 access, MR60 supervised physiology use, or M-PV4 authorization occurred.
