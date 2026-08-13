# SafeNest 멀티센서 중간배포 기술 맥락 및 인수인계

검토 기준일은 2026-08-13이며, 이 문서는 standalone 저장소 `main`의 `f56809cd2df1eb55c3272ff5455a10260e76ff74`를 기준으로 작성되었다. 수치와 상태는 설명문보다 현재 저장소의 validator 통과 JSON, checksum, 모델 파일을 우선하여 확인했다. 팀 저장소의 센서 관련 미병합 자료는 현재 열린 PR과 원격 branch 상태를 별도로 확인했으며, 구형 `ondevice_ai/` 구현은 새 파이프라인의 성능 또는 방향성을 입증하는 자료로 사용하지 않았다.

## 1. 한눈에 보는 센서별 현재 단계와 남은 작업

센서별 표기의 A는 원본과 데이터 처리 기준을 확정하는 단계, B는 저장된 데이터로 전처리와 모델을 비교해 offline 후보를 고르는 단계, C는 실제 센서와 목표 실행 장치에서 입력과 성능을 확인하는 단계이다. D는 C에서 실제 차이가 발견된 센서에만 데이터 추가 수집과 재학습을 수행하는 조건부 단계이고, E는 최종 artifact와 계약을 잠가 통합 준비 상태로 만드는 단계이다. 그 뒤 공통 I-0~I-6은 세 센서를 같은 packet·시간·유효성·위험 판단 규칙에 연결하고 Raspberry Pi와 팀 저장소에서 검증하는 통합 단계이다. 각 단계의 작업량이 같지 않으므로 진행률을 단순 백분율로 표시하지 않고, 완료한 증거 층과 앞으로 통과해야 할 필수 관문으로 남은 양을 설명한다.

| 센서 | 현재 위치 | 현재까지 완료된 의미 | 앞으로 남은 필수 관문 | 조건에 따라 추가되는 작업 |
| --- | --- | --- | --- | --- |
| mmWave | A0~A6와 M-B0~M-B12 완료 | 실제 공개 레이더 데이터의 표준화, 사람 단위 분할, 모델 비교와 offline INT8 후보 고정까지 완료 | M-C 실제 MR60 검증과 장치 결과를 반영한 최종 artifact·통합 준비, 이후 공통 I단계 | MR60과 공개 데이터의 차이가 크면 M-D에서 필요한 조건의 데이터를 더 모아 재학습 |
| CO₂ | C-A0~C-A6와 C-B0~C-B5 완료 | 실제 UCI 원본의 시간 계보, feature, 모델 비교와 offline INT8 occupancy 후보 고정까지 완료 | C-C 실제 SCD40 검증과 C-E 최종 artifact·통합 준비, 이후 공통 I단계 | SCD40의 범위·측정 주기·환경 차이가 크면 C-D에서 gap을 채우는 데이터 확장과 재학습 |
| Thermal | T-A0~T-A6 완료, `t_b_authorized: false` | 48,000장 원본의 온도 단위, 화면 geometry, 라벨 의미, 공식 분할과 중복 한계까지 확정 | T-B0 승인 검토와 T-B offline 모델 비교, T-C 실제 열화상 센서 검증, T-E 최종 lock, 이후 공통 I단계 | 실제 장치나 평가 데이터의 빈틈이 확인되면 T-D에서 새 데이터 확보와 재학습 |

**mmWave — 현재 위치.** 데이터 기반인 A단계와 offline 모델 단계인 B단계가 모두 끝났으므로, 세 가지 증거 층 중 데이터 계보와 offline 후보의 두 층이 마련되었다. **완료의 의미.** 지금 모델은 같은 공개 데이터와 고정 규칙으로 다시 만들고 비교할 수 있지만 MR60에서 같은 신호가 들어오는지는 아직 증명되지 않았다. **남은 양.** 센서 자체의 필수 큰 관문은 M-C 실센서 검증과 그 결과를 반영한 최종 lock·통합 준비이며, 이후 세 센서 공통 I단계가 남아 있다. M-D는 반드시 수행하는 단계가 아니라 M-C에서 실제 domain gap, 즉 공개 데이터와 MR60 신호의 의미·분포 차이가 확인될 때만 추가된다. **바로 다음 작업.** 약 20 rpm 관측을 포함한 MR60 raw·phase·presence·timestamp를 고정된 10 Hz, 300샘플, `BPF_ZSCORE` 입력과 대조하고, controlled capture와 Raspberry Pi 실행을 검증해야 한다.

**CO₂ — 현재 위치.** 실제 원본을 복원한 C-A와 offline 후보를 고정한 C-B가 끝났으므로, CO₂도 데이터 계보와 offline 모델의 두 증거 층이 마련되었다. **완료의 의미.** UCI occupancy 데이터에서는 같은 feature, scaler, threshold와 모델을 재현할 수 있지만, 이 결과는 SCD40의 실제 측정 특성이나 CO₂ 안전 경보를 증명하지 않는다. **남은 양.** 필수 큰 관문은 C-C SCD40 검증과 C-E 최종 artifact·통합 준비이며, 그 뒤 공통 I단계가 남아 있다. C-D는 C-C에서 측정 범위, cadence, 결측 또는 환경 차이가 실제로 확인될 때만 수행한다. **바로 다음 작업.** 현재 팀 PR #14의 partial 자료를 출발점으로 센서 초기 안정화, 측정 간격, stale·결측·재연결, 실제 `CO2_slope` 계산과 UCI 대비 분포 차이를 완결해야 한다.

