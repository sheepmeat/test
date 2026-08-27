# SafeNest mmWave V2 — M-PROT-5A Test-Repo Predeployment Closure

- Phase: **M-PROT-5A**
- Date: 2026-08-27
- Base SHA (`origin/main` after `#179`): `8945e5912a00f9fc177408d7993126431c1a958c`
- Branch: `research/mmwave-m-prot-5a-test-repo-predeployment-closure`
- Worker terminal target: **`M_PROT_5A_TEST_REPO_PREDEPLOYMENT_COMPLETE`**
- Sol exact-head review: **REQUIRED** (do not merge without Sol)
- Manifest: `datasets/mmwave/manifests/M_PROT_5A_predeployment_closure/`

## Purpose

Finish everything that can and should be completed inside `sheepmeat/test` **before** touching the team repository or Raspberry Pi.

This is **not** live Pi / MR60 validation and **not** team-repo integration.

## Split (owner override)

| Slice | Status | Scope |
|---|---|---|
| M-PROT-5A | **ACTIVE** | Test-repo predeployment closure |
| M-PROT-5B | DEFERRED | Team-repo Pi runtime port |
| M-PROT-5C | DEFERRED | Live Pi + MR60 smoke |

```text
LIVE_HARDWARE_EXECUTED = NO
TEAM_REPO_MODIFIED = NO
PI_DEPLOYMENT = DEFERRED
```

## Corrected current pointer

| Item | Value |
|---|---|
| M-PROT-4 | COMPLETE / MERGED / PASS_WITH_LIMITATIONS |
| PR `#179` | MERGED |
| merge / main | `8945e5912a00f9fc177408d7993126431c1a958c` |
| M-PROT-5A | AUTHORIZED / ACTIVE / TEST_REPO_PREDEPLOYMENT_CLOSURE |
| M-PROT-5B | DEFERRED / TEAM_REPO_NOT_YET_INSPECTED_FOR_PORT |
| M-PROT-5C | DEFERRED / LIVE_HARDWARE_NOT_EXECUTED |

Stale AGENTS wording `M-PROT-4_IMPLEMENTED_PENDING_SOL_REVIEW` is corrected in the current overlay only. Historical M-PROT-2/3/4 evidence files are not rewritten.

## Portable deployment handoff

Schema: `M_PROT_5A_PREDEPLOYMENT_HANDOFF_V1`

Machine-readable: `datasets/mmwave/manifests/M_PROT_5A_predeployment_closure/predeployment_handoff.json`

Builder/verifier: `scripts/mmwave/build_m_prot_5a_deployment_bundle.py`

Stages only `RUNTIME_REQUIRED` / `MODEL_REQUIRED` / `CONFIG_REQUIRED` files into a temporary bundle (not committed), verifies B23 + TRAIN scaler identities, rejects absolute-path leakage, and records SHA-256 checksums.

Symbolic destinations (until M-PROT-5B inspects the team repo):

- `PI_RUNTIME_MMWAVE_MODULE`
- `PI_RUNTIME_MODEL_DIR`
- `PI_RUNTIME_CONFIG_DIR`

## Frozen identities (unchanged)

| Asset | Path / value |
|---|---|
| B23 artifact | `models/mmwave/m_pv2/family_b/candidate_seed_23.pt` |
| Artifact SHA-256 | `8f7de6f50d6ff62ff9b0ebfaed0b1fccd8d194c7e33781bc5b93366fae251a2c` |
| Canonical parameter SHA | `6db949c242e25888dd20c3fc8e2305af03448aa229e3ca73e4159216a266d78e` |
| Scaler | `datasets/mmwave/manifests/M-PV2_candidate_training/scaler_statistics.json` |
| Scaler content SHA | `5a2583b5b5064be5480b0cf56f2a2c12d40a4a2d005eb087dc8e12106881159c` |

No model replacement, scaler refit, TFLite, INT8, or threshold tuning.

## Future team-repo input bridge (semantic only)

Required: phase/waveform-like sample + monotonic timestamp.

Preferred: sequence, session identity, reset indication.

Source identity: device / interface / configuration / observation kind.

Presence: explicit defensible presence source when available.

**Vendor scalar RR alone is NOT a B23 model input.**

Transport field names are **not** frozen in 5A.

## Future SafeNest output contract

status/availability · window_ready · breathing state/score · RR bpm or unavailable · quality state/score · fail_closed_code · model identity · timestamp/update identity.

Team UI/backend mapping is deferred to M-PROT-5B.

## Future team-repo handoff note

The next integration agent must **first** inspect the latest:

https://github.com/jinsu1011/safenest-embedded-competition

Locate the **current** Pi-side runtime subtree (do not assume old folder names).

Intended model:

```text
team Pi subtree → placed/cloned on Raspberry Pi → runtime inside that subtree executed
```

Integrate the frozen mmWave deployment bundle/interface into that subtree. Do **not** deploy `sheepmeat/test` wholesale.

`yuname121/integration` is historical evidence only — not the authoritative final target for this phase.

The team repository is **not** modified in M-PROT-5A.

## Predeployment self-test

Deterministic fixture → SW-01 → M-PROT-3 → R1/R2 → B23 → prototype outputs / fail-closed receipt (via existing M-PROT-4 harness). No hardware claim.

## Track F unchanged

```text
D1 57/0 BLOCKED_INVALID_FINAL_MEMBERSHIP
M-PV3.8 RESOURCE_BLOCKED_CLOSED
M-PV4 UNAUTHORIZED
D2 LOCKED
```

## Next

Sol exact-head review of this PR. Do not merge without Sol.

Recommended next phase after merge: **`M-PROT-5B_TEAM_REPO_PI_RUNTIME_PORT`**.
