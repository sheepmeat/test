# SafeNest mmWave — PUBABS-A8 보고용 요약

**동결 C1 외부 OOD stress 추론 실행 결과 (선택·순위 없음)**

| 항목 | 내용 |
|---|---|
| 단계 | PUBABS-A8 |
| 일자 | 2026-08-27 |
| 성격 | A7에서 동결한 규칙대로 **외부 도메인 stress 결과 생성** |
| 실행 상태 | `EXECUTION_COMPLETE` / abort `NONE` |
| 해석 | `DESCRIPTIVE_ONLY` — 과학적 PASS/FAIL·우승자 선정 **없음** |
| PR | https://github.com/sheepmeat/test/pull/167 （merge 대기, Sol 리뷰용） |
| 커밋 | `b992b740268040c27a6beefc5452a6368c93489a` |
| 상세 기술 보고서 | [`…Execution_01.md`](20260827_SafeNest_mmWave_PUBABS_A8_C1_External_Stress_Inference_Execution_01.md) |

---

## 1. 한 줄 결론

A6에서 동결한 VALID34(34세션)에 대해, A7에서 동결한 ROLE_L 6후보(B11·B23·B47·C11·C23·C47)를 **고정 순서·고정 임계값 0.5·PyTorch float32 CPU**로 추론했고, 사전 등록 지표만 산출했다.  
이 결과는 **외부 안전 도메인 stress 증거**이며, 모델 선택·D1 대체·M-PV3.8 재개·M-PV4 승인으로 쓰면 안 된다.

---

## 2. 이번 단계가 한 일 / 안 한 일

### 한 일

1. PR #166(A7 추론 계약) 검증·merge 후 clean A8 브랜치에서 실행
2. A6/A7 해시·어댑터·스케일러·6개 `.pt` 아티팩트 무결성 재검증
3. `r1_centered` → 정규 R2 → M-PV2 `_feature_matrix`로 Family B **621** / Family C **671** 입력 재구성 (이중 z-score 금지)
4. Layer1 ALL77은 **가용성만** 보고, FAIL_CLOSED 43건에는 예측 미생성
5. Layer2 VALID34만 추론 → **204건**(34×6) 원시 출력·지표·결정성 영수증 생성

### 하지 않은 일

- 순위·우승자·후보 탈락
- 임계값 재튜닝 / 캘리브레이션 / C1 스케일러 재적합
- RR·quality·apnea 정확도 채점
- M-PV3.8 최종 선택 게이트를 C1에 적용
- D1 구성·변경, M-PV3.8 재개, M-PV4 승인

---

## 3. 선행 계약 (무결성)

| 계약 | 값 |
|---|---|
| A6 | `PUBABS_C1_EXTERNAL_STRESS_V1` |
| A6 SHA-256 | `d0353c9bf7837a2520364903b53075bde44cddf10b88c3fef58aa4054bbb3310` |
| Layer1 (77) SHA-256 | `cefc7a3820ebb644a9553b3eaad9f4ec600ea555bc25ed891f236cc50c6632f5` |
| Layer2 (34) SHA-256 | `01a1db3ef56e1071896f054a5baad397035ca6d989f42f2d1129d250b6867c7c` |
| A7 | `PUBABS_C1_EXTERNAL_STRESS_INFERENCE_V1` |
| 어댑터 해시 | `cfce866f659658e772e833f64e881549a4244b8c9daaa85423b343f34c424446` |

---

## 4. 데이터 계층 (혼동 금지)

### Layer 1 — 가용성만 (ALL77)

| TOTAL | ABSENT | PRESENT | VALID | FAIL_CLOSED | gap 실패 | 너무 짧음 |
|---:|---:|---:|---:|---:|---:|---:|
| 77 | 11 | 66 | 34 | 43 | 42 | 1 |

FAIL_CLOSED 43건은 모델 입력으로 넣지 않았고, 임의 확률·ABSENT 점수도 만들지 않았다.

### Layer 2 — 조건부 모델 stress (VALID34만)

| TOTAL | ABSENT | PRESENT | PRESENT 피험자 |
|---:|---:|---:|---|
| 34 | 9 | 25 | N1=1, N2=1, N3=9, N4=8, N5=6, **N6=0** |

의미: `CONDITIONAL_ON_ADAPTER_VALID` + `OUT_OF_DOMAIN_EXTERNAL_STRESS` + `DESCRIPTIVE_ONLY`.  
**VALID34 ≠ 전체 C1 코퍼스**, **≠ MR60 배포 성능**, **≠ M-PV3.8 D1 recall**.

---

## 5. 실행 환경

