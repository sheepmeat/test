# SafeNest Active Workspace Instructions

## Canonical project root

- The directory containing this `AGENTS.md` file is the only active SafeNest development root.
- Active code, configuration, datasets, models, tests, manifests, and reports live directly under this root.
- Do not create or use `SafeNest_V4_*`, `SafeNest_V5_*`, `SafeNest_V6/`, or `ondevice_ai/` as alternate active roots.
- Version names belong in model metadata, release tags, reports, and archived snapshot names, not around the active source tree.

## Archive boundary

- `archive/version_snapshots/` contains read-only historical project snapshots.
- Never import code, auto-discover manifests, or resolve runtime models from `archive/`.
- Do not edit archived reports or snapshots to make them look current. Historical paths and claims are evidence of their original state.
- A historical model needed for an active comparison may remain under `models/` only when its lineage and role are explicit in `models/model_manifest.json`.

## Path and provenance rules

- Store repository-relative POSIX paths in JSON, YAML, manifests, metadata, and generated reports.
- Do not persist `/Users/...`, `file://...`, home-relative, drive-specific, or version-wrapper paths in active machine-readable artifacts.
- Runtime path resolution starts from the canonical root and must not fall back to a versioned sibling or archived snapshot.
- Every generated dataset sample must preserve source dataset, subject, session, recording, time/window, extraction profile, label mapping, split, and quality provenance when applicable.

## mmWave phase workflow

- Follow `docs/20260806_ChatGPT_SafeNest_mmWave_Execution_Sequence_01.md`.
- Complete and validate A0 through A6 before Phase B model selection.
- A4 voluntary breath-hold labels are derived SafeNest APNEA proxies and must never be described as clinical apnea.
- A5 uses subject-level grouping. All recordings and windows from one subject must remain in exactly one split.
- `AMBIGUOUS` A4 windows are excluded from pure-class training but retained for provenance and transition analysis.
- A6 must extend the approved pilot contracts to all 440 recordings and must report every failure, exclusion, and low-quality result.
- A6 annotation evidence must never fail open. An annotation read/parse failure blocks that recording and must appear in the exception registry; optional reference-sensor failures must be recorded as warnings.
- The A6 exit gate must validate semantic 1:1 correspondence among every window row, provenance row, and canonical numeric row, successful accounting for every A0 recording, and complete checksum coverage.
- Phase B must inherit the immutable A5 subject split, fit preprocessing statistics on TRAIN only, keep LOCKED_TEST unavailable to model selection, and run a near-duplicate diagnostic before comparative evaluation.

## Change and verification discipline

- Preserve user changes and existing A0-A4 artifacts.
- Generated artifacts must be deterministic for the same inputs and configuration; record checksums with repository-relative paths.
- Run the focused phase validator and upstream regression tests after each phase.
- Do not describe an A phase as complete solely because generation finished; the standalone phase validator must pass against the generated evidence.
- Mock success proves software wiring only unless the result is derived exclusively from the actual selected model prediction.
- Do not claim MR60 real-sensor validation, Raspberry Pi performance, or clinical performance without corresponding measurements.