**Thermal — 현재 위치.** T-A0~T-A6 데이터 기반은 끝났지만 새 모델을 비교하는 T-B는 시작 승인을 받지 않았으므로, 세 증거 층 중 데이터 계보 한 층만 마련된 상태이다. **완료의 의미.** 원본 열화상을 섭씨 62×80 frame과 추적 가능한 label·split로 다시 만들 수 있다는 것은 증명했지만, 기존 `HUMAN_FALL` 모델이 이 데이터에 맞거나 실제 낙상을 잘 찾는다는 것은 증명하지 않았다. **남은 양.** Thermal은 세 센서 중 가장 많은 센서별 작업이 남아 있으며, T-B0 승인 검토와 T-B 모델 비교, T-C 실제 장치 검증, T-E 최종 lock·통합 준비를 차례로 통과한 뒤 공통 I단계로 가야 한다. T-D는 앞 단계에서 확인된 데이터 빈틈이 있을 때만 추가한다. **바로 다음 작업.** T-B0에서 섭씨 canonical frame과 기존 0~1 min-max 입력의 관계, TRAIN↔VALIDATION near-duplicate 통제, 독립 최종평가 데이터 확보 방법을 먼저 확정해야 한다.

세 트랙은 독립 파일과 장비를 사용하는 범위에서 병렬로 진행할 수 있다. 즉 mmWave M-C와 CO₂ C-C를 진행하는 동안 Thermal T-B0/T-B를 진행하고, 공용 계약을 읽기 전용으로 대조하는 I-0도 함께 수행할 수 있다. 다만 같은 센서 안에서는 B보다 C를 먼저 하거나, C에서 차이가 확인되지 않았는데 D 재학습을 시작하거나, 실센서 검증 없이 E와 I의 완료를 선언해서는 안 된다.

## 2. 이 중간배포의 목적과 의미

SafeNest가 해결하려는 문제는 센서마다 별도의 값을 얻는 데서 끝나지 않는다. 실제 mmWave 레이더, CO₂ 센서, 열화상 센서가 보내는 데이터를 같은 기준으로 해석하고, 어떤 원본에서 어떤 전처리와 학습을 거쳐 결과가 나왔는지 나중에도 추적할 수 있어야 한다. 기존에는 실행 가능한 모델과 예제 코드가 일부 존재했지만 학습 원본, 데이터 분할, 전처리 통계, 모델 선택 이유가 서로 충분히 연결되지 않았거나 합성 데이터만으로 확인된 경우가 있었다. 이 상태에서는 새 실센서 데이터가 들어올 때 기존 모델과 동일한 기준으로 처리했는지 판단하기 어렵고, 다른 개발자가 같은 모델을 다시 만들거나 결과를 공정하게 검증하기도 어렵다.

이번 작업은 이 문제를 센서별로 나누어 정비했다. 각 트랙의 A단계는 원본의 신원과 사용 조건을 확인하고, 원본을 일정한 형태로 바꾸며, 각 샘플이 어디서 왔는지를 기록하는 데이터 기반 단계이다. 여기서 정규 표현인 canonical data는 서로 다른 원본을 후속 코드가 일관되게 읽도록 정한 표준 데이터 형태이고, provenance는 각 샘플의 원본·구간·라벨·분할·변환 과정을 거꾸로 추적할 수 있게 하는 계보 기록이다. B단계는 이 고정된 데이터 기준 위에서 여러 전처리와 모델을 비교하고, 선택 결과를 경량 실행 형식으로 변환한 뒤 최종 평가와 파일 식별값을 잠그는 offline 모델 단계이다. C단계는 저장된 공개 데이터가 아니라 실제 MR60, SCD40, 열화상 장치와 목표 실행 환경에서 입력 의미와 성능을 다시 확인하는 device-domain 단계이다. 이후 I단계는 이렇게 독립적으로 확인된 센서 결과를 공용 계약과 위험 판단 흐름에 연결하는 통합 단계이다.

따라서 이 중간배포는 세 센서가 모두 제품 수준에 도달했다는 선언이 아니다. 현재까지 재현 가능한 데이터·실험·모델 증거를 고정하고, 담당자가 바뀌어도 다음 검증을 같은 출발점에서 계속할 수 있게 만든 기술 체크포인트이다. mmWave와 CO₂는 실제 공개 데이터에 대한 offline 후보까지 도달했지만 아직 팀의 물리 센서로 검증하지 않았다. Thermal은 실제·합성 원본을 표준화하고 한계를 확인한 A단계까지 끝났으며, 기존 열화상 모델을 새 canonical 데이터에 맞춰 재학습하거나 선택하는 B단계는 아직 승인되지 않았다.

## 3. 시스템 구조와 증거의 경계

세 트랙은 모두 `원본 → 안전한 판독 → canonical 표현 → 고정 분할 → offline 모델 비교 → 물리 센서 검증 → 멀티센서 통합`이라는 같은 구조를 따른다. manifest는 데이터와 모델의 구성·상태를 기계가 읽을 수 있게 기록한 명세 파일이고, checksum은 파일 내용이 한 바이트라도 바뀌면 달라지는 SHA-256 식별값이다. 이 둘을 함께 보존하면 같은 이름의 파일이 조용히 교체되거나 학습과 평가 대상이 바뀌는 문제를 검사할 수 있다. Validator는 이러한 규칙을 독립적으로 다시 확인하는 검사 프로그램이며, 오류나 필수 증거 누락을 정상값으로 대신하지 않고 중단하는 fail-closed 방식으로 동작한다.

증거는 다음 세 종류를 서로 대신할 수 없다. Offline evidence는 저장된 데이터셋, canonical 파일, TFLite 모델, 강건성 시험 또는 mock 실행에서 얻은 결과이다. 여기서 TFLite는 Raspberry Pi 같은 경량 환경에서 실행하기 위한 TensorFlow Lite 모델 형식이고, mock은 실제 센서 대신 정해진 입력을 넣어 프로그램 연결이 작동하는지만 보는 모의 실행이다. Device-domain evidence는 실제 센서와 목표 장치에서 신호 단위, 측정 주기, 누락, 보정, 전처리, 지연 시간을 확인한 결과이다. Integration evidence는 검증된 각 센서 결과가 전체 SafeNest 통신·위험 판단·표시 흐름에서 올바른 시간과 유효성 상태를 유지하는지 확인한 결과이다. Offline 정확도가 좋아도 실제 센서 신호가 학습 입력과 다르면 device-domain 검증을 통과한 것이 아니며, 한 센서가 실제 장치에서 동작해도 전체 시스템 통합을 증명한 것은 아니다.

