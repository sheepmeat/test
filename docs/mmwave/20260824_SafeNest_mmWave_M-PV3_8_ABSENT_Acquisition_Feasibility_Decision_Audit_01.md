# SafeNest mmWave V2 — M-PV3.8 ABSENT Acquisition Feasibility Decision Audit 01

Date: 2026-08-24

Phase: `M-PV3.8`

Decision: `ACQUISITION_REQUIRES_RESOURCE_ACCESS`

## Decision

The M-PV3.8 ABSENT acquisition campaign is technically plausible and remains bounded by its approved contract, but it is not executable in the current setup. The correct feasibility decision is `ACQUISITION_REQUIRES_RESOURCE_ACCESS`, rather than `ACQUISITION_FEASIBLE` or `ACQUISITION_NOT_FEASIBLE_WITH_CURRENT_SETUP`.

This distinction is material. The current block stems from missing hardware and evidence resources, not from a contradiction in the ABSENT semantic definition, checksum lifecycle, deterministic-selection rule, or no-replacement rule. The audit grants no capture authorization: every listed resource must be available and independently verified through a later preflight.

## Hardware feasibility

| Requirement | Current state | Minimum resource required |
| --- | --- | --- |
| Supported mmWave device | No target live interface detected | A designated supported sensor assigned to the campaign. |
| Recording interface and raw data | Tooling exists, but no live stream was verified | Approved device/host interface and a non-campaign connectivity check. |
| Device identity | No sensor was available to interrogate | Recorded serial/device ID, firmware version, configuration identity or hash, and interface settings. |
| Timestamps and health telemetry | Not observed | Live monotonic timestamps plus continuity, fault/dropout, and health/configuration telemetry. |

Hardware readiness is therefore not demonstrated. It is reasonably attainable only after the responsible team provides physical access to a compatible device and its recording interface. Repository tooling alone is not evidence of device availability.

## Evidence feasibility

Authoritative ABSENT proof cannot be based on radar non-detection, weak periodicity, or an operator assertion. It requires an independent, continuous, time-synchronized occupancy reference covering the complete target zone, coupled with a sealed-zone/access record that proves no human, animal, respiration simulator, or other physiological source is present.

The minimum evidence chain is:

1. An authorized occupancy-reference system with immutable evidence hashing and independent review.
2. A measured, fixed target zone and an access-control/sealed-zone procedure covering every 300-second capture.
3. Shared-clock evidence or explicit synchronization markers with a recorded alignment method.
4. Immediate post-capture SHA-256 receipts that bind each actual recording to exactly one predeclared identity.

No approved occupancy-reference mechanism, synchronization procedure, or evidence receipt was available in the current setup. This independently prevents capture even if the mmWave sensor becomes available.

## Minimum resource package

The campaign needs one supported sensor with stable power and raw/telemetry access; a continuous authorized occupancy-reference system; rigid mounting and target-zone measurement; and a host for immutable raw recordings. It also needs a sensor custodian, a capture operator, and an independent evidence reviewer.

The environment must be a controlled indoor room with controlled access, a static non-human background, no animal or physiological source, no periodic mechanical reflector, and a continuous 300-second empty interval for each fixed slot. Software must provide a non-campaign device check, time-synchronization and evidence-hashing support, and governed generators for the pre-capture lock, immediate checksum receipts, and required registries.

## Preconditions before the campaign can be authorized

Before a `campaign_predeclaration.json` may be created, all minimum resources must be physically available and verified; the non-campaign interface and evidence-tooling check must pass; the occupancy reference, target-zone geometry, access-control procedure, and clock synchronization must be approved; and complete immutable identities for all nine fixed slots must be known.

Only then may a later preflight decide whether to authorize a single bounded campaign. The approved three lineage groups, fixed nine slots, ABSENT semantics, checksum lifecycle, no-replacement rule, and `CHRONOLOGICAL_FIRST_N_QUALIFYING_V1` selection rule remain unchanged.

## Scope confirmation

No campaign predeclaration was created. No capture occurred. No ABSENT label or membership was created, no model was evaluated, and no M-PV3.8 requirement or M-PV4 restriction was changed.
