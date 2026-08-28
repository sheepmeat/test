# SafeNest Thermal B6-R B6R-P1 Public SDT Controlled Training 실행 보고서

## 1. 작업 개요

- 날짜: `2026-08-26`
- Stage: `B6R-P1 — Public SDT Controlled Training`
- 성격: 기존 B6R-0~14에 없던 public-data 전용 보조 stage
- 작업 브랜치: `feature/thermal-b6r-development`
- 선행 stage: `B6R-P0` (`PASS_WITH_LIMITATIONS`)
- 사용자 승인: `2026-08-26`, P1 실행·보고서 작성 지시
- 결과 상태: `PASS_WITH_LIMITATIONS — PUBLIC_DATA_ONLY`
- 기존 B6R-0~14 판정: 변경 없음

## 2. 이 단계가 추가된 이유

본선 B6R은 권위 MI48 snapshot과 physical evidence를 요구하지만, 현재 `B6R-1`은 `INCONCLUSIVE`, `B6R-2`는 `BLOCKED`다. 사용자는 C 계열 physical 작업을 당장 진행하지 않고 P0에서 만든 public SDT 입력으로 모델을 먼저 생성하도록 승인했다.

따라서 P1은 본선의 MI48 gate를 우회하지 않는다. public-data 모델을 별도 identity로 생성하는 실험 흐름이며, 이 결과만으로 MI48 성능·실제 낙상·안전 기능·competition lock을 주장하지 않는다.

## 3. 진입 조건 및 상속한 계약

| 항목 | 적용 내용 |
|---|---|
| P0 identity | `PUBLIC_SDT_48000_THERMAL_ONLY_V1` |
| P0 validation | `PASS_WITH_LIMITATIONS`, SHA-256 `7e7ff6d2b84c1ffe8feaa0379b36dcf07afabee7459ea8f9be7eaee7e819835b` |
| 입력 preprocessing | `PUBLIC_SDT_BILINEAR_62X80_FRAME_MINMAX_V1` |
| label mapping | `SDT_POSTURE_TO_SAFENEST_3CLASS_PROXY_V1` |
| TRAIN | 32,000개 — parameter fitting |
| DEVELOPMENT | 8,000개 — best epoch 선택·검증 |
| LOCKED_PUBLIC_TEST | 8,000개 — P1에서 path 미설정, read `0`, metric `0` |
| random resplit | 수행하지 않음 |

기존 `thermal_prep.py`의 split 병합 및 `thermal_train.py`의 combined random 80:20 분할·legacy overwrite 경로는 사용하지 않았다.

## 4. 학습 runtime 판단

실행 환경을 먼저 조사한 결과 bundled Python `3.12.13`에 NumPy `2.3.5`는 있었지만 TensorFlow, PyTorch, scikit-learn, SciPy, JAX, ONNX는 설치되어 있지 않았다.

이에 의존성을 설치하거나 기존 legacy 학습 경로를 사용하지 않고, 계약에 명시한 NumPy-only 실험 baseline을 구현했다. 이 선택은 학습 실행을 가능하게 하지만 `SMALL_CNN_BASELINE_V1`, Keras, TFLite, Raspberry Pi parity를 충족한다는 뜻은 아니다.

## 5. 모델 및 학습 계약

```text
(62, 80, 1) float32
  → deterministic adaptive mean pool (8, 10) = 80 features
  → Dense 32 + ReLU
  → Dense 3 + softmax
```

- Model ID: `thermal_public_sdt_pooled_mlp_v1`
- Architecture ID: `PUBLIC_SDT_ADAPTIVE_POOL_MLP_V1`
- Parameter count: `2,691`
- Optimizer: deterministic minibatch SGD
- Seed: `42`
- Epoch budget: 최대 `40`
- Batch size: `512`
- Learning rate: `0.05`
- L2: `0.0001`
- Early stopping monitor: DEVELOPMENT loss, patience `8`, min delta `0.00001`
- 초기화: seeded normal(std `0.02`), zero bias
- 산출 model: deterministic timestamp 고정 NPZ

## 6. 수행한 작업

1. P0 validation artifact SHA-256을 확인해 P1 contract와 일치시켰다.
2. P0의 TRAIN/DEVELOPMENT `images.npy`와 labels만 memory-map으로 읽었다.
3. 각 입력을 고정된 `(8,10)` adaptive mean pooling으로 80차원 feature로 변환했다.
4. 같은 seed·순열·예산으로 학습을 두 번 수행하고 weight, history, best epoch를 비교했다.
5. DEVELOPMENT loss 기준 최적 epoch의 별도 public model artifact와 metadata를 저장했다.
6. `models/model_manifest.json`을 학습 전·후 SHA-256으로 비교했다.
7. test 경로를 계약에 `null`로 고정하고 test array open·sample read·metric·selection 사용을 모두 `0/false`로 기록했다.
8. model tensor shape, parameter count, hash, deployment boundary, 절대경로 미기록을 validator로 확인했다.

## 7. 학습 결과

| Split | Samples | Loss | Accuracy | Macro-F1 | 용도 |
|---|---:|---:|---:|---:|---|
| TRAIN | 32,000 | `0.34136194` | `0.9051875` | `0.8992181` | fitting 확인 |
| DEVELOPMENT | 8,000 | `0.34950674` | `0.9070000` | `0.9013267` | best epoch/개발 검증 |
| LOCKED_PUBLIC_TEST | 8,000 | - | - | - | read 0, metric 0 |

