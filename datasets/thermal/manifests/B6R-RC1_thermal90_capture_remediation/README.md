# B6R-RC1 Thermal-90 capture remediation evidence

This directory records the standalone validation result for the non-gating
`B6R-RC1` plan. The normative contract is
`config/thermal/b6r_rc1_thermal90_capture_remediation_contract.json` and the
human execution plan is
`docs/thermal/20260827_SafeNest_Thermal_B6R_RC1_Thermal90_Capture_Remediation_Plan_KO_01.md`.

No sensor frame, participant capture, model, split, or locked-test payload is
stored here. A `PASS` result means only that the remediation plan preserves its
fail-closed identity, acquisition, label, and holdout invariants.

`checksums.sha256` hashes UTF-8 text after CRLF-to-LF normalization. This keeps
the evidence identity stable across Git checkouts with different line-ending
settings; it is not a license to normalize raw sensor payloads.
