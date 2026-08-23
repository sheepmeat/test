# SafeNest mmWave V2 — M-PV3.6 `ROLE_L_FULL_TASK` Evaluation

## 1. 결론

**Gate: `PASS_WITH_LIMITATIONS`**

`ROLE_L_FULL_TASK` 평가 카드를 채웠다. 평가 대상은 M-PV3 Family B/C의 6개 고정 seed이며, 모델·seed·다음 단계를 선택하지 않았다.

질문: **Is `ROLE_L_FULL_TASK` sufficiently evidenced for future selection consideration?**

**아니오.** 카드와 재현 가능한 수치는 확보되었지만, D1 DEV VAL에 허가된 `ABSENT`가 0개이고, 각 후보가 적어도 하나의 M-PV3 고정 utility guard를 충족하지 못한다. 따라서 향후 선택을 위한 역할 적격성 증거는 아직 불완전하다.

> `ROLE_L_FULL_TASK evaluation completed. No model selected.`

## 2. 평가 범위와 고정 기준

- 기준 계약: `MMWAVE_V2_M_PV36_ROLE_BASED_EVALUATION_CONTRACT_V1`, schema `M-PV3.6.2_CORRECTIVE`
- PR #134 병합 기준: `443d45d408829becc6a4e4db71bd6d9152c0d41d`
- 역할: `ROLE_L_FULL_TASK`
- 입력: 30초 문맥 `[B,300,1]`, 목표 `[t-5s,t]`
- 검증 그룹: `D1_DEV_VAL` (57 eligible PRESENT, 0 eligible ABSENT, 2 AMBIGUOUS, 3 subjects)
- 포함: Family B/C × seed 11, 23, 47 (총 6개)
- 제외: Family A RR-only, M-PV3.5 isolation CNN, 15초 short-context role
- M-PV3 상태: `NO_SELECTION_READY`
- 고정 guard: PRESENT recall ≥ 0.95, Brier ≤ 0.05, RR MAE ≤ 5 bpm, ±2 ≥ 0.40, ±4 ≥ 0.60, ±6 ≥ 0.75

계약, threshold, split, label, calibration, training, D2, MR60 supervised physiology는 변경하거나 사용하지 않았다. combined score, weighted ranking, Pareto winner, post-hoc best-seed 선택도 생성하지 않았다.

## 3. Breathing evidence card

D1 DEV VAL에는 eligible PRESENT만 있으므로 PRESENT 지표만 수치화했다. `ABSENT recall`은 `NOT_APPLICABLE`로 남겼고, 양성·음성 양쪽을 포함한 calibration이 검증되지 않아 ECE를 만들지 않았다.

| 후보 | PRESENT recall | precision | F1 | Brier | ABSENT recall | ECE |
|---|---:|---:|---:|---:|---|---|
| Family B / seed 11 | 1.000000 | 1.000000 | 1.000000 | 0.098541 | N/A | N/A |
| Family B / seed 23 | 1.000000 | 1.000000 | 1.000000 | 0.006457 | N/A | N/A |
| Family B / seed 47 | 0.982456 | 1.000000 | 0.991150 | 0.025081 | N/A | N/A |
| Family C / seed 11 | 0.982456 | 1.000000 | 0.991150 | 0.021158 | N/A | N/A |
| Family C / seed 23 | 0.982456 | 1.000000 | 0.991150 | 0.017920 | N/A | N/A |
| Family C / seed 47 | 1.000000 | 1.000000 | 1.000000 | 0.001268 | N/A | N/A |

재계산 수치는 기존 M-PV3 candidate evidence와 모두 최대 절대 차이 `0.0`으로 일치했다. 이는 새 split이나 새 label을 만들지 않고 기존 평가를 다시 확인했다는 뜻이다.

## 4. RR evidence card

| 후보 | MAE (bpm) | median error | ±2 bpm | ±4 bpm | ±6 bpm | 고정 guard 결과 |
|---|---:|---:|---:|---:|---:|---|
| Family B / seed 11 | 4.564752 | 2.794027 | 0.333333 | 0.631579 | 0.771930 | Brier 실패, ±2 실패 |
| Family B / seed 23 | 4.193873 | 2.081020 | 0.491228 | 0.666667 | 0.701754 | ±6 실패 |
| Family B / seed 47 | 4.900418 | 2.308027 | 0.456140 | 0.649123 | 0.736842 | ±6 실패 |
| Family C / seed 11 | 4.539816 | 3.188154 | 0.333333 | 0.631579 | 0.789474 | ±2 실패 |
| Family C / seed 23 | 4.541094 | 2.894703 | 0.368421 | 0.631579 | 0.807018 | ±2 실패 |
| Family C / seed 47 | 4.460836 | 2.379940 | 0.456140 | 0.649123 | 0.736842 | ±6 실패 |

표의 실패 표시는 고정 guard를 변경하거나 후보를 탈락·선정하기 위한 ranking이 아니다. 모든 후보를 같은 frozen 기준으로 기록한 것이다. MAE와 ±4는 6개 모두 guard 이상이지만, 후보별로 Brier·±2·±6 중 하나 이상이 남아 있어 `NO_SELECTION_READY`를 유지한다.

## 5. Class-A safety / quality card