Standalone 저장소는 AI 데이터, 전처리, 모델, 평가, 위험 로직을 정비하는 작업장이고, 팀 저장소에서는 실제 센서 드라이버가 `devices/<device>/src/`, 공용 인터페이스가 `shared/contracts/`, AI 구성요소가 `ondevice_ai/`에 속한다. 팀 저장소의 열린 CO₂ PR #14, Thermal PR #15, ESP32 통합 PR #12, 실행 패키지 PR #11 및 MR60 원격 분석 branch는 C단계와 I단계에서 사용할 중요한 장치 증거이지만, 아직 이 저장소의 A/B 데이터에 자동 합쳐진 학습 자료는 아니다. 특히 팀의 구형 `ondevice_ai/`는 이번 모델 계보를 입증하는 근거가 아니며, 이관할 때에도 센서 드라이버를 AI 폴더에 중복 복사해서는 안 된다.

## 4. 센서별 개발 과정과 현재 상태

### mmWave: 실제 레이더 데이터의 offline 후보 고정

기존 mmWave 모델은 실행 파일은 있었지만 실제 데이터에서 재현 가능한 학습 계보가 부족하거나 합성 데이터 호환성만 확인된 상태였다. 레이더 신호는 사람마다 파형 특성이 다르므로 같은 사람의 기록이 학습과 평가 양쪽에 들어가면, 모델이 새로운 사람의 호흡 패턴을 이해한 것이 아니라 개인 특성을 기억해 성능이 부풀 수 있다. 이를 막기 위해 A0부터 A6까지 Zenodo DOI `10.5281/zenodo.18599983`의 110명·440개 recording을 확인하고, 10 Hz에서 30초 길이인 300개 샘플 창 530개를 만들었다. Git에서 제외된 원본 `datasets/raw_archives/external_datasets/db_records.zip`의 SHA-256은 `f0bcfdac94f88b43bb34d3da8e8f071a787291f86c97798059b8dbf4d4be08b0`이다. Subject-wise split은 한 사람의 모든 recording과 window를 오직 한 분할에만 두는 방식이며, 77명은 TRAIN, 17명은 VALIDATION, 16명은 LOCKED_TEST에 고정되었다. LOCKED_TEST는 모델 선택이 끝난 뒤에만 여는 최종 평가용 데이터이다. 구조상 window는 358/84/88개이고, 애매한 구간을 제외한 순수 클래스 학습·평가 가능 window는 327/79/75개이다. `AMBIGUOUS` 49개는 삭제하지 않고 계보에는 남겼다.

이 데이터 기반은 `datasets/mmwave/processed/mmwave_canonical_real_v1.npy`와 `datasets/mmwave/splits/mmwave_real_subject_split_v1.json`에 고정되어 있다. 전자는 SHA-256 `c2e2cd1615c7af0f0e21700f291ee12ac0347a9f7fc6ccc9f337433c16868f0e`인 표준 신호 배열이고, 후자는 SHA-256 `a1996ea00a1d5066eae6d25f022d04137085434d4768e27cbebcdad4e0385baa`인 사람 단위 분할 계약이다. 전체 생성과 누락·라벨·분할·checksum 검사는 `datasets/mmwave/manifests/a6_full_conversion/`의 증거와 `scripts/validate_mmwave_full_conversion.py`가 담당한다. APNEA 라벨은 자발적 숨참 구간에서 만든 SafeNest용 APNEA 유사 proxy이며, 임상적 수면무호흡 진단 정답이 아니다.

B단계 M-B0부터 M-B12까지는 이 고정 데이터를 사용해 전처리, 학습 불균형 처리, 모델 구조, 초기화 seed, INT8 변환, 강건성, 실행 경로와 최종 평가를 순서대로 비교했다. 선택된 `BPF_ZSCORE` 전처리는 0.1~0.5 Hz 호흡 대역만 통과시키는 band-pass filter와 TRAIN에서 계산한 평균·표준편차로 값을 맞추는 z-score 정규화를 결합한다. 선택 모델은 `Conv1D/GAP` 구조로, Conv1D는 시간에 따른 짧은 신호 패턴을 찾는 1차원 합성곱이고 GAP는 각 특징의 시간축 평균을 내어 작은 분류 입력으로 만드는 global average pooling이다. 학습은 클래스 가중치를 추가하지 않은 cross-entropy 손실인 `CE_UNWEIGHTED`를 사용했고, INT8 변환 범위를 정하는 대표 입력은 클래스가 균형을 이루도록 120개를 선택했다.

최종 파일은 `models/mmwave/experiments/M-B6_stage_equivalence/M-B3_CONV1D_GAP_BASELINE_seed42_M-B5_CAL_CLASS_BALANCED_120_int8.tflite`이며 SHA-256은 `6dff6aaa72c79d76715d40cf7e32bb1e6cd9b2c2e3ac78eaf2fda737561430c5`, 크기는 22,080 bytes이다. Strict INT8은 입력과 출력뿐 아니라 내부 연산도 8비트 정수 실행 계약을 만족한다는 뜻이며, 입력은 `[1, 300, 1]`, 출력은 `NORMAL`, `RAPID_OR_ABNORMAL`, `APNEA` proxy 세 클래스이다. 이 모델의 상태 `REAL_DATA_OFFLINE_CANDIDATE`는 실제 공개 데이터로 offline 선택과 고정을 끝냈다는 의미이지, MR60BHA2·Raspberry Pi·제품·임상 검증을 마쳤다는 의미가 아니다. 선택과 lock의 현재 근거는 `datasets/mmwave/manifests/M-B11_artifact_lock/`과 `datasets/mmwave/manifests/M-B12_phase_b_offline_final/phase_b_closure_summary.json`이며, 사람이 읽는 요약은 `docs/reports/20260813_Cursor_M-B12_mmWave_Phase_B_Offline_Final_Report_01.md`에 있다.

