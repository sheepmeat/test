# Thermal T-A2 — Geometry, Calibration, and Canonical Frame Contract

Date: 2026-08-10

Phase: `T-A2`

Outcome: `PASS_WITH_LIMITATIONS`

T-A3 authorized: `YES`

## Decision

The selected software canonical profile is `G1_FIXED_ASPECT_CROP_BILINEAR`: preserve SDT orientation as stored, crop the fixed source rectangle `(left=10, top=0, right=630, bottom=480)`, and apply deterministic custom NumPy bilinear downsampling to `(62,80)`. The canonical physical unit is Celsius and the canonical dtype is float32. No model score, model inference, normalization, or SafeNest label remapping was used.

## Geometry boundary

The verified SDT distributed frame is `(480,640)` and already contains the authors' bilinear enlargement from the FLIR Lepton 3.5 native `(120,160)` grid. T-A2 does not reverse that operation or claim a restored native frame. Thermal-44 physical orientation and packet ordering remain `UNVERIFIED / DEFERRED_T_C`.

The predeclared candidate set contains 3 fixed geometry policies (direct stretch, fixed aspect crop, masked aspect pad) crossed with nearest, bilinear, and exact area interpolation. The ranking rule was fixed before candidate measurements: preserve semantics and source orientation, preserve physical values, minimize artificial content, minimize unacceptable FOV loss, minimize distortion, then favor stable/simple deterministic implementation and the fixed software grid.

The selected crop retains `[10, 0, 630, 480]` and `96.875%` of source area. Direct stretch retains full FOV but has higher anisotropy; pad retains FOV by introducing masked invalid rows. The fixed crop has no synthetic pixels and reduces aspect anisotropy.

## Physical calibration

SDT Celsius conversion remains `(encoded_uint16 - 27315) / 100`. Ambient/reference compensation and hardware-specific calibration are not applied because no verified parameter source exists. Float32 was selected after comparison with float64 reference conversion: maximum measured conversion error `1.83105469e-06 °C`, below the source `0.01 °C` encoded resolution.

## Invalid pixels and provenance

T-A1's no-sentinel policy is inherited. NaN/Inf or a supplied partial invalid source mask fails closed; no neighbor, mean-temperature, zero, ambient, or other synthetic value is inserted. The selected crop has an all-true validity mask. Every pilot record retains the original encoded source hash and exact source member/frame index separately from the canonical frame hash.

## Pilot and visual check

The bounded real-data pilot uses 12 evenly spaced sorted source indices per original pose class (48 total), with all four classes represented. Repeated canonicalization is byte-stable. Coordinate traces and asymmetric synthetic fixtures show row/column order preserved with no transpose, rotation, or flip. The tracked visual is a colorized human diagnostic only and is not radiometric model input.

## Deferred boundaries

T-A2 does not create temporal windows, SafeNest fall labels, grouping/splits, full canonical conversion, model comparisons, or Thermal-44 hardware claims. Train/validation split placeholders remain unhydrated.
