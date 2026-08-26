# SafeNest mmWave V2 — D1 Physical Resource Recovery & Live Preflight Readiness Audit

- Phase: **MMWAVE-V2-D1-RESREC-01**
- Date: 2026-08-27
- Base SHA (post-PR #169 `origin/main`): `d0a6bdb86e5cc9dd8b81fbd0652169861866dc17`
- Branch: `audit/mmwave-v2-d1-resource-recovery-01`
- Mode: **RESOURCE / READINESS only** — not capture, not D1 membership, not model evaluation
- Resource-recovery verdict: **`RESREC_PARTIAL_RECOVERY`**
- Next recommendation: **`RECOMMEND_RESOURCE_ACQUISITION_OR_OWNER_ACTION`**
- Live preflight ready: **NO**
- Manifest: `datasets/mmwave/manifests/MMWAVE_V2_D1_physical_resource_recovery_01/`

---

## PR #169 merge receipt

| Field | Value |
|---|---|
| PR | https://github.com/sheepmeat/test/pull/169 |
| Reviewed head | `69e8cea185947a4aa168d1ab253369ab4058fa9a` — exact match |
| Reviewed base | `d7f2421808a79e75afccb8f08b3a29c0f5a1f1fa` (`main`) |
| State / mergeable at merge | OPEN / true |
| `PR169_MERGE_COMMIT` | `d0a6bdb86e5cc9dd8b81fbd0652169861866dc17` |
| `POST_R0_ORIGIN_MAIN` | `d0a6bdb86e5cc9dd8b81fbd0652169861866dc17` |

---

## Frozen acquisition contract (unchanged)

| Field | Value |
|---|---|
| Plan ID | `MMWAVE_V2_M_PV38_ABSENT_ACQUISITION_PLAN_V1` |
| Plan SHA-256 | `797cb281b1d7be9ba3946e34fa0b824df44b44dc436474d63b4d4d472f87c18a` |
| Path | `datasets/mmwave/manifests/M-PV3_8_absent_acquisition_planning/acquisition_plan.json` |
| Structure | 3 lineage × 3 slots; quotas → **57** ABSENT; `CHRONOLOGICAL_FIRST_N_QUALIFYING_V1` |
| Preflight contract | `MMWAVE_V2_M_PV38_ABSENT_CAPTURE_PREFLIGHT_V1` |
| Frozen preflight result | **`CAPTURE_BLOCKED`** (vocabulary `CAPTURE_READY` is **not** defined in-repo) |
| Lifecycle | `RESOURCE_BLOCKED_CLOSED` / `ACQUISITION_REQUIRES_RESOURCE_ACCESS` |

This audit **did not** shrink 57, change quotas/lineages/slots, allow replacement/top-up/retry, or relax occupancy/interface requirements.

**ID note:** checklist-local `B-01..B-04` ≠ post-PUBABS must-have `B-01..B-07`. This audit uses **post-PUBABS B-01..B-07**.

---

## Resource matrix (must-haves)

| ID | Requirement | Status | Blocking? | Action |
|---|---|---|---|---|
| B-01 | mmWave raw/timestamp/health interface | `INACCESSIBLE_FROM_THIS_ENVIRONMENT` | YES | Provide designated sensor UART/path; run SW-01 live |
| B-02 | rigid mount + measured zone | `NOT_EVIDENCED` | YES | Measured placement/zone evidence |
| B-03 | occupancy + sealed-zone proof | `NOT_EVIDENCED` | YES | Approve & configure EV-01..04 mechanism |
| B-04 | host storage + clock | Audit host `AVAILABLE_VERIFIED`; designated capture host `NOT_EVIDENCED` | YES | Identify capture host (e.g. Pi) |
| B-05 | non-campaign interface checker | `TOOLING_DEFINED_LIVE_CHECK_MISSING` | YES | Implement/run SW-01 when B-01 reachable |
| B-06 | nine-slot + SHA tooling demo | `AVAILABLE_VERIFIED_FIXTURE_ONLY` | YES* | Fixture done; real campaign lock only after Sol capture auth |
| B-07 | PP-01..PP-04 assigned | `BLOCKED_OWNER_OR_ACCESS` | YES | Owner assign roles |

\*B-06 fixture progress does **not** clear campaign readiness.

---

## Live vs repo-only evidence

| Area | Evidence class |
|---|---|
| Plan / gate / checklist / preflight / lifecycle | Repo canonical hashes verified |
| Serial / UART inventory | Live non-destructive; **no** target mmWave port |
| `MMWaveSensorAdapter.connect()` | Live fail-closed: `HardwareBackendUnavailable` |
| Occupancy / mount geometry | Repo requirements only; **not** measured live |
| Audit Mac host disk/clock/hash | Live verified |
| SW-01 live checker | **Absent**; artifact validator = `COMPONENT_CHECK_ONLY` |
| Stage1/Stage2 | **Fixture-only** under `.../fixtures/` (`REAL_SLOT_CONSUMED=NO`) |

---

## Preflight

```text
PREFLIGHT_PREREQUISITES_COMPLETE = NO
PREFLIGHT_EXECUTED               = NO
PREFLIGHT_RESULT                 = CAPTURE_BLOCKED  (frozen; unchanged)
```

A full frozen live preflight was **not** re-run as PASS. Only the artifact validator for the existing `CAPTURE_BLOCKED` record was executed (`exit 0`).

**Preflight pass would still not authorize 57-session capture** without separate Sol authorization.

---

## D1 / lifecycle (unchanged)

```text
D1 PRESENT = 57
D1 ABSENT  = 0
D1 MEMBERSHIP = BLOCKED_INVALID_FINAL_MEMBERSHIP
MODEL_READY_WORK = NO
M-PV3.8 = RESOURCE_BLOCKED_CLOSED
M-PV3.8 EVALUATION = NOT_EXECUTED
M-PV4 = UNAUTHORIZED
D2 = LOCKED
```

Governed ABSENT capture, D1 membership build, ROLE_L inference/training/selection, public-data discovery, C1 reopen, PUBABS-A10: **NOT_EXECUTED / NOT_CREATED**.

---

## Verdict

**`RESREC_PARTIAL_RECOVERY`** — contracts recovered; audit-host clock/storage evidenced; Stage1/Stage2 **fixture** demo executed; live sensor/mount/occupancy/roles/SW-01 and designated capture host remain blocking.

**`RECOMMEND_RESOURCE_ACQUISITION_OR_OWNER_ACTION`**

Not `LIVE_PREFLIGHT_READY`. Not capture-authorized.