모델 선택에 사용한 VALIDATION Macro F1은 seed 42에서 0.663708이었다. Macro F1은 클래스별 정밀도와 재현율을 함께 반영한 F1을 구한 뒤 각 클래스에 같은 비중을 주어 평균낸 값이므로 큰 클래스 하나의 성능만으로 전체 점수가 좋아지는 일을 줄인다. 그러나 최종 결과로 보고해야 하는 수치는 별도의 최종 평가 Macro F1 0.494836과 정확도 0.56이다. 클래스별로 NORMAL 재현율은 0.20, RAPID_OR_ABNORMAL 재현율은 0.421053, APNEA proxy 재현율은 0.935484였고, APNEA proxy 오탐률은 0.522727이었다. 즉 숨참 proxy를 놓치는 비율은 낮았지만 정상 또는 다른 이상을 APNEA로 과다 판정하는 문제가 컸다. 피험자별 Macro F1 중앙값은 0.388888, 최저값은 0.095238이어서 사람 간 편차도 크다. seed 44의 VALIDATION Macro F1이 0.329107까지 내려간 사실은 초기 가중치에 따른 민감성도 남아 있음을 보여준다. 선택 모델은 같은 최종 모집단에서 구형 v0.1 호환 기준 0.166667과 합성 학습 v0.2 호환 기준 0.391074보다 높았지만, 이 비교만으로 물리 센서 사용 가능성을 결론낼 수 없다.

최종 holdout 처리에는 반드시 이어받아야 할 예외가 있다. LOCKED_TEST의 전체 구조적 모집단은 88개였지만 순수 클래스 supervised 평가 대상은 75개였고, 최초 harness가 75개만 반환하도록 설계된 accessor에 88개를 잘못 기대해 검사 단계에서 중단되었다. 이때 payload release는 한 번 발생했지만 모델 inference, 예측값, 성능 계산은 모두 0회였다. 그래도 holdout 내용이 한 번 공개되었으므로 더 이상 pristine, 즉 한 번도 열리지 않은 최종 시험이라고 부를 수 없다. 독립 검토 후 제한적 재사용 예외를 만들고 접근 전 recovery harness를 고정했으며, 이후 정확히 한 번의 recovery access에서 75개×3개 모델인 225회 추론을 수행했다. 재실행은 없었다. 따라서 최종 명칭은 `REUSED_LOCKED_TEST_AFTER_PREINFERENCE_STRUCTURAL_ABORT`를 그대로 유지해야 하며, 새로운 선택이나 사후 튜닝을 위해 LOCKED_TEST 또는 recovery를 다시 열어서는 안 된다.

다음 단계는 M-C 물리 장치 도메인 검증이다. 팀 자료에 있는 약 20 rpm 관측과 저신호대잡음비·입력 유효성 문제 분석은 조사 출발점일 뿐, 새 offline 후보가 그 현상을 이미 설명하거나 해결했다는 증거가 아니다. M-C에서는 MR60이 내보내는 `breath_phase`의 단위, 측정 주기, 끊김, presence 상태, window 구성과 실제 전처리가 고정된 10 Hz·300샘플·`BPF_ZSCORE` 입력 계약과 같은지 먼저 비교해야 한다. 그 차이가 수치로 확인된 뒤에만 MR60 전용 adapter, 추가 수집 또는 gap 기반 재학습을 결정할 수 있다.

### CO₂: UCI 원본에서 occupancy 후보까지의 재현 가능한 계보

기존 CO₂ runtime 모델과 scaler는 어떤 원본과 분할로 학습되었는지 충분히 확인되지 않았고, manifest상 검증 범위도 합성 데이터에 머물렀다. Scaler는 서로 단위와 범위가 다른 입력을 모델이 비교할 수 있도록 크기를 맞추는 변환이며, 어느 데이터로 그 통계를 계산했는지가 기록되지 않으면 평가 데이터의 정보가 학습에 섞였는지 확인하기 어렵다. 새 C-A0~C-A6은 UCI Occupancy Detection Dataset, DOI `10.24432/C5X01N`의 원본 archive에서 20,560개 관측을 재구성하고, 원본 시각·파일·행·라벨과 후속 feature를 1:1로 추적하게 만들었다. 원본 archive는 `datasets/raw_archives/external_datasets/occupancy+detection.zip`에 있으나 Git에 포함하지 않으며, SHA-256은 `4ae3f46aa98eedff564a9f6924d1635173e2fd2c816004342a9be93076d3a81a`이다. CC BY 4.0 출처·라이선스와 파일 동일성의 근거는 `datasets/co2/manifests/c_a6_final_integrity_lock/full_chain_integrity_summary.json`에 고정되어 있다.

무작위 행 분할 대신 서로 떨어진 원본 시간 구간을 보존했다. `datatraining.txt`는 TRAIN, `datatest.txt`는 VALIDATION, `datatest2.txt`는 LOCKED_TEST이고, slope 계산 초기 3행씩을 제외한 모델 가능 표본은 각각 8,140, 2,662, 9,749개이다. Temporal block split은 시간상 분리된 덩어리를 그대로 학습·검증·최종시험 역할로 쓰는 방법으로, 가까운 시점의 거의 같은 환경값이 양쪽에 섞이는 위험을 줄인다. 다만 원본에는 사람이나 독립 세션 식별자가 없어 group independence, 즉 서로 독립적인 사람·세션 단위 분리를 했다고 증명할 수는 없다. 표준 표본과 역할은 `datasets/co2/manifests/c_a5_canonical_samples/canonical_source_samples.jsonl` 및 `split_membership_manifest.json`에 기록되고, A단계 전체 연결은 `scripts/validate_co2_final_integrity.py`가 확인한다.

