# SafeNest mmWave V2 — M-PV3.8 ABSENT Membership Acquisition Contract Independent Re-Audit

- Phase: **Independent validation re-audit — corrected M-PV3.8 ABSENT membership acquisition contract**
- Base: `origin/main` after `#142` (`c900205`)
- Prior audit: `#141` / `20260823_SafeNest_mmWave_M-PV3_8_ABSENT_Membership_Acquisition_Contract_Independent_Audit_01.md` (`NEEDS_CORRECTION`)
- Audited corrective artifacts:
  - `docs/mmwave/20260823_SafeNest_mmWave_M-PV3_8_ABSENT_Membership_Contract_Corrective_Revision_01.md`
  - `config/mmwave/m_pv38_absent_membership_acquisition_gate.json` (`M-PV3.8.3_CORRECTIVE`)
  - `datasets/mmwave/manifests/M-PV3_8_absent_membership_acquisition_gate/`
- Gate: **audit only. no sample creation. no membership construction. no evaluation. no candidate inspection. no threshold change. no M-PV4 authorization.**

This document does not construct `D1_FINAL_SELECTION_BOTH_CLASS_V1`, does not open candidate outputs, and does not authorize M-PV4.

---

## Decision

`APPROVED`

The corrected acquisition contract resolves all five prior blocking findings with sufficient rigor for a valid final-evaluation membership definition. Membership construction remains a separately authorized later step; this re-audit only clears the contract defect gate.

## Blocking Findings

No blocking findings.

## Prior Finding Closure

| Prior finding | Corrective resolution verified |
|---|---|
| ABSENT class semantics under-specified | ABSENT now requires no human target, no target physiological source, valid sensor observation, and intended negative-class status. Breath-hold, apnea-proxy, non-detection, low SNR, sensor failure, `INPUT_UNAVAILABLE`, and ambiguous presence are forbidden. Accepted windows use `subject_id=NO_HUMAN_TARGET` with an explicit reason code. |
| Final lock missing immutability fields | Lock schema requires `window_id`, `class_assignment_reason`, `creation_timestamp`, `generator_tool_version`, `repository_commit_sha`, and membership checksum, plus preprocessing-artifact identifiers. |
| Within-recording easy-negative selection | Selection rule `CHRONOLOGICAL_FIRST_N_QUALIFYING_V1` is predeclared; manual operator selection is forbidden; rejected candidates remain in the registry. |
| Failed-recording replacement loophole | Replacement, top-up, reallocation, alternate recording, and second attempt are forbidden for the entire campaign after predeclaration lock. |
| Preprocessing / cache leakage | Fitting, normalization refresh, cache regeneration, derived-artifact creation, and feature-extraction changes using final-membership data are forbidden; only previously authorized training artifacts may supply preprocessing parameters. |

## Scope limits retained

- No ABSENT samples created
- No membership constructed or locked
- No model evaluation performed
- No threshold or candidate-roster change
- D2 access and MR60 supervised physiology remain forbidden
- **M-PV4 remains unauthorized**
