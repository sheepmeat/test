# SafeNest mmWave V2 — M-PV3.8 ABSENT Membership Acquisition Contract Independent Audit

- Phase: **Independent validation audit — M-PV3.8 ABSENT membership acquisition contract**
- Base: `origin/main` after `#140` (`394dda8`), including merged `#135`–`#139`
- Audited artifacts:
  - `docs/mmwave/20260823_SafeNest_mmWave_M-PV3_8_ABSENT_Membership_Acquisition_Gate_01.md`
  - `config/mmwave/m_pv38_absent_membership_acquisition_gate.json`
  - `datasets/mmwave/manifests/M-PV3_8_absent_membership_acquisition_gate/`
  - Cross-read only: `docs/mmwave/20260823_SafeNest_mmWave_M-PV3_8_Minimal_Selection_Readiness_Gate_01.md` and the blocked final-selection evaluation for frozen-guard context
- Gate: **audit only. no sample creation. no contract edit. no threshold change. no model selection. no evaluation run. no D2. no MR60 supervised physiology.**

This document does not authorize membership construction, M-PV3.8 final selection execution, `M-PV3.8-RR-ONE`, or M-PV4.

---

## Decision

`NEEDS_CORRECTION`

The proposed acquisition contract is not yet sufficiently rigorous to create a valid final evaluation membership. Membership construction must remain blocked until the findings below are corrected in the acquisition contract and lock schema.

## Blocking Findings

1. **ABSENT class semantics remain under-specified for final membership.**  
   Eligible ABSENT is defined as `BREATHING_REFERENCE_ABSENT` confirmed by an “intentional non-breathing interval.” That wording can admit human-present apnea-proxy / breath-hold intervals, or other “no breathing detected” states, into the final ABSENT class. The contract does not hard-require a valid sensor observation with **no human present / no target physiological source**, and does not explicitly forbid converting human-present non-detection, low SNR, radar failure, missing input, sensor dropout, or ambiguous presence into ABSENT. Failed respiration estimation, poor quality, and `INPUT_UNAVAILABLE` are partially covered, but presence-versus-absence contamination remains open.

2. **Final lock omits mandatory immutability fields.**  
   Before evaluation, the lock must freeze window IDs, class-assignment reason, creation timestamp, and software/data provenance. The current `required_row_fields` / `final_lock_requirements` include recording IDs, subject IDs, label mapping, reviewer decision, and checksums, but do **not** require:
   - `window_id` (or an equivalent immutable window identifier distinct from only time bounds)
   - `class_assignment_reason` coded for every accepted ABSENT row
   - membership `creation_timestamp`
   - software provenance (contract ID/version, generator tooling version, and repository commit SHA used to build the lock)

3. **Within-recording context selection still allows easy-negative cherry-picking.**  
   The campaign fixes subject quotas and a 7/6/6 recording allocation, but it does not predeclare a deterministic window schedule (for example chronological first-N, seeded random draw, or exhaustive accept-until-quota over all qualifying intervals). Operators can still choose only the easiest qualifying negatives inside a recording before lock, then freeze that membership.

4. **Failed-recording replacement wording creates a campaign loophole.**  
   The markdown says a failed recording is rejected, not replaced. The machine-readable rule says a failed recording is “rejected rather than replaced **after the campaign closes**,” which can be read to allow replacement or reallocation while the campaign is still open. One bounded membership construction requires an unambiguous no-replacement / no-reallocation rule for the entire campaign, not only after close.

5. **Leakage controls omit preprocessing statistics and cached derived artifacts.**  
   Subject/recording/window disjointness is stated, but the acquisition lock does not forbid fitting or refreshing preprocessing statistics, caches, or derived window artifacts on final-membership ABSENT recordings before lock. Without that prohibition, the held-out membership can cease to be genuinely held-out even when subject IDs look disjoint.

## Non-blocking observations

- Ambiguity handling is directionally correct: `AMBIGUOUS` remains in provenance/registry, is excluded from pure-class counts/metrics, and must not be relabeled.
- One-shot campaign stop, D2 forbid, MR60 supervised physiology forbid, and “no candidate output before lock” are correctly retained.
- Frozen Family B/C × seeds 11/23/47 guards, Class A safety, and `M-PV3.8-RR-ONE` limits live in the already-defined readiness gate; this acquisition contract does not itself reopen ranking, Pareto selection, threshold relaxation, or post-hoc seed choice. Those rules are preserved by non-interference, provided the blocking acquisition defects above are fixed first.

## Required outcome

Do not construct `D1_FINAL_SELECTION_BOTH_CLASS_V1` from this contract as written. Correct the blocking findings, then re-audit the acquisition contract before any ABSENT membership construction or M-PV3.8 candidate-output access.

**M-PV4 remains unauthorized.**
