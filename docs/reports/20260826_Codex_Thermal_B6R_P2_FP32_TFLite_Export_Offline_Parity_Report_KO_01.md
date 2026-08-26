# SafeNest Thermal B6-R B6R-P2 FP32 TFLite Export & Offline Parity 실행 보고서

## 1. 작업 개요

- 날짜: `2026-08-26`
- Stage: `B6R-P2 — Public SDT FP32 TFLite Export & Offline Parity`
- 브랜치: `feature/thermal-b6r-development`
- 시작 HEAD: `f7b4256a5e310ecc53889761560c051082359243`
- 목적: B6R-P1 NumPy candidate의 architecture와 trained parameter를 그대로 FP32 TFLite로 옮기고 DEVELOPMENT에서 NumPy↔TensorFlow↔TFLite 구현 동등성을 검증
- 최종 상태: `PASS`
- 명시적 제외: 재학습, quantization, Raspberry Pi benchmark, MI48/physical 평가, runtime selector/default 변경, safety integration, B6R-P3 정의·실행

## 2. 전체 진행상황 요약

MI48 본선과 public-data 보조 흐름은 별도다. P2 성공은 MI48 본선 gate를 변경하지 않는다.

| 흐름 | Stage | Status | 핵심 상태 |
|---|---|---|---|
| MI48 본선 | B6R-0 | `FAIL` | B5 authoritative checkpoint/binary 증거 부족 |
| MI48 본선 | B6R-1 | `INCONCLUSIVE` | authoritative MI48 snapshot 부재 |
| MI48 본선 | B6R-2 | `BLOCKED` | group/label/independent holdout 계약 불가 |
| MI48 본선 | B6R-3~14 | `NOT_STARTED` | 선행 gate 미충족 |
| Public 보조 | B6R-P0 | `PASS_WITH_LIMITATIONS` | 48,000 public SDT materialization 및 split lock |
| Public 보조 | B6R-P1 | `PASS_WITH_LIMITATIONS` | NumPy-only pooled MLP controlled training |
| Public 보조 | B6R-P2 | `PASS` | FP32 TFLite export와 offline parity 통과 |

## 3. B6R-P1 인수 상태

| 항목 | 실제 검증값 |
|---|---|
| P1 status | `PASS_WITH_LIMITATIONS` |
| model ID | `thermal_public_sdt_pooled_mlp_v1` |
| architecture ID | `PUBLIC_SDT_ADAPTIVE_POOL_MLP_V1` |
| dataset ID | `PUBLIC_SDT_48000_THERMAL_ONLY_V1` |
| preprocessing ID | `PUBLIC_SDT_BILINEAR_62X80_FRAME_MINMAX_V1` |
| label mapping ID | `SDT_POSTURE_TO_SAFENEST_3CLASS_PROXY_V1` |
| input | `(62,80,1)` `float32` |
| class order | `NOT_HUMAN`, `HUMAN_NORMAL`, `HUMAN_FALL_PROXY` |
| weight shape | `(80,32)`, `(32,)`, `(32,3)`, `(3,)` |
| parameter count | `2,691` |
| training seed | `42` |
| P1 artifact SHA-256 | `35680056a841913c50e3d3e5fc7988e209e80ba5e62fd179fb135d35acf25677` |
| P1 metadata SHA-256 | `e510fa234b95c3cad5fc080e89adf316bff95e0535581fbc2ce063900d4e6fbc` |
| DEVELOPMENT | accuracy `0.9070`, macro-F1 `0.9013267411`, loss `0.3495067358` |
| default activation / safety authority | `false` / `false` |
| LOCKED_PUBLIC_TEST | array open `0`, sample read `0`, metric `false` |

NPZ를 직접 열어 4개 tensor의 이름·shape·dtype·parameter 수를 재계산했고, DEVELOPMENT prediction/probability hash도 P1 metadata와 일치했다. 알려진 제한은 public SDT가 MI48 native/physical 자료가 아니고 `HUMAN_FALL_PROXY`가 실제 낙상 사건이나 안전 판정이 아니라는 점이다.

## 4. B6R-P2 정의 이유