선택 입력 순서는 `CO2`, `Temperature`, `Humidity`, `CO2_slope` 네 값이다. `CO2_slope`는 현재 값이 과거 150초 전후의 값보다 얼마나 빠르게 변했는지를 실제 경과시간으로 나눈 ppm/min 특징이며, 미래 값을 보지 않는 causal `ENDPOINT_H150` 방식이다. 90초보다 긴 공백 뒤에는 이력 구간을 다시 시작하고, 각 파일의 초기 3개씩 총 9개 warmup 표본은 slope가 준비되지 않은 것으로 남긴다. 이 특징은 UCI 기록에서 검증된 offline 계산이며, 실제 SCD40의 측정 간격·결측·보정과 동일하다는 뜻은 아니다. 목표 0은 `VACANT`, 1은 `OCCUPIED`로 방의 재실 여부만 나타내며, CO₂ 위험 농도나 SafeNest 전체 위험도를 뜻하지 않는다. 원본에 있던 Light와 HumidityRatio는 비교에는 사용되었지만 선택 후보 입력에서는 제외했다.

C-B0~C-B5에서는 logistic regression, random forest, 작은 neural network들을 다섯 seed에서 같은 VALIDATION 조건으로 비교했다. 선택된 `LINEAR_LOGISTIC`은 네 feature의 가중합을 occupancy 확률로 바꾸는 단순 선형 분류기이며, 복잡한 모델보다 재현성과 검증 성능의 균형이 좋았다. TRAIN에서만 StandardScaler를 맞추고, 적은 `OCCUPIED` 사례를 학습 중 같은 수로 뽑아 주는 `BALANCED_RANDOM_OVERSAMPLE`을 사용했으며, occupancy 판정 threshold는 0.58로 고정했다. Threshold는 출력 확률이 어느 값 이상일 때 `OCCUPIED`로 볼지를 정하는 경계값이다.

선택 가중치와 bias는 새로 재학습하지 않고 동일한 Keras Dense 층으로 옮긴 뒤 Float TFLite와 full-integer INT8 TFLite로 변환했다. 이 exact bridge는 알고리즘을 바꾸지 않고 실행 형식만 옮겼음을 검사하기 위한 절차이다. 최종 모델 `models/co2/candidates/c_b4/full_integer_int8.tflite`의 SHA-256은 `bb2ed28533bca75d4fa3d06348e017c506df47d7c34b29574b77f70b6b386816`, 크기는 1,544 bytes이며, `[1, 4]` INT8 입력에서 `[1, 1]` INT8 occupancy 확률을 낸다. INT8과 기준 모델은 VALIDATION 2,662개 중 7개, 즉 0.263%에서만 최종 클래스가 달랐고 변환 동등성 gate를 통과했다. 다만 일부 입력이 INT8 표현 범위 끝에 닿는 saturation이 VALIDATION에서 10,648개 원소 중 3개, LOCKED_TEST에서 38,996개 중 159개 관측되었으므로 장치 입력 범위를 다시 확인해야 한다.

C-B5는 VALIDATION만으로 drift와 잡음에 대한 stress test를 끝낸 다음 후보를 동결하고 LOCKED_TEST를 한 번만 평가했다. 최종 상태는 `FINAL_OFFLINE_UCI_CANDIDATE_LOCKED`이고, 평가 후 추가 튜닝은 없었다. LOCKED_TEST 9,749개에서 정확도는 0.754129, balanced accuracy는 0.728653, Macro F1은 0.685658, `OCCUPIED` 재현율은 0.684751, `OCCUPIED` F1은 0.538950이었다. Balanced accuracy는 `VACANT`와 `OCCUPIED` 재현율을 같은 비중으로 평균낸 값이다. VALIDATION Macro F1 0.908609보다 최종 결과가 크게 낮아 시간 구간이 바뀌었을 때의 일반화 차이가 분명하다. VALIDATION 입력에 +1 ppm/min 선형 drift를 준 진단에서는 Macro F1이 약 0.266으로, -2 ppm/min에서는 `OCCUPIED` 재현율이 약 0.112로 내려갔다. 이 값은 취약 방향을 찾는 인공 stress 결과이지 SCD40의 실제 오차 사양이나 원인 확정이 아니다.

최종 후보의 metadata와 lock은 `models/co2/candidates/c_b5/final_candidate_metadata.json` 및 `datasets/co2/manifests/c_b5_robustness_final_lock/`에 있다. 반면 `models/co2/co2_occupancy_int8_v0.1.0.tflite`와 기존 scaler는 세 입력을 쓰는 과거 runtime 자산으로, 새 네 입력 후보와 동일한 모델이 아니며 자동 교체되지 않았다. `models/model_manifest.json`도 아직 새 B5 후보를 운영 모델로 승격하지 않은 과거 runtime registry이다. 다음 C-C에서는 팀 PR #14의 SCD40 자료를 사용해 실제 측정 주기, 초기 안정화, 결측, stale 값, 재연결, 환경 변화와 slope 계산을 확인하고 UCI 입력 분포와 비교해야 한다. 현재 열린 PR #14에는 기본 연결 확인 30/30 valid, 재시도한 baseline 300/300 valid, 호기 상승·복귀 시험 360개 중 329개 valid와 8.61% 결측이 기록되어 있으나, 센서를 분리한 60초 원시 시험은 아직 검증되지 않아 전체 판정도 `PARTIAL`이다. 여기서 stale은 새 측정이 오지 않았는데 이전 값이 계속 최신값처럼 남는 상태이다. SCD40 검증 전에는 occupancy 후보를 CO₂ 안전 경보 또는 배포 후보로 부를 수 없다.