안전 precedence는 다음과 같이 확인했다.

`PRESENCE → QUALITY_OR_AVAILABILITY → PHYSIOLOGY`

Q2는 실제 장치 검증이 아닌 `SYNTHETIC_ONLY` 시나리오다. 6개 corruption mode (`FLAT_EXACT`, `SOURCE_FREEZE`, `STALE_SOURCE`, `LARGE_GAP`, `JITTER_PLUS_LARGE_GAP`, `REPUBLICATION_TO_FREEZE`)를 각 후보에 적용했다.

- Q2 invalid false acceptance: 모든 후보 `0.0`
- invalid → physiology transition: 모든 후보 `0`
- invalid 이후 physiology emission: 모든 후보 `0`
- clean false rejection: 모든 후보 `0.0`
- fail-closed preservation: 모든 후보 `true`
- `INPUT_UNAVAILABLE`에서 `PRESENT`, `ABSENT`, `NORMAL`, `APNEA` emission: 모두 `0`

Safety는 보상 불가능한 Class A 항목이며, 이 카드는 모델 선택 점수로 사용하지 않았다.

## 6. Stability card

seed를 하나도 제거하지 않고 11/23/47을 모두 보고했다. 아래의 worst/best는 감사용 extrema일 뿐, seed 선택이 아니다.

| Family | 지표 | mean | population std | min | max | worst seed | best seed |
|---|---|---:|---:|---:|---:|---:|---:|
| B | PRESENT recall | 0.994152 | 0.008270 | 0.982456 | 1.000000 | 47 | 23 |
| B | Brier | 0.043360 | 0.039753 | 0.006457 | 0.098541 | 11 | 23 |
| B | RR MAE | 4.553015 | 0.288565 | 4.193873 | 4.900418 | 47 | 23 |
| B | RR ±2 | 0.426901 | 0.067695 | 0.333333 | 0.491228 | 11 | 23 |
| B | RR ±4 | 0.649123 | 0.014325 | 0.631579 | 0.666667 | 11 | 23 |
| B | RR ±6 | 0.736842 | 0.028649 | 0.701754 | 0.771930 | 23 | 11 |
| C | PRESENT recall | 0.988304 | 0.008270 | 0.982456 | 1.000000 | 11 | 47 |
| C | Brier | 0.013448 | 0.008714 | 0.001268 | 0.021158 | 11 | 47 |
| C | RR MAE | 4.513916 | 0.037536 | 4.460836 | 4.541094 | 23 | 47 |
| C | RR ±2 | 0.385965 | 0.051648 | 0.333333 | 0.456140 | 11 | 47 |
| C | RR ±4 | 0.637427 | 0.008270 | 0.631579 | 0.649123 | 11 | 47 |
| C | RR ±6 | 0.777778 | 0.029819 | 0.736842 | 0.807018 | 47 | 23 |

각 family의 subject-level 결과도 `D1_PERSON_03`, `D1_PERSON_09`, `D1_PERSON_11`에 대해 seed별로 보존했다. 원자료는 `stability_card.json`에 있다.

## 7. Footprint card

| Family | parameter count | checkpoint bytes | assembled tensor | MAC estimate | FLOP estimate |
|---|---:|---:|---|---:|---:|
| B (각 seed 동일) | 17,915 | 76,473 | `[1,621]` | 615,776 | 1,231,552 |
| C (각 seed 동일) | 21,115 | 89,337 | `[1,671]` | 618,976 | 1,237,952 |

역할 trace는 `[1,300,1]` float32이며, MAC/FLOP는 구조 기반 추정치다. Raspberry Pi latency/throughput은 측정하지 않았고 claim하지 않았다. INT8/TFLite 변환도 수행하지 않았다.

## 8. Limitations and future-selection answer

- D1 ABSENT limitation: eligible ABSENT 0개이므로 absent recall, specificity, full both-class role eligibility를 판단할 수 없다.
- D0는 observe-only이며 별도 reserved validation을 열지 않았다.
- D2 semantic access 금지.
- MR60 supervised physiology 미사용.
- calibration fitting 및 final threshold tuning 없음; numeric ECE 없음.
- INT8/TFLite 및 Raspberry Pi benchmark 없음.
- Q2는 `SYNTHETIC_ONLY` safety evidence이며 live-device validation이 아님.
- M-PV3 `NO_SELECTION_READY`를 유지하며 B/C winner, best seed, combined score, Pareto winner, M-PV4 recommendation을 만들지 않음.

따라서 현재 카드는 **평가 증거가 존재한다는 의미의 `PASS_WITH_LIMITATIONS`**이지만, 향후 모델 선택을 정당화할 만큼 충분히 완결된 역할 증거는 아니다.

## 9. 산출물

- Machine-readable cards/manifest: `datasets/mmwave/manifests/M-PV3_6_role_L_full_task_evaluation/`
- Runner: `scripts/mmwave_m_pv36_role_l_full_task_evaluation.py`
- Validator: `scripts/validate_mmwave_m_pv36_role_l_full_task_evaluation.py`
- Focused tests: `tests/test_mmwave_m_pv36_role_l_full_task_evaluation.py`
- Checksums: manifest directory의 `checksums.json`, `checksums.sha256`