| 항목 | 값 |
|---|---|
| Python / PyTorch / NumPy | 3.9.6 / 2.8.0 / 1.26.4 |
| 디바이스 | CPU |
| 결정성 | deterministic algorithms ON, threads=1 |
| 형식 | float32 state_dict (TFLite/INT8/ONNX 변환 없음) |
| breathing 결정 | `sigmoid(logit) ≥ 0.5` → PRESENT |
| 재현 | 전체 추론 2회 동일 |
| 204건 출력 집합 SHA-256 | `13e4d85591300dda5619630608e49477cd989e05095925ac9d68706147aa626c` |

---

## 6. 사전 등록 1차 지표 (고정 표시 순서)

분모는 항상 명시: ABSENT **9**, PRESENT **25**.

| 후보 | ABSENT 생리 방출 건수 / 9 | 방출률 | PRESENT recall / 25 |
|---|---:|---:|---:|
| B11 | 0 | 0.000 | 0.00 |
| B23 | 0 | 0.000 | 0.00 |
| B47 | 2 | 0.222 | 0.00 |
| C11 | 9 | 1.000 | 1.00 |
| C23 | 7 | 0.778 | 0.72 |
| C47 | 0 | 0.000 | 0.00 |

**용어**

- **ABSENT 생리 방출**: 사람 타깃이 없는(ABSENT) 세션에서 breathing 결정을 PRESENT로 낸 경우. RR 오차·무호흡·임상 오진이 **아님**.
- 표는 **고정 패널 순서**이며, 성능 순 정렬·“최고 후보” 서술이 **아님**.

---

## 7. 등록된 2차 지표 요지 (진단용)

| 후보 | TP | FP | TN | FN | Precision | F1 | Brier |
|---|---:|---:|---:|---:|---:|---:|---:|
| B11 | 0 | 0 | 9 | 25 | N/A | N/A | 0.505 |
| B23 | 0 | 0 | 9 | 25 | N/A | N/A | 0.735 |
| B47 | 0 | 2 | 7 | 25 | 0.00 | N/A | 0.723 |
| C11 | 25 | 9 | 0 | 0 | 0.735 | 0.847 | 0.265 |
| C23 | 18 | 7 | 2 | 7 | 0.72 | 0.72 | 0.262 |
| C47 | 0 | 0 | 9 | 25 | N/A | N/A | 0.735 |

Brier는 **진단용**이며 M-PV3.8 `Brier ≤ 0.05` 게이트와 비교해 PASS/FAIL로 쓰지 않는다.  
RR / quality / apnea 계열 지표는 **채점하지 않음** (`NOT_SCORED`).

---

## 8. 제한사항 (결과가 좋아도/나빠도 유지)

1. **TRAIN z-score 스케일 리스크 = HIGH** (C1 스케일러 재적합 금지)
2. **교차 센서 도메인 리스크 = HIGH**
3. VALID34는 코퍼스 대표가 아님
4. Layer2 ABSENT n=9로 작음
5. VALID PRESENT에 **N6 = 0**

좋은 외부 결과라도 모델 선택·M-PV3.8 재개·M-PV4·D1 대체를 **승인하지 않는다**.  
나쁜 외부 결과로 동결 M-PV3.8 패널에서 후보를 **제거하지도 않는다**.

---

## 9. 라이프사이클 상태 (변경 없음)

```text
D1_FINAL_SELECTION_BOTH_CLASS_V1  = UNCHANGED
M-PV3.8                           = RESOURCE_BLOCKED_CLOSED
M-PV4                             = UNAUTHORIZED
D2                                = LOCKED
Final membership                  = BLOCKED_INVALID_FINAL_MEMBERSHIP
```

---

## 10. 산출물 위치

| 종류 | 경로 |
|---|---|
| 실행 스크립트 | `scripts/mmwave/pubabs_a8_external_stress_inference.py` |
| 머신 가독 매니페스트 | `datasets/mmwave/manifests/PUBABS_A8_c1_external_stress_inference/` |
| validation | 동 디렉터리 `validation_result.json` |
| 영문 기술 보고서 | `docs/mmwave/20260827_SafeNest_mmWave_PUBABS_A8_C1_External_Stress_Inference_Execution_01.md` |
| 본 보고용 요약(KO) | 본 문서 |
| 테스트 | `tests/test_mmwave_pubabs_a8_external_stress_inference.py` (7 passed) |

원시 C1 `Data.zip`은 DOI·MD5 검증 후 사용했으며 **커밋하지 않음**.

---

## 11. Sol / 다음 단계에 넘길 말

- A8 실행 무결성: **완료** (`abort_status=NONE`, 204/204).
- 과학적 해석·선택 게이트: **아직 없음** (`DESCRIPTIVE_ONLY`).
- 요청: Sol independent review of [PR #167](https://github.com/sheepmeat/test/pull/167). **본 에이전트는 A8 PR을 merge하지 않음.**
