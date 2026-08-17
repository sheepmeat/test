# Agent handoff — T-B5 provision + Git tracking policy

For the next agent. Do not treat this as T-C validation or RP-A2 authorization.

## What was done (2026-08-17)

### Item 3 — Pi provision

- SSD mount: `/Volumes/SafeNestssd`
- Source: `SafeNestAI/thermal/experiments/T-B4/T-B4_execution_result/artifacts/SMALL_CNN_BASELINE_V1_P1_full_int8.tflite`
- Copied to Pi `sandi@192.168.137.249:/home/sandi/integration/sources/ondevice_ai/models/rp_x0_b_complete/thermal/SMALL_CNN_BASELINE_V1_P1_full_int8.tflite`
- SHA-256 matched `fa9730c29535477a3994c11e664474a0ca0116afaaa172889f47446ab2ac46be`
- Size 318280
- Isolated LiteRT load/invoke PASS: input `[1,62,80,1] int8`, output `[1,3] int8`
- `TB5Runtime.missing = False`
- Live UDP `:5005` was not injected. Production `model_manifest.json` was not switched.
- Live MI48 uint16 vs P1 Celsius unit is still **UNVERIFIED**. Do not claim HUMAN_FALL from live NPZ.

Pi git freeze remains `1ffbc7d` on `diagnostic/rp-x0-b-runtime-wiring`. The `.tflite` on Pi is a working-tree provision, not a reason to merge RP-A1.

### Policy amendment (this repo)

T-B5 historically stored binaries on SSD only. CO2/mmWave B files were already in Git. Thermal B was the gap.

New Git copies:

```text
models/thermal/candidates/t_b5/SMALL_CNN_BASELINE_V1_P1_full_int8.tflite
models/thermal/candidates/t_b5/SMALL_CNN_BASELINE_V1_P1_float32.tflite
models/thermal/candidates/t_b5/identity.json
models/thermal/candidates/t_b5/SHA256SUMS
docs/20260817_Locked_B_Binaries_Git_Tracking_Policy_01.md
.cursor/rules/locked-b-binaries.mdc
```

Branch: `policy/git-track-locked-b-binaries` from `origin/main`.

## Do next / do not

Do:

- `git pull` this branch (or merge after review) so teammates get the TFLite without the SSD.
- SHA-check before any T-B5 invoke.
- Keep mmWave live B gate CLOSED until real `breath_phase` exists (RP-X0 item 1).
- Keep C-B6 fail-closed until ESP flash sends `boot_id` + event ids (RP-X0 item 2). Item 2 is ESP flash, not Pi ID invention.

Do not:

- Substitute v0.1.0 thermal.
- Claim `thermal44_deployment_validated`.
- Implement RP-A2 or merge RP-A1 as part of this policy.
- Inject synthetic TCP `:9000` / UDP `:5005` into the live Pi.
- `git add data/` on the Pi.

## RP-X0 remaining gaps

| Item | Owner | Status |
|---|---|---|
| 1 `breath_phase` | ESP (+ Pi persist nested `mmwave`) | NOT DONE |
| 2 CO2 physical-event | ESP flash of `display-test2` ino | NOT DONE (Pi parser already ready) |
| 3 T-B5 bytes | SSD → Pi + Git | DONE this turn |
| Live thermal unit/layout | T-C | UNVERIFIED |
