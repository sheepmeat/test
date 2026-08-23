# SafeNest mmWave V2 — M-PV3.8 ABSENT Acquisition Contract Checksum Lifecycle Clarification

**Date:** 2026-08-23
**Contract clarification:** `M-PV3.8.4_CHECKSUM_LIFECYCLE_CLARIFICATION`
**Status:** `READY_FOR_CAPTURE_AUTHORIZATION`

## 1. Decision

The checksum lifecycle ambiguity is resolved through a two-stage recording identity model. The clarification changes neither ABSENT semantics nor any no-replacement, deterministic-selection, leakage-prevention, candidate, threshold, D2, MR60, or M-PV4 restriction.

This is contract clarification only. No recording was captured, no ABSENT sample or membership was created, no evaluation ran, and no candidate output was accessed.

## 2. Stage 1 — pre-capture identity lock

Before capture, `campaign_predeclaration.json` must immutably freeze the campaign ID, slot ID, planned recording ID, lineage group, recording order, sensor identity, placement, target zone, selection-rule version, contract version, repository SHA, and creation timestamp.

A SHA-256 is explicitly `NOT_APPLICABLE_BEFORE_CAPTURE`: the file does not yet exist. The planned identity cannot be changed, replaced, or reallocated after this lock.

## 3. Stage 2 — post-capture immutable checksum receipt

Immediately after each capture, `post_capture_checksum_receipts.json` must immutably bind exactly one actual recording to exactly one predeclared planned recording ID. Each receipt requires the planned recording ID, actual recording identifier, SHA-256, file metadata, capture timestamp, source provenance, and generator/tool version.

The receipt must be locked before any eligibility scan. A missing receipt, duplicate binding, mismatch, or checksum failure fails the fixed slot; it does not permit replacement, top-up, reallocation, or a second attempt.

## 4. Final-lock integration

The final membership lock must include the post-capture receipt artifact and its checksum, alongside the existing membership metadata, window identifiers, ABSENT evidence, ambiguity/rejection registry, deterministic order, and training-only preprocessing provenance.

The final-membership data remains unseen by preprocessing fitting, normalization refresh, cache generation, derived feature generation, and feature-extraction changes.

## 5. Validation result

The machine-readable contract, lock schema, acquisition plan, and planning result consistently require the two-stage lifecycle. JSON syntax, SHA-256 checks, lifecycle consistency assertions, and diff checks passed.

**READY_FOR_CAPTURE_AUTHORIZATION** means that a separate authority may authorize the one bounded capture campaign. It does not itself authorize capture execution, membership construction, model evaluation, or M-PV4.