### Thermal: 모델 재학습 전 데이터 의미와 물리 단위 확정

Thermal에는 이미 `models/thermal/thermal_fall_int8_v0.1.0.tflite`와 inference 코드가 있었지만, 그 모델이 받은 62×80 배열이 어떤 원본의 온도 단위와 화면 방향에서 만들어졌는지, `HUMAN_FALL`이 실제 낙상 사건을 뜻하는지, train과 validation이 독립적인지 충분히 증명되지 않았다. 그래서 T-A0~T-A6의 목표는 성능을 높이는 재학습이 아니라, 열화상 한 장의 물리적 의미와 출처를 고정하여 잘못된 전처리나 라벨 해석으로 학습을 시작하지 않게 하는 것이었다.

선택 데이터는 SDT Dataset, DOI `10.5281/zenodo.4124309`이다. 저장소 증거는 Zenodo metadata의 CC BY 4.0 표기와 배포 설명의 비상업 연구 제한이 충돌한다고 기록하므로, 현재는 더 엄격한 공통 조건인 비상업 연구·출처 표기를 적용한다. 원본 재배포나 상업적 사용은 별도 조건 검토가 필요하다. Raw reader인 `datasets/thermal/raw_reader.py`는 480×640 `uint16` 열화상 값을 Kelvin의 100분의 1 단위로 읽고 `(raw - 27315) / 100`으로 섭씨를 복원한다. Canonical converter인 `datasets/thermal/canonical_converter.py`는 좌우 10 pixel씩을 제거한 `[10, 0, 630, 480]` 영역을 bilinear, 즉 주변 네 pixel을 거리 비율로 섞는 보간법으로 62×80에 축소한다. 이 `G1_FIXED_ASPECT_CROP_BILINEAR` 계약은 회전·반전 없이 섭씨 `float32`를 보존하며, A단계에서는 프레임별 최솟값·최댓값으로 0~1을 만드는 min-max 정규화를 하지 않는다. 정확한 규칙은 `datasets/thermal/manifests/T-A2_geometry_calibration_canonical_frame/selected_geometry_profile.json`에 있다.

T-A6은 공식 source partition을 그대로 유지해 합성 TRAIN 32,000장, 합성 VALIDATION 8,000장, 실제 `REAL_EVAL_DEVELOPMENT` 8,000장, 총 48,000장을 변환했다. 실패·제외·경고는 모두 0이었다. 실제 test는 이미 개발 과정에서 확인했으므로 새 이름만 붙여 pristine LOCKED_TEST로 되돌릴 수 없다. 또한 원본에는 subject, session, sequence, event, timestamp 증거가 없어 사람 단위 일반화나 시간에 따른 낙상 사건 탐지를 검증할 수 없다. 파일명과 index도 시간 순서로 해석해서는 안 된다. Source label은 `LYING`, `SITTING`, `STANDING`, `EMPTY_ROOM`이고, 현재 runtime 호환을 위해 `EMPTY_ROOM→NOT_HUMAN`, `SITTING/STANDING→HUMAN_NORMAL`, `LYING→HUMAN_FALL`로 연결하지만, `LYING`은 누워 있는 한 장면에서 만든 자세 proxy일 뿐 실제 낙상 발생 정답이 아니다.

48,000장의 compact evidence는 `datasets/thermal/manifests/T-A6_execution_result/`에 있고, 큰 canonical 배열과 행별 provenance는 용량 때문에 Git에 포함하지 않고 logical artifact 이름과 SHA-256만 registry에 보존한다. TRAIN 배열 SHA-256은 `749c847fc9ab50ea5eee8827f0d47b5ebaa48165732a382c59f8b96c565b9d93`, VALIDATION은 `5d16451702c1bccfa945d9188d9b29a26ce11c8b33bf7a0dfbb25bfa86d74610`, 실제 개발 평가는 `cd696e68aeec063cbc8185719b4f4dad3d038cb3d28eec0d3701b8311e4ad8f1`이다. 재현 실행은 `scripts/run_thermal_t_a6_colab.py`, compact 증거 검사는 `scripts/validate_thermal_t_a6_stage2.py`, 전체 predecessor 연결 검사는 `scripts/validate_thermal_t_a6.py`가 담당한다. `datasets/thermal/processed_thermal_80x62.npz`는 출처가 혼합된 legacy 파일로 `LEGACY_NON_AUTHORITATIVE_NOT_USED`이며 새 학습의 근거가 아니다.

Exact duplicate, 즉 byte 수준으로 같은 cross-role frame은 0개였지만, 모양과 온도가 매우 가까운 near-duplicate를 정해진 기준으로 찾은 결과 72,981쌍이 확인되었다. 그중 58,467쌍은 TRAIN 내부이고 14,514쌍은 TRAIN과 VALIDATION 사이였으며, 2,004개 샘플이 확인된 cluster에 속했다. 이 검사는 5,945,736개 후보쌍을 생성했지만 후보 목록이 제한을 넘어 잘렸고, profile 자체도 `DETERMINISTIC_SCREENING_NOT_EXHAUSTIVE`이므로 모든 유사쌍을 완전 탐색했다고 주장할 수 없다. 이 중복 구조는 향후 T-B 모델 성능이 비정상적으로 높아지는지 해석할 때 반드시 고려해야 한다.

