# SafeNest mmWave V2 — M-PV3.8 ABSENT Acquisition Planning Result Report

**Date:** 2026-08-23
**Result type:** Planning result only
**Gate:** `PASS_WITH_LIMITATIONS`
**Current status:** `ABSENT_ACQUISITION_REQUIRED`

## 1. Result

The future ABSENT acquisition campaign is planned, but it has not started. The plan preserves the M-PV3.8.3 corrective boundaries: no existing D1 row is relabeled, no AMBIGUOUS evidence is reused, and no model, candidate output, threshold, membership, or M-PV4 decision is touched.

The plan defines a fixed 57-context target through three acquisition-lineage groups and three fixed recording slots per group. Future deterministic scan quotas are 7/6/6 per group, and the only permitted selection rule is `CHRONOLOGICAL_FIRST_N_QUALIFYING_V1`.

## 2. Evidence and environment requirements

Each future slot requires a rigidly mounted sensor, a predeclared bounded target zone, a 300-second uninterrupted empty-zone observation, continuous authoritative occupancy evidence, sealed-zone/access evidence, sensor-health telemetry, and immutable time-aligned provenance. Human/animal presence, physiological sources, periodic mechanical reflectors, low-SNR/fault states, missing input, and `INPUT_UNAVAILABLE` make a slot or window ineligible.

The occupancy mechanism must establish both no human target and no target physiological source. An operator statement is only supporting evidence unless the approved protocol explicitly makes it the authoritative continuous occupancy reference.

## 3. Construction controls

Before capture, the campaign must lock its slot IDs, planned recording IDs, recording order, scan bounds, quotas, placement, target-zone definition, selection rule, tool version, and repository SHA. Rejections must be retained in deterministic order.

After the predeclaration lock, there is no replacement, top-up, reallocation, alternate recording, quota change, or second attempt. A failed slot ends the bounded campaign rather than opening a retry loop.

## 4. Limitation and blocker

A future recording has no SHA-256 before capture, while the current acquisition contract lists recording checksums among predeclared fields. Before capture is authorized, the contract owner must explicitly accept the following interpretation:

1. Lock a planned recording ID and slot identity before capture.
2. Immediately after capture, create an immutable receipt that binds the resulting recording SHA-256 to that predeclared ID.
3. Do not run an eligibility scan or make any membership decision until the receipt is locked.

Without that clarification, the campaign cannot satisfy the contract literally.

## 5. Completion accounting

| Item | Result |
|---|---|
| Capture performed | No |
| ABSENT labels created | No |
| Membership constructed | No |
| Model evaluation / candidate-output access | No |
| M-PV4 authorized | No |

## 6. Next step

Obtain explicit approval of the checksum-receipt interpretation, then separately authorize the one bounded capture campaign. Until then, the correct status remains `ABSENT_ACQUISITION_REQUIRED`.