P1은 학습된 NumPy model만 제공하므로 Raspberry Pi/TFLite 경로에서 사용할 deployment-format artifact와 implementation parity 근거가 없었다. P2는 성능 개선 stage가 아니라 P1 identity 보존 여부를 검증하는 직접 후속 단계로 정의했다. 결과 확인 전에 다음 gate를 contract에 고정했다.

- pooled/hidden/logits/probability max absolute difference `<= 1e-5`
- probability mean absolute difference `<= 1e-6`
- prediction agreement `100%`
- mismatch count `0`

## 5. 수행 작업

1. P0/P1 contract, manifest, artifact, 보고서와 commit history를 대조했다.
2. P1 NPZ hash, metadata hash, weight shape/hash, FP32 dtype, parameter count, class order, seed, DEVELOPMENT result를 검증했다.
3. P1 `numpy.linspace(..., dtype=int64)` 경계와 같은 높이 경계 `[0,7,15,23,31,38,46,54,62]`, 너비 경계 `[0,8,...,80]`의 TensorFlow adaptive mean pool을 구현했다.
4. P1 weight를 새로 학습하지 않고 Dense 32/ReLU/Dense 3/Softmax graph에 그대로 주입했다.
5. DEVELOPMENT에서 class별 typical 8개와 boundary-margin 8개, 총 48개 deterministic fixture를 생성하고 sample ID를 manifest에 기록했다.
6. NumPy↔TensorFlow pooled feature, hidden, logits, probability를 비교했다.
7. built-in TFLite op만 허용하고 optimization/quantization 없이 FP32 `.tflite`를 실제 생성했다.
8. TensorFlow Lite Interpreter로 input/output metadata와 quantization 없음 상태를 확인했다.
9. TensorFlow↔TFLite, NumPy↔TFLite probability 및 argmax를 비교했다.
10. 동일 process에서 2회 export하고 byte SHA-256 일치를 확인했다.
11. legacy model, default manifest, interpreter/runtime selector와 locked test access를 감사했다.

## 6. 변경 파일

- `.gitattributes` — P2 contract/manifest LF 정책.
- `config/thermal/b6r_p2_public_sdt_fp32_tflite_contract.json` — 상속 identity, fixture, 사전 tolerance, export/deployment 경계.
- `scripts/export_thermal_b6r_p2_public_sdt_fp32_tflite.py` — source audit, TensorFlow reconstruction, FP32 export, parity와 audit 생성.
- `scripts/validate_thermal_b6r_p2_public_sdt.py` — 독립 artifact/interpreter/parity/safety boundary validator.
- `tests/test_thermal_b6r_p2_public_sdt.py` — pooling 경계·순서·reconstruction·fixture·contract 단위검증.
- `models/thermal/public_sdt/public_sdt_pooled_mlp_fp32_tflite_v1.tflite` — 신규 shadow-only FP32 artifact.
- `datasets/thermal/manifests/B6R-P2_public_sdt_fp32_tflite_export/` — export, tensor, parity, determinism, checksum, locked-test, legacy, source, validation 증거.
- `docs/20260822_Codex_Thermal_B6R_Robust_Relative_FP32_Parallel_Roadmap_KO_01.md` — P2 정식 정의 및 `PASS` 결과.
- `docs/README.md`, `docs/thermal/B6R_DEVELOPMENT_INDEX.md` — current pointer/status.
- 이 보고서 — 실행 근거와 제한·rollback.

## 7. 환경

| 항목 | 값 |
|---|---|
| OS | `Windows-11-10.0.26200-SP0` |
| Python | `3.12.13` |
| NumPy | `2.5.2` |
| TensorFlow | `2.20.0` |
| TFLite interpreter | `tensorflow.lite.Interpreter` |
| dependency 격리 | Git-ignored project-local `.venv`; global/OS Python 변경 없음 |

TensorFlow 2.20은 `tensorflow.lite.Interpreter` deprecation warning을 출력했다. 현재 변환·load·invoke는 성공했지만 향후 Pi stage에서는 target LiteRT/tflite-runtime 환경을 별도로 확인해야 한다.

