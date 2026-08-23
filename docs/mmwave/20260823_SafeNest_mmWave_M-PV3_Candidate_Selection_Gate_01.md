# SafeNest mmWave V2 — M-PV3 30초 후보 평가·선정 게이트

## 판정

- Gate: **PASS_WITH_LIMITATIONS**
- Selection result: **`NO_SELECTION_READY`**
- Selected float model: **없음**
- Ready for M-PV4: **NO** (단일 float 후보가 frozen utility gate를 모두 통과하지 못함)
- 15초 lane: **이번 gate에서 기다리지 않았고, registry/evidence에 섞지 않음**

M-PV3는 병합된 M-PV2 30초 후보 9개만 읽어 평가했다. 재학습, architecture 변경, M-PV1/M-PV2 데이터 변경, D2 payload 의미 접근, MR60 지도 physiology, calibration/최종 threshold tuning, INT8/TFLite, Pi 배포는 수행하지 않았다.

## 동결한 기준

계약은 평가 전에 `MMWV_V2_M_PV3_SELECTION_CONTRACT_V1`로 동결했다. 안전을 1순위로 두고 다음 순서로 판단한다.

1. Q2 invalid 입력은 fixed quality gate에서 physiology가 노출되지 않아야 한다. invalid false acceptance는 0, clean false rejection은 10% 이하로 고정했다.
2. provenance, TRAIN-only preprocessing, D2/MR60 금지, fresh-process deterministic replay, checkpoint/canonical SHA 일치를 확인한다.
3. full-task family B/C만 breathing PRESENT recall, Brier/ECE 진단, RR 연속값 MAE/median/±2/±4/±6를 평가한다. Family A는 RR/quality-only limitation으로 남긴다.
4. 후보가 모두 통과하지 않으면 선택하지 않는다. 통과 후보가 여러 개면 Pareto front를 보존하고, validation loss 하나로 고르지 않는다.

계약의 utility guard는 `PRESENT recall >= 0.95`, `Brier <= 0.05`, `RR MAE <= 5 bpm`, `within ±2 >= 0.40`, `within ±4 >= 0.60`, `within ±6 >= 0.75`이다. 이 값들은 이번 gate에서 사후로 조정하지 않았다.

## Registry / tensor / provenance audit

- M-PV2 registry: 9/9 family-seed 조합 확인
- checkpoint: 모두 M-PV2 model root 아래 존재, registry SHA/bytes 일치
- canonical parameter SHA: 9/9 일치
- tensor dimensions: A 59, B 621, C 671 일치
- scaler: TRAIN clean-only SHA `5a2583b5b5064be5480b0cf56f2a2c12d40a4a2d005eb087dc8e12106881159c`
- model-ready input: 562 unique (D0 318, D1 244), duplicate overlay 0
- provenance: 필수 source/subject/recording/interval/split/profile/mask/quality lineage 보존, absolute path 0
- D2 rows/inference: 0 / 0

## 후보 결과 (D1_DEV_VAL)

| 후보 | PRESENT recall | Brier | RR MAE | ±2 | ±4 | ±6 | Q2 invalid FA | clean FR | utility |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| A/11 | — | — | 4.208 | 42.1% | 68.4% | 82.5% | 0 | 0 | breathing 미지원 |
| A/23 | — | — | 3.958 | 50.9% | 73.7% | 80.7% | 0 | 0 | breathing 미지원 |
| A/47 | — | — | 4.039 | 49.1% | 75.4% | 82.5% | 0 | 0 | breathing 미지원 |
| B/11 | 100.0% | 0.0985 | 4.565 | 33.3% | 63.2% | 77.2% | 0 | 0 | Brier/±2 미통과 |
| B/23 | 100.0% | 0.0065 | 4.194 | 49.1% | 66.7% | 70.2% | 0 | 0 | ±6 미통과 |
| B/47 | 98.2% | 0.0251 | 4.900 | 45.6% | 64.9% | 73.7% | 0 | 0 | ±6 미통과 |
| C/11 | 98.2% | 0.0212 | 4.540 | 33.3% | 63.2% | 78.9% | 0 | 0 | ±2 미통과 |
| C/23 | 98.2% | 0.0179 | 4.541 | 36.8% | 63.2% | 80.7% | 0 | 0 | ±2 미통과 |
| C/47 | 100.0% | 0.0013 | 4.461 | 45.6% | 64.9% | 73.7% | 0 | 0 | ±6 미통과 |

Q2 평가는 `SOURCE_FREEZE`, `LARGE_GAP`, `STALE_SOURCE`, `FLAT_EXACT`, `REPUBLICATION_TO_FREEZE`를 각각 한 건씩 평가했다. 모든 후보에서 invalid physiology exposure 0건, invalid false acceptance 0.0, clean false rejection 0.0이었다. 이 결과는 synthetic unavailable-input profile에 대한 결과이며 실시간 MR60 실측 검증은 아니다.

## 왜 선택하지 않았나

안전 게이트와 재현성은 9개 모두 통과했다. 그러나 full-task 후보 중에서는 한 후보도 동결한 utility guard를 모두 만족하지 않았다. 예를 들어 B/23은 breathing calibration과 MAE가 좋지만 ±6 비율이 70.2%이고, C/47은 Brier가 0.0013으로 가장 좋지만 ±6 비율이 73.7%다. 이를 근거 없이 threshold를 낮추거나 한 지표만 보고 승격하면 selection gate가 사후 튜닝으로 변하므로 `NO_SELECTION_READY`를 유지했다.

따라서 M-PV3의 결론은 “안전하게 재현 가능한 후보군은 확인했지만, 이번 계약으로 단일 생산 후보를 고를 증거는 아직 부족하다”이다. 후속 M-PV4는 이 결과를 읽고 utility guard의 근거를 별도 승인하거나, 더 넓은 검증 evidence를 추가한 뒤 재평가해야 한다. 이번 단계에서 후보 checkpoint나 training data를 바꾸지는 않는다.

## Reproducibility / validation

- representative fresh-process replay: `family_b/seed_11`
- canonical parameter SHA, checkpoint SHA, input/scaler/config SHA, prediction SHA: 모두 일치
- M-PV3 validator: **PASS_WITH_LIMITATIONS**, failed checks 0
- M-PV3 tests: **4 passed**
- M-PV2 validator: **PASS_WITH_LIMITATIONS**
- M-PV1 validator: **PASS_WITH_LIMITATIONS**
- R1/R2/R3/I3 validators: 모두 **PASS_WITH_LIMITATIONS**, errors 0
- upstream regression tests: **67 passed**

## 산출물

- 계약: `config/mmwave/m_pv3_selection_contract.json`
- 증거: `datasets/mmwave/manifests/M-PV3_candidate_selection/`
- 평가기: `scripts/mmwave_m_pv3_candidate_selection.py`
- validator: `scripts/validate_mmwave_m_pv3_candidate_selection.py`
- 테스트: `tests/test_mmwave_m_pv3_candidate_selection.py`