기존 thermal model은 SHA-256 `5b56da8d127ccef85f30b6459cc0cfe2d86490e41f3caa5bd2a7b70bbc46ae84`, 크기 318,184 bytes인 `[1, 62, 80, 1]` INT8 입력·3클래스 출력 자산이다. 그러나 `models/model_manifest.json`은 이 모델의 검증 상태를 `CONFIRMED_SYNTHETIC_ONLY`로 기록하고, `inference/thermal_interpreter.py`는 0~1 밖의 값을 받으면 프레임별 min-max를 적용한다. 새 canonical 데이터는 물리적 섭씨 값을 그대로 유지하므로 두 전처리 계약이 자동으로 일치하지 않는다. 이 때문에 현재 기계 증거 `datasets/thermal/manifests/T-A6_execution_result/execution_summary.json`은 `T_A6_FULL_COMPLETE_WITH_LIMITATIONS`이면서 `t_b_authorized: false`이다. 즉 Thermal A단계는 완료되었지만 기존 모델 성능이 새 데이터에서 입증된 것도, T-B 학습을 바로 시작해도 된다는 승인도 아니다. 다음 작업은 별도의 T-B0 검토에서 canonical 섭씨 입력을 어떤 TRAIN 전용 정규화로 모델에 넣을지, near-duplicate와 실제 개발 평가를 어떻게 다룰지, 공정한 평가 세트를 새로 확보할지를 먼저 확정하는 것이다.

팀의 현재 열린 PR #15는 실제 full-frame을 62×80으로 받아 TFLite와 fail-closed 경로를 거쳐 UDP로 전송한 증거를 담고 있으며, 이전 TCP 경로에서 전원 불안정과 655.3°C 비정상값이 발생해 UDP로 전환한 이력도 보존한다. 반면 열린 PR #12는 약 70% pixel이 고정되거나 무효였던 조건에서 full-frame 전송을 끄고 최고 온도 하나인 `thermal_max_c`만 보낸다. 따라서 두 경로는 서로 다른 장치 계약이다. 또한 Thermal-90, MI48, Thermal-44라는 센서 명칭이 자료마다 섞여 있다. T-C 전에 실제 모델명, packet 단위, raw 값의 온도 변환, 62×80 방향, calibration, invalid pixel 정책을 하나의 provenance로 맞춰야 하며, 장치 통신이 성공했다는 사실을 낙상 모델의 일반화 성능으로 바꾸어 말해서는 안 된다.

## 5. 센서 간 상태와 현재 artifact inventory

세 센서는 동일한 A/B/C 절차를 따르지만 현재 성숙도는 다르다. 아래 표의 “고정”은 해당 파일과 선택 규칙을 checksum으로 보존했다는 뜻이며, 실제 장치나 제품 검증을 뜻하지 않는다.

| 센서 | 데이터·계보 상태 | 모델·알고리즘 상태 | offline 평가와 lock | 실제 장치 상태 | 통합 상태 | 허용된 다음 단계 |
| --- | --- | --- | --- | --- | --- | --- |
| mmWave | A0~A6 완료, 사람 단위 77/17/16 분할 고정 | M-B0~M-B12 완료, seed42 strict-INT8 후보 선택 | `REAL_DATA_OFFLINE_CANDIDATE`; 최종 Macro F1 0.494836, 비-pristine 재사용 예외 포함 | MR60 미검증, 팀 약 20 rpm 자료는 조사 입력 | mock wiring 외 실통합 미검증 | M-C 장치 신호·전처리·실행 검증 |
| CO₂ | C-A0~C-A6 완료, UCI 시간 block과 20,560개 계보 고정 | C-B0~C-B5 완료, logistic INT8 후보 선택 | `FINAL_OFFLINE_UCI_CANDIDATE_LOCKED`; LOCKED_TEST 1회, Macro F1 0.685658 | SCD40 미검증, 팀 PR #14는 partial evidence | occupancy 출력의 공용 위험계약 미검증 | C-C SCD40 cadence·결측·slope·분포 검증 |
| Thermal | T-A0~T-A6 완료, 48,000장 변환과 한계 감사 | 새 T-B 모델 없음; 기존 runtime 모델은 합성 검증·전처리 불일치 | 모델 성능 lock 없음, pristine LOCKED_TEST 없음, `t_b_authorized: false` | full-frame·scalar 경로와 센서 명칭 미조정 | frame contract와 공용 provider 미조정 | T-B0 학습·평가 protocol 승인 검토 후 T-B, 이후 T-C |

현재 모델 파일의 역할도 구분해야 한다. 새 mmWave와 CO₂ 파일은 offline 비교가 끝난 선택 후보이지만 아직 `models/model_manifest.json`의 운영 항목으로 승격되지 않았다. Thermal에는 새 A단계에서 만든 모델이 없고 기존 자산만 있다.

| Artifact | 입력과 출력 | 현재 역할 |
| --- | --- | --- |
| `models/mmwave/experiments/M-B6_stage_equivalence/M-B3_CONV1D_GAP_BASELINE_seed42_M-B5_CAL_CLASS_BALANCED_120_int8.tflite` | 300개 호흡 신호 → NORMAL/RAPID/APNEA proxy | 선택·고정된 실제 공개 데이터 offline 후보. MR60 deployment 모델은 아님 |
| `models/mmwave/mmwave_resp_int8_v0.1.0.tflite` | 300개 호흡 신호 → 3클래스 | 역사적 호환 기준. 같은 최종 모집단에서 class collapse가 확인되어 선택 후보와 동등하지 않음 |
| `models/mmwave/mmwave_resp_int8_v0.2.0_candidate.tflite` | 300개 호흡 신호 → 3클래스 | 합성 학습 호환 기준. 실제 장치 성능 근거가 아님 |
| `models/co2/candidates/c_b4/full_integer_int8.tflite` | CO₂·온도·습도·과거 기반 slope 4개 → occupancy 확률 | 선택·고정된 UCI offline 후보. SCD40·안전경보 검증 전 |
| `models/co2/co2_occupancy_int8_v0.1.0.tflite` | 과거 3-feature 계약 → VACANT/OCCUPIED | 학습 계보가 확인되지 않은 기존 runtime 자산. 새 B5 후보로 자동 교체되지 않음 |
| `models/thermal/thermal_fall_int8_v0.1.0.tflite` | 정규화된 62×80 frame → NOT_HUMAN/HUMAN_NORMAL/HUMAN_FALL | 합성 데이터만 확인된 기존 runtime 자산. 섭씨 canonical 입력과의 전처리 일치 및 실제 낙상 성능 미검증 |

