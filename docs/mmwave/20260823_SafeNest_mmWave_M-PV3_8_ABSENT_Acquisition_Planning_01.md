# SafeNest mmWave V2 — M-PV3.8 ABSENT Acquisition Planning

**Date:** 2026-08-23
**Scope:** Planning only; no capture, label, membership, or evaluation

## 1. Minimum campaign design

The future campaign targets 57 potential ABSENT contexts across three fixed acquisition-lineage groups (`D1_PERSON_03`, `D1_PERSON_09`, and `D1_PERSON_11`). Each group has three predeclared slots with fixed later scan quotas of 7, 6, and 6 contexts. This is nine slots total; it is not a membership and it creates no label.

Each slot records one uninterrupted 300-second empty-zone observation. Future selection, if separately authorized, uses only `CHRONOLOGICAL_FIRST_N_QUALIFYING_V1`: ascending timestamp scan, first qualifying windows only, every rejection retained, and no operator choice.

## 2. Environment and hardware conditions

The sensor is rigidly mounted. Per slot, the predeclaration must freeze sensor serial, position, height, azimuth, elevation, target-zone polygon, recording ID, and slot order. The target zone is a bounded three-dimensional area that remains empty throughout the entire capture. The sensor observation cone must also exclude people and animals that could be a target physiological source.

Allowed conditions are a controlled indoor room, static non-human background, and documented pre/post sensor-health checks. Human/animal presence, respiration simulators, moving fans or periodic mechanical reflectors, uncontrolled zone access, low-SNR or fault states, dropout, and missing input are forbidden.

## 3. Authoritative absence proof

No-human proof requires a continuous, time-synchronized, authorized target-zone occupancy reference with immutable evidence hash and independent review. No-target-physiological-source proof requires that reference together with a sealed-zone/access record showing no human, animal, respiration simulator, or other physiological source. The sensor must also provide immutable health telemetry and continuous raw-stream evidence under the governing quality contract.

An operator statement is supporting evidence only; it is authoritative only if the approved protocol explicitly names it as the continuous occupancy reference. No breathing detected, weak periodicity, model output, or sensor failure cannot be used as absence proof.

## 4. Capture and rejection protocol

The 300-second slot must continuously satisfy the empty-zone condition. Candidate contexts are 30 seconds with a five-second target. Pre/post health checks are recorded outside candidate selection. Any presence, source, health, timestamp, provenance, alignment, stale/frozen/gapped, `INPUT_UNAVAILABLE`, or uncertainty condition rejects the slot/window and is recorded. It never becomes ABSENT.

## 5. Pre-lock artifacts

Before capture, create and lock:

- `campaign_predeclaration.json`: contract/version, campaign timestamp, generator/tool version, repository SHA, fixed slot IDs, planned recording IDs, slot order, quota, scan bounds, and selection rule.
- `recording_manifest.json`: fixed placement/zone/environment conditions and later immutable recording receipt references.
- `occupancy_and_sensor_evidence_registry.json`: time-aligned occupancy, access, sensor-health, and review evidence.
- `rejection_registry.json`: every rejected slot/window, original evidence, reason, and deterministic scan order.
- `checksums.json` and `checksums.sha256`.

One implementation risk must be resolved before capture: a future recording cannot have a SHA-256 checksum before it exists. The predeclaration should lock a planned recording ID before capture; a post-capture immutable receipt should bind its checksum to that exact ID before any scan. The contract owner must explicitly approve this two-stage interpretation before the campaign begins.

## 6. Stop conditions and blockers

The campaign can proceed to a later, separately authorized deterministic scan only when all nine fixed slots have valid evidence. If any fixed slot fails, stop the campaign and retain the rejection; no replacement, top-up, reallocation, quota change, alternate recording, or second attempt is allowed.

If continuous authoritative occupancy proof cannot cover the target zone, the source is `DATA_SOURCE_INVALID_FOR_M_PV3_8`. If it can, but no capture has yet occurred, the current state remains `ABSENT_ACQUISITION_REQUIRED`.

This plan does not authorize membership construction, M-PV3.8 evaluation, candidate-output access, or M-PV4.
