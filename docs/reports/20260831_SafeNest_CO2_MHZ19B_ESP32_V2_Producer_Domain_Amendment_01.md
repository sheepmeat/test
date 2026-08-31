# SafeNest CO₂ — MH-Z19B ESP32 v2 producer domain amendment

- Document version: `01`
- Date: `2026-08-31`
- Scope: protocol / capture-contract amendment only
- Does **not** start C-C2, retrain C-B6, change threshold 0.43, rewrite the scaler, or edit `archive/`

## Why this file exists

Team firmware PR:

```text
https://github.com/jinsu1011/safenest-embedded-competition/pull/68
branch: feature/esp32-mhz19b-co2-v2-port
firmware: safenest-esp32-sensor-node/1.7.0-mhz19b.1
sketch: ESP32/Arduino/esp32_sensor_node_mhz19b_v2/
```

SCD40 is physically unavailable. The team v2 node was ported to Winsen MH-Z19B UART as a **new sketch**, not an in-place overwrite of `esp32_sensor_node_260828_v2`.

This standalone repository's C-C1 / C-C1R / C-C1T capture and operator docs still describe the producer as SCD40 `readMeasurement()` / I²C `0x62`. Leaving that unamended would make later MH-Z19B captures look like SCD40-domain evidence. They are not.

## Compatibility decision (do not reopen here)

```text
OVERALL: COMPATIBLE_ONLY_AS_NEW_DEVICE_DOMAIN
PATH B
Retrain now: NO
Threshold 0.43: unchanged
```

ppm units matching is **not** drop-in compatibility. Do not pool SCD40 and MH-Z19B metrics. Do not treat UART poll rate as physical NDIR conversion rate.

## Producer identity

| Field | MH-Z19B v2-port value |
|---|---|
| `co2_sensor_model` | `MH-Z19B` |
| `co2_event_identity_class` | `INFERRED_UART_SAMPLE` |
| `co2_measurement_event_id` | Increments at most once per declared UART poll (team default 5 s), not per 1 Hz TCP `seq` |
| `co2_measurement_monotonic_ms` | ESP `millis()` at the accepted UART sample |
| `co2_measurement_event_valid` | False during 3 min preheat, checksum/timeout/stale; then the protocol zero tuple `0/0/false` |
| `co2_preheat` | True for 180 s after boot |

Winsen manuals (v1.7, 2020-10-15) do **not** provide Sensirion `getDataReadyStatus`. Official docs do not prove each command `0x86` is a new conversion. Capture tooling that still says "verified fresh SCD40 measurement event" must not be applied to this producer without renaming the event class.

Existing C-C1T required payload fields remain valid and are a subset:

```text
co2_measurement_event_id
co2_measurement_monotonic_ms
co2_measurement_event_valid
```

The new keys above are additive. They must be retained when present. A validator must not invent SCD40 conversion semantics from them.

`device_type=MH-Z19B` is allowed only as a **new device domain** label. It does not authorize C-C2 under the SCD40 protocol, and it does not relax ENDPOINT_H150 / 150 s / gap 90 s / threshold 0.43.

## Operator notes (hardware)

- Vin 4.5–5.5 V, peak 150 mA. Not the ESP32 3.3 V rail.
- UART 9600 8N1 TTL 3.3 V, TX/RX crossed.
- Team pins: UART1 GPIO 32/33. Never share MR60 UART2 GPIO 16/17.
- 3 minute preheat: packets may flow; they are not valid model measurements.
- Factory ABC is left ON in the team sketch (`0x79` not sent). Range command `0x99` not sent.

## Explicit non-goals of this amendment

- Do not retrain or replace C-B6
- Do not change threshold 0.43
- Do not start C-C2 / formal Accuracy/F1
- Do not rewrite scaler or TFLite
- Do not edit `archive/`
- Do not modify checksum-locked C-C1T JSON in this change (those files still describe the SCD40-era producer; this report is the overlay)

## Frozen AI contract (unchanged)

```text
C_B6_REDUCED_CO2_SLOPE_CANDIDATE_001
inputs: CO2, CO2_slope
Temperature/Humidity: NOT required
slope: ENDPOINT_H150 / ENDPOINT_DIFFERENCE, 150 s, past-only
gap reset: > 90 s
nominal model cadence: ~60 s
threshold: 0.43 FROZEN
```

Slope reconstruction stays on the Pi runtime. ESP32 must not compute slope.