## 6. 알려진 한계와 변경하면 안 되는 인수인계 경계

중간배포 이후 담당자는 성능 숫자보다 먼저 그 숫자가 허용하는 주장의 범위를 보존해야 한다. mmWave의 APNEA는 임상 라벨이 아니고, CO₂의 OCCUPIED는 위험 농도가 아니며, Thermal의 LYING은 낙상 사건이 아니다. Mock 실행 성공은 코드 연결을 증명할 뿐 실제 센서 정확도를 증명하지 않는다. Mac에서 측정한 짧은 지연 시간도 Raspberry Pi 지연 시간으로 바꾸어 보고할 수 없다.

데이터 경계도 고정되어야 한다. mmWave의 subject split과 선택 전처리는 다시 섞지 않고, 비-pristine 최종평가 명칭과 접근 이력을 숨기지 않는다. CO₂의 LOCKED_TEST는 이미 한 번 평가되었으므로 모델·threshold·feature를 그 결과에 맞춰 다시 선택하지 않는다. Thermal은 공식 TRAIN/VALIDATION/REAL_EVAL_DEVELOPMENT 역할을 무작위로 재분할하거나 실제 개발 평가를 LOCKED_TEST로 승격하지 않으며, 확인된 TRAIN↔VALIDATION near-duplicate와 group provenance 부재를 계속 보고한다. 새로운 독립 평가가 필요하면 기존 파일의 이름을 바꾸는 대신 출처와 분리 기준이 검증된 새 데이터를 확보해야 한다.

Artifact 경계에서는 선택 모델, scaler, feature 순서, class map, checksum, 전처리 profile과 결과 manifest를 하나의 묶음으로 다룬다. 모델 파일만 복사하면 같은 추론이 재현되지 않는다. `models/model_manifest.json`의 과거 `deployment_allowed` 필드는 현재 A/B/C 증거보다 우선하지 않으며, 새 후보를 runtime 기본값으로 승격하려면 별도 통합 변경과 회귀검증이 필요하다. 큰 raw archive와 Thermal canonical 배열은 Git에서 제외된 것이 정상이며, compact manifest의 logical path와 checksum으로 존재와 동일성을 확인한다. `archive/version_snapshots/`는 역사 자료이므로 active 코드나 모델을 자동 탐색하는 경로가 아니다.

팀 저장소로 이관할 때에는 검토된 standalone commit의 Git-tracked active 파일만 `ondevice_ai/`에 옮긴다. `.git/`, raw dataset, local hardware bundle, cache, release ZIP, standalone `archive/`를 함께 보내지 않는다. 팀의 `devices/` 구현과 `shared/contracts/`를 AI 폴더의 센서 mock·adapter로 덮어쓰지 말고, 충돌 파일은 replace·merge·preserve·relocate·retire 중 하나로 먼저 분류한다. 입력이 없거나 stale·NaN·invalid인 상황을 정상값 0으로 바꾸지 않는 fail-closed 의미를 유지하고, device driver나 팀 threshold 변경은 해당 소유자의 별도 검토를 받아야 한다.

## 7. 다음 개발 절차와 중간배포 준비 판정

세 트랙의 다음 일은 독립 파일과 장비가 준비되는 범위에서 병렬로 진행할 수 있지만, 각 센서 안에서는 증거 순서를 건너뛰면 안 된다. mmWave는 M-C에서 MR60 raw/phase와 고정 offline 입력을 대응시키고 controlled capture, domain-gap 분석, Raspberry Pi 실행을 수행한다. CO₂는 C-C에서 SCD40의 cadence, warmup, 보정, 결측·stale·reconnect, slope 계산과 UCI 분포 차이를 측정한다. Thermal은 바로 재학습하지 않고 먼저 T-B0에서 Celsius canonical과 기존 0~1 runtime 전처리의 관계, 중복 통제, 새로운 공정 평가 세트와 모델 비교 protocol을 승인한 뒤 T-B를 시작하고, 후보가 고정된 후에 실제 장치 T-C로 간다.

동시에 I-0에서는 standalone provider, 팀 `devices/`, `shared/contracts/`, packet timestamp와 validity 의미를 읽기 전용으로 대조할 수 있다. 다만 센서별 C단계가 끝나기 전에 전체 위험 판단의 정확도를 주장하거나, 열린 팀 PR의 부분 결과를 병합 완료·장치 검증 완료로 간주해서는 안 된다. 추가 데이터셋과 재학습은 “데이터가 많으면 좋다”는 이유가 아니라 M-C/C-C/T-C에서 확인된 신호 범위, 사람 다양성, 환경, 누락, 자세·event 라벨의 구체적 빈틈을 채우는 방향으로 결정한다.

현재 판정은 다음과 같다. mmWave는 M-B12의 offline 중간배포 checkpoint로 사용할 수 있지만 `Phase_B_release_ready`와 제품 배포는 false이고 formal Git tag나 GitHub Release도 없다. CO₂는 B5 UCI offline 후보가 잠겼지만 SCD40·안전·통합 검증 전이다. Thermal은 A6 데이터 기반이 `FULL_AUDIT_COMPLETE_WITH_LIMITATIONS`로 완료되었으나, 최신 validator가 명시한 대로 T-B authorization은 false이다. 제공된 Thermal 인수인계 문구 중 `YES_WITH_LIMITATIONS`라는 표현은 현재 기계 증거와 충돌하므로 채택하지 않았다. 세 트랙을 함께 묶은 이번 산출물은 재현 가능한 중간 인수인계에는 적합하지만, 실센서 배포·Raspberry Pi 성능·임상 또는 안전 성능·멀티센서 통합 완료를 선언하는 release는 아니다.