## 8. 실행 명령

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_thermal_b6r_p2_public_sdt -v
.\.venv\Scripts\python.exe -m scripts.export_thermal_b6r_p2_public_sdt_fp32_tflite
.\.venv\Scripts\python.exe -m scripts.validate_thermal_b6r_p2_public_sdt
.\.venv\Scripts\python.exe -m unittest tests.test_thermal_b6r_p0_public_sdt tests.test_thermal_b6r_p1_public_sdt tests.test_thermal_b6r_p2_public_sdt tests.test_thermal_interpreter -v
```

재현 환경은 `python -m venv .venv` 후 `.venv/Scripts/python.exe -m pip install tensorflow==2.20.0`으로 구성한다. materialized P0 TRAIN/DEVELOPMENT payload는 P0 artifact registry의 hash와 일치해야 한다.

## 9. Export 결과

| 항목 | 결과 |
|---|---|
| source model | `thermal_public_sdt_pooled_mlp_v1` |
| output model | `thermal_public_sdt_pooled_mlp_fp32_tflite_v1` |
| artifact | `models/thermal/public_sdt/public_sdt_pooled_mlp_fp32_tflite_v1.tflite` |
| size | `70,592 bytes` |
| SHA-256 | `f88d65d76dbb21862e1f3cdff17cefb038a432047ded6ac8d5563bc8bc8c52ff` |
| conversion | built-in ops, optimization 없음, quantization 없음, FP32 I/O |
| input | index `0`, `serving_default_thermal_frame:0`, `[1,62,80,1]`, `float32`, scale `0.0`, zero-point `0` |
| output | index `330`, `StatefulPartitionedCall_1:0`, `[1,3]`, `float32`, scale `0.0`, zero-point `0` |

## 10. Parity 결과

| 비교 | 대상 | Max abs diff | Mean abs diff | Agreement | Mismatch | Result |
|---|---|---:|---:|---:|---:|---|
| NumPy ↔ TensorFlow | pooled | `1.1920929e-7` | `4.3407149e-9` | `100%` | `0` | PASS |
| NumPy ↔ TensorFlow | hidden | `3.5762787e-7` | `1.1276872e-8` | `100%` | `0` | PASS |
| NumPy ↔ TensorFlow | logits | `1.4305115e-6` | `2.3634897e-7` | `100%` | `0` | PASS |
| NumPy ↔ TensorFlow | probabilities | `1.4901161e-7` | `2.6310115e-8` | `100%` | `0` | PASS |
| TensorFlow ↔ TFLite | probabilities | `2.9802322e-7` | `3.2731595e-8` | `100%` | `0` | PASS |
| NumPy ↔ TFLite | probabilities | `3.5762787e-7` | `3.8006313e-8` | `100%` | `0` | PASS |

모든 값은 사전 정의 tolerance 이내이며 mismatch sample ID는 없다.

## 11. Locked Test Audit

```text
LOCKED_PUBLIC_TEST read count: 0
array open count: 0
metric computed: false
selection/tuning use: false
```

P2 contract와 구현은 test path를 받지 않는다. 사용한 데이터는 P0의 `DEVELOPMENT` validation split과 P1 artifact뿐이다. P0 source provenance의 현재 PC 위치는 `C:\Users\KIMTAEGYUN\Documents\ChatGPT\Thermal_AI\열화상_dataset`이며, 이 폴더는 public SDT source archive이지 MI48/현장 후보가 아니다. P2는 source archive를 직접 재처리하거나 변경하지 않았고 `Desktop/sessions`도 사용하지 않았다. source·derived payload·경로 정책의 전체 설명은 `docs/reports/20260826_Codex_Thermal_B6R_B6R-P0_Public_SDT_Materialization_Report_KO_01.md`와 B6R roadmap의 current PC path registry를 따른다.

## 12. Legacy / Runtime 변경 Audit

| 항목 | 결과 |
|---|---|
| legacy thermal model changed? | `false`, SHA `5b56da8d...6ae84` 동일 |
| default `models/model_manifest.json` changed? | `false`, SHA `d55a1bce...6a97b` 동일 |
| runtime selector/interpreter changed? | `false`, interpreter SHA `8ed40930...a087` 동일 |
| default activation changed? | `false` |
| safety authority changed? | `false` |

## 13. Stage Gate 판정

최종 판정: `PASS`

| Test | Expected | Actual | Result |
|---|---|---|---|
| P1 artifact integrity | exact SHA/metadata/weight contract | 모두 일치 | PASS |
| P0/P1 inheritance | dataset/preprocessing/label/class 불변 | 모두 일치 | PASS |
| NumPy↔TF reconstruction | intermediate max abs `<=1e-5` | 최대 `1.4305115e-6` | PASS |
| FP32 TFLite export | 실제 file 생성 | 70,592 bytes | PASS |
| Interpreter load/tensor metadata | FP32 `[1,62,80,1]→[1,3]`, quantization 없음 | 일치 | PASS |
| TF↔TFLite parity | max `<=1e-5`, mean `<=1e-6`, mismatch 0 | `2.9802322e-7`, `2.6857050e-8`, 0 | PASS |
| NumPy↔TFLite parity | max `<=1e-5`, mean `<=1e-6`, mismatch 0 | `3.5762787e-7`, `3.8006313e-8`, 0 | PASS |
| Export determinism | 2회 SHA 일치 | `f88d65d7...c52ff` 동일 | PASS |
| Locked test | read 0 | 0 | PASS |
| Legacy/default/runtime | 불변 | 불변 | PASS |
| Focused/upstream regression | 실행 성공 | 22 tests, 20 pass, 2 skip, 0 fail | PASS |

## 14. 문제 및 제한사항

- public SDT 결과이며 MI48 native sensor/physical 성능이 아니다.
- `HUMAN_FALL_PROXY`는 lying/fallen posture proxy이며 실제 낙상 사건이나 safety decision이 아니다.
- Raspberry Pi latency, p50/p95/p99, RSS, 장시간 replay, target LiteRT 호환성은 측정하지 않았다.
- production runtime selector와 default manifest에 P2 artifact를 등록하지 않았다.
- P0/P1 public split에는 subject/session/recording identity가 없어 group-isolated generalization을 주장할 수 없다.
- 기존 legacy interpreter 회귀 중 repository NPZ가 필요한 2개 smoke test는 입력 파일 부재로 skip됐다. 나머지 20개는 통과했다.

## 15. 전체 진행상황

| Stage | Status | 핵심 결과 |
|---|---|---|
| B6R-P0 | `PASS_WITH_LIMITATIONS` | public SDT 48,000개 materialization, split/provenance lock |
| B6R-P1 | `PASS_WITH_LIMITATIONS` | deterministic NumPy pooled MLP, DEVELOPMENT-only selection |
| B6R-P2 | `PASS` | exact P1 weight FP32 TFLite export, offline parity, mismatch 0 |

본선은 B6R-1 `INCONCLUSIVE`, B6R-2 `BLOCKED`를 유지하며 B6R-3~14는 실행하지 않았다.

## 16. 다음 해야 할 일

다음 후보는 제안만 한다.

`B6R-P3 — Raspberry Pi FP32 TFLite Replay & Shadow Benchmark`

1. Raspberry Pi target interpreter/LiteRT version과 exact artifact SHA 확인.
2. fixed replay에서 preprocess/inference/total latency p50/p95/p99 측정.
3. RSS·CPU·temperature와 30분 이상 prolonged replay stability 측정.
4. 반복 load/inference output determinism과 shadow-only runtime 경계 확인.
5. default activation 없이 rollback 가능한 opt-in 경로 여부 평가.

이번 실행에서는 B6R-P3를 roadmap의 정식 stage로 정의하거나 구현하지 않았다.

## 17. Rollback

P2는 legacy/default runtime을 변경하지 않았으므로 운영 rollback 조작은 필요 없다. 문제가 발견되면 이 delivery commit을 일반 `git revert <B6R-P2 delivery commit>`로 되돌리거나 다음 신규 파일만 제거하는 후속 commit을 만든다.

- `models/thermal/public_sdt/public_sdt_pooled_mlp_fp32_tflite_v1.tflite`
- `datasets/thermal/manifests/B6R-P2_public_sdt_fp32_tflite_export/`
- P2 contract/export/validator/test/report와 pointer 변경

P1 NPZ, legacy model, `models/model_manifest.json`, runtime selector는 P2 이전 identity 그대로 유지된다.

`STOP — B6R-P3 또는 이후 작업은 새 사용자 지시 없이 실행하지 않는다.`