- best epoch: `40`
- train prediction SHA-256: `ff7f08891334d0abbe68aa91718048bb7cdeb9dcea321ce25ac410bcff0a3e8f`
- development prediction SHA-256: `65efe9df3da592c9c01a4da0d1ab2709815009fe803a8b1f319d97fc1c3d7223`
- development probabilities SHA-256: `3b00401e800513bdc9b93f4e8eb5123060dfcc5ee380bb0d24f62ec46f7aab7f`

위 수치는 public split의 offline 지표이며 MI48 또는 실제 낙상 성능 지표가 아니다.

## 8. 결정론·무결성·안전 경계 검증

| 검증 | 결과 |
|---|---|
| P0 predecessor identity | PASS |
| NumPy 학습 2회 weight 동일 | PASS |
| 학습 history·best epoch 동일 | PASS |
| test array open | `0` |
| test sample read | `0` |
| test metric/selection/tuning | `false/false/false` |
| model tensor shape | `(80,32)`, `(32,)`, `(32,3)`, `(3,)` PASS |
| parameter count | `2,691` PASS |
| deterministic NPZ model SHA-256 | `35680056a841913c50e3d3e5fc7988e209e80ba5e62fd179fb135d35acf25677` |
| legacy `models/model_manifest.json` 변경 | 전후 SHA 동일, PASS |
| default activation | `false` |
| safety authority | `false` |
| deployment mode | `SHADOW_ONLY` |

## 9. 생성 파일

- `config/thermal/b6r_p1_public_sdt_training_contract.json`
- `scripts/train_thermal_b6r_p1_public_sdt.py`
- `scripts/validate_thermal_b6r_p1_public_sdt.py`
- `tests/test_thermal_b6r_p1_public_sdt.py`
- `models/thermal/public_sdt/public_sdt_pooled_mlp_v1.npz` (10,879 bytes)
- `models/thermal/public_sdt/public_sdt_pooled_mlp_v1.json` (2,607 bytes)
- `datasets/thermal/manifests/B6R-P1_public_sdt_controlled_training/`

P1 model은 legacy thermal model과 별도 경로·별도 model ID를 사용한다. `models/model_manifest.json`의 default thermal entry는 수정하지 않았다.

## 10. 검증 및 테스트

| Test | Actual | Result |
|---|---|---|
| Python compile | P1 train/validator/focused test 성공 | PASS |
| focused unittest | `5 tests`, 모두 성공 | PASS |
| P1 training | TRAIN 32,000 / DEVELOPMENT 8,000 | PASS |
| deterministic repeat | weight/history/best epoch 일치 | PASS |
| P1 validator | `PASS_WITH_LIMITATIONS` | PASS |
| test access audit | path 미설정, read 0, metric 0 | PASS |
| legacy manifest audit | 전후 SHA 동일 | PASS |

실행 시 test archive·test materialized array는 읽지 않았다.

## 11. 제한 사항

- 데이터는 public SDT이며 MI48 native raw capture가 아니다.
- subject/session/recording identity가 없어 group-isolated generalization을 주장하지 않는다.
- `HUMAN_FALL_PROXY`는 lying/fallen posture proxy이며 실제 낙상 사건이 아니다.
- NumPy pooled MLP는 `SMALL_CNN_BASELINE_V1`이 아니며 Keras↔TFLite parity가 없다.
- Raspberry Pi latency, memory, thermal physical input, fail-closed runtime은 검증하지 않았다.
- public DEVELOPMENT 지표는 model 선택에 사용된 지표이므로 독립 최종 성능으로 해석하지 않는다.

## 12. 본선 상태 및 적용 가능 범위

- `B6R-0`: 기존 `FAIL` 유지
- `B6R-1`: 기존 `INCONCLUSIVE` 유지
- `B6R-2`: 기존 `BLOCKED` 유지
- `B6R-3~B6R-14`: 시작하지 않음
- B6R-11·13·14 physical/competition lock: 여전히 수행 불가

이 모델은 offline 분석과 shadow-only 비교에만 사용할 수 있다. 기본 모델 교체, safety alarm/emergency 판단, thermal-only strongest danger 생성, MI48/physical/competition claim에는 사용할 수 없다.

## 13. 다음 작업 규칙

다음 후보는 P1 보고서 검토 후 별도 승인되는 TFLite export 또는 runtime integration stage다. 해당 stage에서도 exact model hash와 preprocessing identity를 유지하고, legacy rollback·`default_activation=false`·`safety_authority=false`를 먼저 보장해야 한다.

MI48 본선은 별개다. 권위 MI48 payload와 provenance를 확보한 뒤 B6R-1 새 revision과 B6R-2를 다시 통과해야 한다.

## 14. Stage Gate 판정 및 STOP

최종 판정: `PASS_WITH_LIMITATIONS — PUBLIC_DATA_ONLY`

P0 contract 상속, TRAIN/DEVELOPMENT controlled training, test 비접근, deterministic repeat, 별도 model identity, legacy 불변 검증은 완료됐다. 이 판정은 public-data 실험 모델 생성 완료를 의미하며 MI48·physical·safety release 승인을 의미하지 않는다.

`STOP — 별도 승인 없이 TFLite/Pi/runtime/safety integration 또는 기본 모델 교체를 진행하지 않는다.`
