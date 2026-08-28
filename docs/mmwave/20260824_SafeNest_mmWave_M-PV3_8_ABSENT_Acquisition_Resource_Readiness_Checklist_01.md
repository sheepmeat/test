# SafeNest mmWave V2 — M-PV3.8 ABSENT Acquisition Resource Readiness Checklist 01

Date: 2026-08-24

Phase: `M-PV3.8`

Mode: `READINESS_REQUIREMENTS_ONLY`

## Required hardware

1. A designated supported mmWave sensor with stable power and a host-supported recording interface. Before a campaign it must yield its serial/device ID, firmware/configuration identity, raw observations, monotonic timestamps, and health telemetry.
2. A rigid mount and a measured bounded target zone. Record position, height, azimuth, elevation, and the target-zone geometry before the campaign lock.
3. An authorized independent occupancy-reference system continuously covering the full target zone.
4. A host with controlled storage for immutable raw recordings, telemetry, evidence receipts, and registries.

## Required software and tooling

1. A non-campaign device check that verifies raw observation availability, timestamps, continuity, fault/dropout handling, and health telemetry.
2. A governed generator for the complete nine-slot pre-capture identity lock and immediate post-capture SHA-256 receipts binding actual recordings to planned recording IDs.
3. Time-synchronization and evidence-hashing tooling for the sensor, occupancy reference, and access-control evidence.
4. Validated registry tooling for recording provenance, occupancy/evidence, sensor health, and rejections.

## Required evidence and proof

The evidence chain must continuously prove no human in the target zone and no animal, respiration simulator, or other physiological source. It requires a sealed-zone/access-control record, resolvable clock synchronization, immutable evidence hashes, independent review, and immediate checksum receipts after capture.

Radar non-detection, weak periodicity, no respiration detected, low SNR, sensor failure, and an operator statement alone are not valid ABSENT proof.

## Required personnel and process

- A sensor custodian provides device access and establishes sensor/firmware/configuration identity.
- A capture operator follows the fixed protocol but cannot manually choose windows or replace a failed slot.
- An independent evidence reviewer verifies the occupancy/access proof and negative-class provenance.
- A campaign authority approves the evidence mechanism, synchronization method, and one complete nine-slot lock before capture.

## Minimum setup for a future preflight pass

All hardware, tooling, evidence mechanisms, and assigned roles must be available. The controlled room must have controlled access, static non-human background, no animal or physiological source, no periodic mechanical reflector, and a 300-second uninterrupted empty interval per fixed slot. All nine slot identities must be complete before `campaign_predeclaration.json` is generated.

## Estimated blockers

| Blocker | Severity | Clear condition |
| --- | --- | --- |
| Supported device and raw/telemetry access | `HARD_BLOCKER` | A non-campaign device check verifies identity, raw data, timestamps, continuity, and health telemetry. |
| Authorized occupancy and sealed-zone evidence | `HARD_BLOCKER` | Continuous, synchronized, hashable proof covers the full target zone. |
| Artifact and synchronization tooling | `HARD_BLOCKER` | A non-campaign fixture demonstrates registries, time alignment, and one-to-one receipt binding. |
| Any failed future fixed slot | `CAMPAIGN_STOP_CONDITION` | No recovery path exists: replacement, top-up, reallocation, alternate recording, and second attempt are forbidden. |

No duration estimate is responsible until the equipment custodian, evidence authority, and controlled room are available. This checklist changes no M-PV3.8 requirement and does not authorize capture, membership construction, model evaluation, or M-PV4.
