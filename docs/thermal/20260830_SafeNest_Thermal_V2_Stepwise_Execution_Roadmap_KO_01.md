# SafeNest Thermal V2 — 단계별 순차 실행 로드맵

- Document ID: THERMAL_V2_STEPWISE_EXECUTION_ROADMAP_KO_01
- Date: 2026-08-30
- Repository: sheepmeat/test
- Branch: thermal-v2/stepwise-execution
- Scope: standalone Thermal V2 evidence completion through G5
- Authority: 20260830_SafeNest_Thermal_V2_Master_Execution_Map_01.md
- Initial roadmap base commit: 25863118c06b8c065f4aa2e8d3c85cc9b4799a6a

## CURRENT_NEXT_STEP

~~~text
CURRENT_PHASE: TV2-D1
CURRENT_STEP: TV2-D1.2
CURRENT_STATUS: NEXT
NEXT_STEP: TV2-D1.2
TRAINING_AUTHORIZED: NO
LAST_COMPLETED_REPORT: docs/reports/20260830_Codex_Thermal_V2_TV2-D1.1_Execution_Report_KO_01.md
LAST_COMMIT: dd945c07e61e7235a80e86d681fb8f7038496b56
~~~

LAST_COMMIT is the clean origin/main base immediately before this stepwise
roadmap. The roadmap commit is bootstrap delivery evidence; after the first
atomic step, this field must point to the previous step's delivery commit.

## 1. Purpose

이 문서는 SafeNest Thermal V2의 실행 순서를 evidence-first 방식으로
고정한다. 목표는 G0 이후의 증거를 충분히 작은 atomic step으로 세분화하여,
사용자가 매번 CURRENT_NEXT_STEP에 지정된 단계 하나만 실행하도록 하는
것이다.

~~~text
repository evidence
→ source / license / provenance contract
→ representation / label / split contract
→ G1 data-model contract
→ Candidate A/B float evidence
→ common offline evaluation
→ G5 standalone prototype artifact
→ Team repository application later
→ Integration / Pi / device-domain validation deferred
~~~

이 문서는 과학적 최종 모델 선정, production 교체, 실제 낙상·안전
성능의 증명서가 아니다. HUMAN_FALL_PROXY는 이 로드맵 전체에서
fall-compatible posture/event proxy로만 취급한다.

## 2. Current Verified State

### 2.1 Git and repository baseline

- 작업 저장소는 AGENTS.md와 git rev-parse --show-toplevel로 확인한
  sheepmeat/test checkout이다. 물리 디렉터리명으로 저장소 정체성을
  추정하지 않는다.
- 최초 진입 시 main의 작업 트리는 clean이었다.
- origin을 fetch한 뒤 local main은 origin/main으로 fast-forward 되었고,
  다시 clean임을 확인했다.
- thermal-v2/stepwise-execution은 동일 이름의 local/remote branch가
  없을 때 main에서 새로 생성했다. 기존 branch를 삭제하거나 재생성하지
  않았다.
- 현재 모든 변경은 이 branch에서만 수행한다. Team repository와
  Integration repository에는 branch, commit, push, PR을 만들지 않는다.

### 2.2 Evidence status reconciliation

Master Map의 구조와 ID는 canonical로 보존한다. 아래 Resolved working
status는 Master Map, 최신 구체 보고서, 실제 artifact의 차이를 이번
순차 실행에서 사용하는 해석이다. 어느 상태도 근거 없이 상향하지 않는다.

| Node | Master Map status | Latest repository evidence | Resolved working status | Reason / authority |
|---|---|---|---|---|
| G0 | PASS | Master Map이 T-V2-G0 CURRENT STATE VERIFIED로 기록 | DONE / PASS | baseline, historical evidence, known gap이 Control-Tower map에 기록됨 |
| TV2-D0 | ACTIVE | D0 report: PASS_WITH_LIMITATIONS; five serious leads와 D1 order 기록 | DONE_WITH_LIMITATIONS | discovery operation은 보고서로 완료되었으나 Map node text는 active임. D1이 후속 검증 |
| TV2-H0 | ACTIVE | H0 report: PASS_WITH_LIMITATIONS; NORMAL→FALL_PROXY=174/4000 및 missing taxonomy 확인 | DONE_WITH_LIMITATIONS | audit operation은 완료되었으나 semantic hard-negative subset 자체는 아직 불가 |
| GEO | ACTIVE | G1 foundation: READY_WITH_LIMITATIONS; T-A2 profile와 V2 proposal 존재 | ACTIVE / REVIEW_PENDING | Thermal-44 equivalence와 source별 mapping은 아직 review 대상 |
| PRE | ACTIVE | G1 foundation: P1 shared proposal READY_WITH_LIMITATIONS | ACTIVE / REVIEW_PENDING | P1은 제안이지 frozen contract가 아님 |
| SPLIT | ACTIVE | G1/T-A5: official partition preservation, subject identity limitation, no pristine holdout | ACTIVE / REVIEW_PENDING | D1-D3 source grouping evidence가 추가되어야 G1을 닫을 수 있음 |
| LABEL | ACTIVE | G1/H0: 3-class proxy와 static/event boundary proposal | ACTIVE / REVIEW_PENDING | external source별 mapping과 ambiguity가 아직 미확정 |
| G1 | PLANNED / NOT_STARTED | G1 report: G1_READY_PENDING_D0_D3; G1 PASS 아님 | PLANNED / BLOCKED_BY_D1_D2_D3 | D0-D3와 Control-Tower contract review가 선행되어야 함 |
| Candidate A | PLANNED / REQUIRED | A0: PASS_WITH_LIMITATIONS, family REVISED_COMPACT_CONVENTIONAL_CNN | PLANNED / FAMILY_PROPOSED | exact head는 G2에서 결정; training evidence 없음 |
| G2 | PLANNED | A0: A_RECOMMEND_REVISED_SMALL_CNN | PLANNED | G1 PASS 이후 train-ready contract를 만들고 검증해야 함 |
| Candidate B | CONDITIONAL | A0: B_JUSTIFIED; Master Map은 conditional | CONDITIONAL / NOT_EVALUATED | distinct second hypothesis를 G3에서 승인하거나 skip해야 함 |
| G3 | NOT_EVALUATED | A0 recommendation only; no G3 decision artifact | CONDITIONAL | 모델 수를 늘리는 목적의 B는 금지 |
| G4 | PLANNED | no V2 candidate comparison | PLANNED | common protocol, C1 control, A/B evidence가 필요 |
| G5 | PLANNED | no V2 standalone artifact | PLANNED | G4 이후에만 artifact readiness를 평가 |
| Team Application | PLANNED / later | Master Map separates it from standalone | DEFERRED | 현재 roadmap의 endpoint는 standalone G5 |
| Integration / Pi / device-domain | DEFERRED | Master Map and AGENTS boundary | DEFERRED | 현재 V2 development prerequisite가 아님 |

### 2.3 Status vocabulary

| Status | Meaning in this roadmap |
|---|---|
| DONE | 해당 operation 또는 gate의 repository evidence가 완료됨 |
| ACTIVE | evidence/contract work가 진행 중이거나 review pending |
| NEXT | 사용자가 다음 실행에서 수행할 단 하나의 atomic step |
| PLANNED | 선행 gate 이후 수행하도록 승인된 후속 step |
| CONDITIONAL | G3/G5 등 별도 decision 또는 authorization이 필요한 path |
| BLOCKED | evidence, access, license, hardware, 또는 contract 때문에 진행 중단 |
| DEFERRED | 현재 standalone V2 scope 밖이며 후속 지시가 필요한 path |

`DONE_WITH_LIMITATIONS`, `PASS_WITH_LIMITATIONS`, `BLOCKED_ACCESS`,
`BLOCKED_LICENSE`, `BLOCKED_HARDWARE`, `SKIPPED_NOT_JUSTIFIED`는 위 기본
상태에 붙는 구체 qualifier다. 예를 들어 최신 B6R-P3는
`BLOCKED_HARDWARE`이지만 V2 G1의 blocker로 자동 전파되지 않는다.

### 2.4 Verified model and failure baseline

현재 V2 comparison reference는 역사적인 T-B CNN이 아니라 B6R public SDT
pooled-MLP이다.

~~~text
model_id: thermal_public_sdt_pooled_mlp_fp32_tflite_v1
architecture: PUBLIC_SDT_ADAPTIVE_POOL_MLP_V1
input: [1, 62, 80, 1] float32
parameters: 2,691
data: PUBLIC_SDT_48000_THERMAL_ONLY_V1
preprocessing: 480×640 → bilinear 62×80 → per-frame min-max → adaptive pool 8×10 → MLP
DEVELOPMENT accuracy: 0.907000
DEVELOPMENT macro F1: 0.901326741104394
HUMAN_NORMAL → HUMAN_FALL_PROXY: 174 / 4,000 = 4.35%
LOCKED_PUBLIC_TEST: array open 0, sample read 0, metric false
~~~

H0는 이 failure signal이 public DEVELOPMENT에서 관찰됨을 확인했지만,
174개 row를 SITTING/STANDING, low centroid, occlusion, orientation 등으로
분해할 수 없다고 명시했다. synthetic masking/shift는 software stress
hypothesis일 뿐 semantic hard-negative label이 아니다.

### 2.5 Existing contract lineage

기존 T-A lineage는 다음 제한과 함께 유효한 선행 evidence다.

- T-A0/T-A1: SDT Zenodo source identity, 480×640 single-channel uint16,
  Kelvin centiunit conversion, original labels, fail-closed reader.
- T-A2: G1_FIXED_ASPECT_CROP_BILINEAR, crop [10,0,630,480), canonical
  Celsius float32 [62,80], source orientation preservation.
- T-A3: SDT는 frame-level만 지원하며 sequence/event/window를 검증할 수
  없다. LYING은 temporal fall event가 아니다.
- T-A4: source label 불변, dual-layer source-plus-proxy mapping,
  NOT_HUMAN / HUMAN_NORMAL / HUMAN_FALL compatibility boundary.
- T-A5: official source partition 보존, frame-random/hash resplit 금지,
  subject/session identity 부재와 pristine locked holdout 부재.
- T-A6: real-test development conversion은 완료된 evidence가 있으나
  synthetic train/validation hydration과 full lineage에는 별도 제한이
  있다. 이는 V2 G1 PASS를 자동으로 의미하지 않는다.

G1 foundation은 위 lineage를 재구성하여 다음을 제안했지만 아직 freeze하지
않았다.

~~~text
GEO  = 62×80 physical canonical frame, source-specific validation required
PRE  = P1_TRAIN_FITTED_GLOBAL_ZSCORE proposal, TRAIN-only statistics
SPLIT = strongest available subject/session/sequence/scene grouping
LABEL = three proxy classes with explicit static/event/ambiguous boundaries
~~~

### 2.6 Dataset discovery and hard-negative evidence

D0가 후속 D1 검토 대상으로 남긴 serious candidates는 다음과 같다.

| Source | D0 value | Primary D1 question |
|---|---|---|
| Thermal Fall 66 / TF-66 | HIGH_VALUE semantically; operationally blocked | request/public wording, payload, license, participant grouping |
| IPHPDT / IPHD | PROMISING_WITH_ADAPTATION | labeled derivative access, dataset terms, temperature encoding, subject grouping |
| Thermal-IM | PROMISING_WITH_ADAPTATION | BSD-3 scope, actual annotation.json, actor/scene split, rendered thermal payload |
| QUIDA | PROMISING_WITH_ADAPTATION | OSF asset license, CSV schema, MLX90640 values, subject-level windows |
| eHomeSeniors | REFERENCE_ONLY to PROMISING_WITH_ADAPTATION | supplement payload/schema, release terms, six-subject grouping |

MUVIM, TSF, LWIRPOSE, TADAR, local screenshot trees 등은 D0에서
UNRESOLVED, REFERENCE_ONLY, LOW_VALUE, 또는 REJECT로 구분되었다.
새로운 후보를 추가할 때는 D1.1 inventory에 먼저 추가하고 동일한 evidence
field를 채운다.

### 2.6.1 TV2-D1.1 ledger freeze delivery

TV2-D1.1은 `PASS_WITH_LIMITATIONS`로 완료되었다. canonical ledger는
`docs/reports/20260830_Codex_Thermal_V2_TV2-D1.1_Execution_Report_KO_01.md`
section 6이며, D0의 모든 독립 source와 grouped rejection class를 17개 stable
record로 보존한다. IPHPDT derivative와 underlying IPHD는 permission boundary가
달라 별도 `source_id`로 분리했다. raw payload, training, model/data/runtime
mutation, `LOCKED_PUBLIC_TEST` 접근은 없었다.

Serious source verification order는 다음과 같이 고정되며 다음 실행은 하나뿐이다.

~~~text
TV2-D1.2 = TF_66
TV2-D1.3 = IPHPDT + IPHD
TV2-D1.4 = THERMAL_IM
TV2-D1.5 = QUIDA
TV2-D1.6 = EHOME_SENIORS
~~~

Dataset/asset license와 access metadata가 unresolved인 source는 성공으로
상향하지 않았다. D1.1의 limitation은 후속 source-specific 검증으로 전달되며,
Parent TV2-D1 또는 G1 PASS를 의미하지 않는다.

### 2.7 Parallel B6R evidence is context, not V2 authority

B6R-P0/P1/P2/P4 public-SDT auxiliary lineage는 source/model/locked-test
경계를 검증하는 참고 evidence이다. P0/P1은 PASS_WITH_LIMITATIONS, P2는
FP32 TFLite parity PASS, P3는 BLOCKED_HARDWARE, P4는
PASS_WITH_LIMITATIONS — PUBLIC_DATA_SOFTWARE_ONLY_NON_GATING이다. 이
결과들은 V2 G1, candidate training, MI48, physical validation, Pi, 또는
production authority로 자동 전파되지 않는다. legacy model, default
manifest, runtime selector, safety authority는 계속 보호한다.

## 3. Canonical Flow

Canonical ID와 큰 순서를 변경하지 않는다.

~~~text
G0 PASS
  ↓
TV2-D0 / TV2-H0 / GEO / PRE / SPLIT / LABEL
  ↓
TV2-D1
  ↓
TV2-D2
  ↓
TV2-D3
  ↓
G1
  ↓
Candidate A / G2 (required)
  ↓
Candidate B / G3 (conditional)
  ↓
G4 Offline Evaluation
  ↓
G5 Standalone Prototype Ready
  ↓
Team Application — later
  ↓
Integration / Pi / device-domain validation — deferred
~~~

D0/H0와 GEO/PRE/SPLIT/LABEL의 evidence는 병렬로 생성될 수 있지만,
순차 실행 시점의 CURRENT_NEXT_STEP는 항상 하나만 지정한다. D1-D3 및
G1은 training gate이고, G1 PASS 전에는 downstream training step을
활성화하지 않는다.

## 4. Repository Boundary

| Boundary | Rule |
|---|---|
| Primary development | https://github.com/sheepmeat/test.git; Thermal V2 data contracts, evidence, Candidate A/B, offline evaluation, standalone artifact |
| Team repository | https://github.com/jinsu1011/safenest-embedded-competition; later application target only; current work에서 수정/branch/commit/push/PR 금지 |
| Integration repository | https://github.com/yuname121/integration.git; deferred; current V2 prerequisite가 아님 |
| Active tree | AGENTS.md가 있는 Git root 직하의 docs/, datasets/, scripts/, inference/, models/, tests/ |
| Historical archive | archive/는 read-only evidence; active runtime이나 manifest discovery에 사용하지 않음 |
| Raw data | license/provenance가 확정되지 않은 raw archive를 repo에 복제하거나 commit하지 않음 |

모든 machine-readable artifact와 보고서에는 repository-relative POSIX path만
저장한다. Windows drive path, home path, file:// URI, local credential,
SSH target, raw archive bytes는 저장하지 않는다.

## 5. Non-goals for This First Execution

이번 bootstrap 실행의 범위는 branch 생성, evidence 읽기, current-state
reconstruction, 이 roadmap 문서 생성뿐이다.

- TV2-D1 source verification을 시작하지 않는다.
- dataset, sample, metadata, archive를 다운로드·추출·복제하지 않는다.
- raw/canonical/split dataset과 기존 manifest를 변경하지 않는다.
- Candidate A/B training, tuning, hyperparameter search, model selection을
  하지 않는다.
- TFLite export, INT8 conversion, model overwrite, runtime selector 변경,
  deployment 변경을 하지 않는다.
- LOCKED_PUBLIC_TEST를 열거나 sample/metric/selection에 사용하지 않는다.
- Team/Integration/Pi/device-domain/scientific-final 단계로 이동하지 않는다.

## 6. Execution Principles and Gates

1. **One atomic step.** 사용자가 다음 실행을 요청할 때 현재 block의
   NEXT_STEP 하나만 수행한다. 후속 step을 미리 수행하지 않는다.
2. **Evidence before contract.** 공식 dataset/project page, paper,
   publisher, official archive 순서로 확인하고, 2차 자료만으로 license나
   access를 확정하지 않는다.
3. **Conservative unknowns.** 사실을 확인할 수 없으면
   UNRESOLVED, LICENSE_UNRESOLVED, ACCESS_NOT_VERIFIABLE로 기록한다.
4. **License/provenance gate.** paper license와 dataset license를 분리하고,
   request-only/public link를 redistribution permission으로 해석하지
   않는다.
5. **Grouping before materialization.** subject → session →
   sequence/video → scene 순으로 가장 강한 실제 key를 사용한다. 없는
   identity를 filename, frame index, hash, timestamp로 발명하지 않는다.
6. **No leakage.** neighboring video frames/windows의 random split,
   subject/session cross-role, duplicate concealment를 금지한다.
7. **Training gate.** G1 PASS repository evidence 전에는 Candidate A/B,
   C1 control의 training을 승인하지 않는다. G1 PASS 후에도 해당 atomic
   training step만 YES_FOR_EXACT_STEP_ONLY가 된다.
8. **Locked-test protection.** public locked test 및 이미 개발에 사용된
   SDT real-test role을 pristine final test라고 부르지 않는다. model
   selection/tuning/threshold/architecture에 사용하지 않는다.
9. **Claim boundary.** staged fall/static lying은 clinical or natural fall이
   아니며 public SDT/Pi shadow evidence는 MI48, physical, safety, production
   evidence가 아니다.
10. **History preservation.** PASS, limitation, blocked, rejected, skipped
    path를 삭제하지 않는다. status가 다른 문서는 양쪽 status와 resolved
    reason을 함께 보존한다.

### Gate authorization rule

~~~text
G0 PASS
  → D1/D2/D3 evidence work only; TRAINING_AUTHORIZED=NO
  → G1 PASS
  → G2 Candidate A contract / G3 conditional decision
  → exact float training steps
  → G4 common offline comparison
  → G5 standalone artifact readiness
~~~

G1 BLOCKED이면 downstream training과 model/export/runtime 작업을 중단하고
blocker를 report와 roadmap history에 남긴다. G3가
SKIPPED_NOT_JUSTIFIED이면 B specification/training/evaluation path를
삭제하지 않고 해당 status로 종료한 뒤 G4에서 A/C1과 비교한다.

## 7. Complete Atomic Step Table

### 7.1 Bootstrap and current evidence

| Step ID | Parent Task | Status | Objective | Inputs | Actions | Outputs | Pass Criteria | Fail / Blocked Criteria | Forbidden Actions | Report | Next Step |
|---|---|---|---|---|---|---|---|---|---|---|---|
| ROADMAP-0 | G0 / bootstrap | DONE | 안전한 전용 branch에서 current state와 전체 순서를 고정 | clean main, Master Map, D0/H0/G1/A0 및 선행 evidence | branch 상태 확인, required docs·implementations·manifests 검토, roadmap 작성 | 이 문서, machine-readable state block | branch가 thermal-v2/stepwise-execution, current state와 next step이 evidence로 설명됨 | main dirty, branch 충돌, evidence 접근 불가 시 중단 | D1 실행, 다운로드, 학습, 모델/runtime/data 변경 | 이 roadmap 자체가 bootstrap delivery report; 별도 execution report 없음 | TV2-D1.1 |
| G0 | G0 | DONE / PASS | baseline·historical evidence·known gap의 canonical anchor 보존 | Master Map, B6R-P baseline, T-B history, H0/D0 | status를 새로 상향하지 않고 Master Map의 G0 anchor를 상속 | G0 reference pointer | Master Map에 G0 PASS와 evidence boundary 존재 | baseline identity 또는 protected test boundary가 불명확하면 BLOCKED | G0를 training authorization으로 해석 | Master Map / current-state evidence | TV2-D1.1 |
| TV2-D0 | TV2-D0 | DONE_WITH_LIMITATIONS | 추가 후보 discovery 결과를 D1 inventory 입력으로 보존 | D0 report와 official-source URLs | D0 candidate/value/limitations를 freeze; 새 D1 판단은 하지 않음 | D0 report, candidate list | five serious leads와 rejected/reference leads가 source별 식별됨 | source identity가 없거나 D0 report가 없으면 UNRESOLVED | D0를 license/access/training approval로 확대 | 기존 D0 report | TV2-D1.1 |
| TV2-H0 | TV2-H0 | DONE_WITH_LIMITATIONS | current pooled-MLP false-fall signal과 hard-negative gap 보존 | H0 report, P1/P4 evidence | 174/4000 failure와 missing semantic slices를 그대로 상속 | H0 report, failure-mode constraints | aggregate failure와 limitations가 재현 가능하게 기록됨 | row-level provenance가 없는데 semantic subset을 주장하면 BLOCKED | error row를 crouch/bend/occlusion으로 re-label, locked test 접근 | 기존 H0 report | TV2-D1.1 |
| G1-PREP | G1 | ACTIVE / REVIEW_PENDING | GEO/PRE/SPLIT/LABEL proposal과 D0/H0 dependency 관리 | G1 foundation, T-A2/T-A4/T-A5/T-A6, D0/H0 | proposal을 reference로 읽고 D1-D3 결과가 들어올 자리를 유지 | G1 proposal pointer | G1_READY_PENDING_D0_D3가 G1 PASS와 구분됨 | proposal만으로 G1을 닫을 수 없음 | contract freeze, training, runtime 변경 | 기존 G1 foundation report | TV2-D1.1 |

### 7.2 TV2-D1 — License / Provenance / Access verification

D1은 source triage와 controlled verification만 수행한다. 각 source step은
최소한 Identity, Access, License, Provenance, Payload, Grouping, Label을
다룬다. 실제 payload가 필요할 때도 official path, 허용된 terms, 최소
sample/metadata 범위만 사용한다.

| Step ID | Parent Task | Status | Objective | Inputs | Actions | Outputs | Pass Criteria | Fail / Blocked Criteria | Forbidden Actions | Report | Next Step |
|---|---|---|---|---|---|---|---|---|---|---|---|
| TV2-D1.1 | TV2-D1 | DONE_WITH_LIMITATIONS / PASS_WITH_LIMITATIONS | D0 후보 inventory와 source-by-source D1 evidence ledger freeze | D0 report, Master Map, official links, report template | stable source_id, official identity, paper/project/archive URL, access route, license/provenance/payload/group/label field를 만들고 순서를 고정 | D1 inventory/ledger, no raw payload | TF-66, IPHPDT/IPHD, Thermal-IM, QUIDA, eHomeSeniors와 D0 rejected/reference entries가 모두 보존되고 각 field가 PENDING 또는 링크 근거를 가짐 | candidate 누락, official identity 불명, status 추측 | raw download, account/approval bypass, training, model/data mutation | docs/reports/20260830_Codex_Thermal_V2_TV2-D1.1_Execution_Report_KO_01.md | TV2-D1.2 |
| TV2-D1.2 | TV2-D1 | NEXT | Thermal Fall 66 access/license/provenance 계약 검증 | D0 TF-66 entry, official paper/project/access page | public vs request wording, owner/publisher, release/version, license, payload route, participant/session/video grouping, fall/non-fall semantics 확인 | TF-66 evidence row | direct access 또는 정확한 blocker와 license state가 기록되고 LICENSE_UNRESOLVED가 숨겨지지 않음 | payload·terms·grouping 확인 불가 시 BLOCKED_ACCESS 또는 LICENSE_UNRESOLVED | data 임의 수신, frame을 training pool에 추가 | docs/reports/..._TV2-D1.2_Execution_Report_KO_01.md | TV2-D1.3 |
| TV2-D1.3 | TV2-D1 | PLANNED | IPHPDT/IPHD labeled derivative와 underlying dataset 경계 검증 | D0 IPHPDT/IPHD entry, Sensors paper, ChaLearn page | paper license와 dataset terms 분리, derivative access, Kelvin×100 representation, boxes/masks, version, subject/session, standing/sitting/lying/bending 확인 | IPHPDT/IPHD evidence row | dataset license/redistribution/derived-artifact status와 grouping limitation 명시 | request-only/derivative scope 불명 시 BLOCKED_LICENSE 또는 ACCESS_NOT_VERIFIABLE | paper open-access를 dataset permission으로 취급, processed data 복제 | docs/reports/..._TV2-D1.3_Execution_Report_KO_01.md | TV2-D1.4 |
| TV2-D1.4 | TV2-D1 | PLANNED | Thermal-IM normal-motion hard-negative source 검증 | D0 Thermal-IM entry, official repo/paper/download | BSD-3 scope, release identity, permitted archive members, annotation.json vocabulary, RGBT_T.mp4 representation, actor/room/scene/split, walking/sitting/kneeling 확인 | Thermal-IM evidence row | asset-level terms, rendered-vs-radiometric status, actor/scene grouping, action labels가 evidence 또는 explicit unresolved로 남음 | linked asset terms/annotations/split 확인 불가 시 BLOCKED_ACCESS 또는 LICENSE_UNRESOLVED | full archive download, redistribution assumption, fall-positive relabel | docs/reports/..._TV2-D1.4_Execution_Report_KO_01.md | TV2-D1.5 |
| TV2-D1.5 | TV2-D1 | PLANNED | QUIDA temperature/event reference contract 검증 | D0 QUIDA entry, PeerJ paper, OSF record | asset license, CSV schema, MLX90640 32×24 values/units, timestamps, subject folders, Falls.csv, simulated-fall/no-fall semantics, missing-sample and split evidence 확인 | QUIDA evidence row | OSF asset terms와 subject-level event provenance가 확인되거나 explicit unresolved | license/schema/access 불명 시 BLOCKED_LICENSE 또는 ACCESS_NOT_VERIFIABLE | simulated fall을 clinical truth로 승격, random window split | docs/reports/..._TV2-D1.5_Execution_Report_KO_01.md | TV2-D1.6 |
| TV2-D1.6 | TV2-D1 | PLANNED | eHomeSeniors supplement sensor/payload/provenance 검증 | D0 eHomeSeniors entry, paper, supplement/Figshare route | MLX90640/Omron fields, serialization/units, file identity, six-subject/fall-type grouping, ordinary context, release terms, official split 확인 | eHomeSeniors evidence row | payload와 terms를 source-specific evidence로 기록하고 normal-label weakness 보존 | supplement unavailable 또는 license unclear이면 REFERENCE_ONLY, BLOCKED_ACCESS, LICENSE_UNRESOLVED | full download, six subjects를 generalization proof로 해석 | docs/reports/..._TV2-D1.6_Execution_Report_KO_01.md | TV2-D1.7 |
| TV2-D1.7 | TV2-D1 | PLANNED | source별 D1 ledger의 missing/unresolved/blocked status 정규화 | D1.1–D1.6 reports/ledger, official evidence | paper-vs-dataset license conflict, access type, version, payload certainty, group key, label confidence를 namespace별 reconcile | consolidated D1 evidence registry, exception registry | 모든 candidate가 VERIFIED, UNRESOLVED, LICENSE_UNRESOLVED, ACCESS_NOT_VERIFIABLE 중 근거 있는 status를 가짐 | unresolved item 빈칸/추측, license 상향 | candidate ranking을 accuracy로 변경, data import/training | docs/reports/..._TV2-D1.7_Execution_Report_KO_01.md | TV2-D1.8 |
| TV2-D1.8 | TV2-D1 | PLANNED | D1 consolidated gate와 D2 진입 source set 결정 | D1 registry, exception registry, all D1 reports | source별 decision을 D2_ELIGIBLE, REFERENCE_ONLY, BLOCKED_ACCESS, BLOCKED_LICENSE, REJECT 등으로 결정; permitted minimal payload scope 고정 | D1 gate report and status snapshot | 각 source의 next role이 하나로 결정되고 raw data가 commit되지 않음 | required fields 미충족, provenance/license 불명 source를 D2에 강제하면 BLOCKED | D2 compatibility, derived artifact, training, locked-test access | docs/reports/..._TV2-D1.8_Execution_Report_KO_01.md | TV2-D2.1 |

### 7.3 TV2-D2 — Representation and SafeNest compatibility

D2는 D1을 통과하거나 D2_ELIGIBLE로 명시된 source만 대상으로 한다.
source representation을 canonical physical representation → [62,80,1]
경로에 연결할 수 있는지 검토하지만 training이나 model selection은 하지
않는다.

| Step ID | Parent Task | Status | Objective | Inputs | Actions | Outputs | Pass Criteria | Fail / Blocked Criteria | Forbidden Actions | Report | Next Step |
|---|---|---|---|---|---|---|---|---|---|---|---|
| TV2-D2.1 | TV2-D2 | PLANNED | D1 source set representation dossier와 compatibility matrix 작성 | D1 gate registry, source payload metadata | raw/radiometric/rendered/intensity classification, file type, native shape, FPS/static, bit depth, unit, orientation, compression, invalid-pixel fields 정리 | representation registry and test matrix | every D1-eligible source에 verified/provisional/unresolved field와 required test가 있음 | representation이 thermal인지조차 확인 불가하면 BLOCKED/REFERENCE_ONLY | common shape만으로 compatibility 확정 | docs/reports/..._TV2-D2.1_Execution_Report_KO_01.md | TV2-D2.2 |
| TV2-D2.2 | TV2-D2 | PLANNED | calibrated temperature matrix source geometry/unit compatibility 검토 | QUIDA/eHomeSeniors/IPHD evidence, T-A2/G1 geometry | Celsius/Kelvin conversion, 32×24/160×120 mapping, orientation, resize/interpolation, validity mask, nonfinite/zero policy evaluate | source geometry compatibility records | deterministic source→canonical mapping 또는 explicit exclusion; physical unit claim 정확 | unit/orientation/invalid semantics unresolved이면 INCLUDE_TRAIN 금지 | arbitrary compensation, silent zero fill, device equivalence claim | docs/reports/..._TV2-D2.2_Execution_Report_KO_01.md | TV2-D2.3 |
| TV2-D2.3 | TV2-D2 | PLANNED | rendered thermal video/image spatial/temporal compatibility 검토 | TF-66/Thermal-IM/IPHPDT evidence, D2.1 matrix | decoded channel semantics, frame extraction, aspect ratio, orientation, FPS/timestamps, compression, static-vs-temporal boundary inspect | rendered-source compatibility records | rendered intensity와 radiometric temperature를 구분하고 extraction contract 재현 가능 | codec/units/orientation/grouping 미확인 시 REFERENCE_ONLY/BLOCKED 유지 | rendered intensity를 Celsius로 부름, full raw archive repo 복제 | docs/reports/..._TV2-D2.3_Execution_Report_KO_01.md | TV2-D2.4 |
| TV2-D2.4 | TV2-D2 | PLANNED | source label과 SafeNest three-class proxy/hard-negative semantics 연결 | D1 labels, H0 taxonomy, G1 LABEL proposal | standing/sitting/walking/bending/kneeling/crouching/reclining/lying/fall/near-floor/partial/occlusion 분리; event_evidence_type와 ambiguity 부여 | label compatibility matrix, mapping/exclusion registry | original label 불변, explicit mapping, static lying vs temporal fall 분리, unsupported activity not inferred | conflict/missing label, partial/ambiguity면 UNRESOLVED/EXCLUDE | source label overwrite, static lying→real fall, missing category as negative | docs/reports/..._TV2-D2.4_Execution_Report_KO_01.md | TV2-D2.5 |
| TV2-D2.5 | TV2-D2 | PLANNED | grouping, split, duplicate, subject/session leakage와 domain gap 평가 | D1 group fields, T-A5/SPLIT, D2 registries | strongest group key, source namespace, window inheritance, exact/near duplicate scope, source-domain separation, future split strategy audit | D2 leakage/grouping audit and split feasibility record | no random correlated-frame split; group downgrade/absent identity explicit; audit scope disclosed | group key absent/overlap, duplicate policy impossible, leakage unbounded이면 training 제외 | random frame/window split, fake subject IDs, validation rebalancing | docs/reports/..._TV2-D2.5_Execution_Report_KO_01.md | TV2-D2.6 |
| TV2-D2.6 | TV2-D2 | PLANNED | D2 consolidated gate 및 source별 SafeNest role recommendation | D2.1–D2.5 artifacts | geometry/unit/label/grouping evidence를 합쳐 D3_ELIGIBLE, HARD_NEGATIVE_ONLY, REFERENCE_ONLY, BLOCKED 등을 제안 | D2 gate report, compatibility snapshot | eligible source마다 mapping, group, preprocessing boundary, limitation 완결 | common shape만으로 통과, missing evidence 은폐 시 BLOCKED | training, resplit, model comparison, locked test | docs/reports/..._TV2-D2.6_Execution_Report_KO_01.md | TV2-D3.1 |

### 7.4 TV2-D3 — Dataset expansion policy decision

D3는 실제 dataset import보다 source role과 governance를 결정하는 단계다.
각 source는 반드시 아래 decision 중 하나를 받는다.

~~~text
INCLUDE_TRAIN
INCLUDE_DEVELOPMENT_ONLY
HARD_NEGATIVE_ONLY
REFERENCE_ONLY
BLOCKED_ACCESS
BLOCKED_LICENSE
REJECT
~~~

BLOCKED_*, REJECT, REFERENCE_ONLY 경로도 삭제하지 않고 decision history에
남긴다.

| Step ID | Parent Task | Status | Objective | Inputs | Actions | Outputs | Pass Criteria | Fail / Blocked Criteria | Forbidden Actions | Report | Next Step |
|---|---|---|---|---|---|---|---|---|---|---|---|
| TV2-D3.1 | TV2-D3 | PLANNED | source inclusion role table 작성 | D1/D2 registries and gate decisions | source/version/license/group/representation/semantic evidence와 role candidate를 한 row로 연결 | D3 source-role matrix | 모든 source와 excluded reference가 exactly one provisional role을 가짐 | decision conflict or missing provenance면 BLOCKED | accuracy, convenience, download size로 role 결정 | docs/reports/..._TV2-D3.1_Execution_Report_KO_01.md | TV2-D3.2 |
| TV2-D3.2 | TV2-D3 | PLANNED | label mapping, ambiguity, hard-negative role freeze | H0 taxonomy, D2.4, G1 LABEL proposal | original token, mapping policy ID, target, event evidence, limitation, EXCLUDE/UNRESOLVED rule source-specific로 고정 | label decision registry | three target classes와 source-native labels 분리; unsupported categories forced negative 아님 | temporal/static or normal/fall conflict면 BLOCKED | count 개선을 위한 re-label, clinical/safety wording | docs/reports/..._TV2-D3.2_Execution_Report_KO_01.md | TV2-D3.3 |
| TV2-D3.3 | TV2-D3 | PLANNED | immutable group/split/leakage policy 확정 | D2.5, source groups, T-A5/SPLIT | group namespace, TRAIN/DEVELOPMENT/later-eval roles, duplicate policy, source balancing after split, locked-test rule 선언 | split strategy and leakage contract | every row inherits source/group/role; no frame-random split; locked role protected | group identity absent or cross-role overlap이면 source downgrade/BLOCKED | random split, fake groups, locked test sampling | docs/reports/..._TV2-D3.3_Execution_Report_KO_01.md | TV2-D3.4 |
| TV2-D3.4 | TV2-D3 | PLANNED | preprocessing/materialization boundary와 TRAIN-only statistic rule 결정 | D2 representation, G1 PRE/GEO, D3 roles | source→canonical→model-ready boundary, P1 mean/std fit source, epsilon, nonfinite handling, adapter boundary, no raw commit rule 고정 | preprocessing and materialization contract | statistics fit only after split and on TRAIN; artifact에 profile/source/quality/provenance 기록 | unreviewed fallback, validation/test statistics, materialization license 불가 | per-frame hidden fallback, validation/test stats, raw archive commit | docs/reports/..._TV2-D3.4_Execution_Report_KO_01.md | TV2-D3.5 |
| TV2-D3.5 | TV2-D3 | PLANNED | final D3 expansion decision과 G1 input snapshot 발행 | D3.1–D3.4 artifacts | each source final role, exclusion reason, mapping, group/split, preprocessing boundary 결정; approved source set만 G1 handoff | D3 decision report, final source-role snapshot | every source one decision, exclusions/reasons preserved, no training artifact | required D1/D2 evidence missing or role indefensible면 BLOCKED | training, tuning, raw/canonical mutation, model selection | docs/reports/..._TV2-D3.5_Execution_Report_KO_01.md | G1.1 |

### 7.5 G1 — Data / model contract ready

G1은 문서 proposal의 존재가 아니라 D1-D3와 GEO/PRE/SPLIT/LABEL의
repository evidence가 합쳐진 gate다. 아래 하위 단계가 끝나기 전에는
TRAINING_AUTHORIZED를 YES로 바꾸지 않는다.

| Step ID | Parent Task | Status | Objective | Inputs | Actions | Outputs | Pass Criteria | Fail / Blocked Criteria | Forbidden Actions | Report | Next Step |
|---|---|---|---|---|---|---|---|---|---|---|---|
| G1.1 | G1 / GEO | PLANNED | source-specific geometry를 canonical 62×80 contract에 연결 | D2 geometry, T-A2, G1 foundation | [1,62,80,1], source shape/channel/unit, crop/resize/orientation/dtype, validity/fail-closed behavior freeze | GEO contract snapshot | each included source deterministic mapping or explicit non-inclusion; no Thermal-44 equivalence | unsupported shape/unit/orientation unresolved면 BLOCKED | data-dependent crop, zero substitute, runtime geometry change | docs/reports/..._G1.1_Execution_Report_KO_01.md | G1.2 |
| G1.2 | G1 / PRE | PLANNED | shared Candidate A/B/C1 preprocessing contract freeze | D3.4, T-B0/T-B1, G1 PRE | P1 train-fitted global z-score mean/std, epsilon 1e-6, finite handling, fit counts/checksums, bounded P2 fallback policy freeze | PRE contract snapshot | same stats/profile for matched candidates; TRAIN-only fit; no implicit clipping | statistics leak or unbounded profile search면 BLOCKED | per-frame refit, open hyperparameter search, legacy runtime rewrite | docs/reports/..._G1.2_Execution_Report_KO_01.md | G1.3 |
| G1.3 | G1 / SPLIT | PLANNED | immutable roles and leakage/locked-test policy freeze | D3.3, T-A5, group evidence | group hierarchy, source namespace, role membership, duplicate audit, LOCKED_PUBLIC_TEST access log policy lock | SPLIT contract snapshot | no correlated group crosses roles; locked test unread; absent identities and holdout limitation explicit | role contamination, group assignment indefensible, test opened이면 BLOCKED | random frame split, retroactive holdout, test-driven selection | docs/reports/..._G1.3_Execution_Report_KO_01.md | G1.4 |
| G1.4 | G1 / LABEL | PLANNED | three-class proxy label and source mapping contract freeze | D3.2, H0, T-A4, D2.4 | NOT_HUMAN, HUMAN_NORMAL, HUMAN_FALL_PROXY, event/static/ambiguous types, source labels, mapping/exclusion/claim limits lock | LABEL contract snapshot | original labels immutable; unsupported/ambiguous rows fail closed; no clinical/safety wording | mapping count-driven, temporal evidence absent, ambiguity forced이면 BLOCKED | source overwrite, lying=real fall, missing activity as negative | docs/reports/..._G1.4_Execution_Report_KO_01.md | G1.5 |
| G1.5 | G1 | PLANNED | integrated G1 audit and PASS/BLOCKED decision | G1.1–G1.4, D3 snapshot, all reports | predecessor validation, artifact/checksum/path audit, contract consistency, training/locked-test authorization reconcile | G1 gate report and updated roadmap block | G1 PASS only if GEO/PRE/SPLIT/LABEL+D3 evidence reviewable and limitations explicit | missing contract, unresolved intended source, leakage, license, locked-test violation이면 BLOCKED | Candidate training, export, runtime/model manifest change | docs/reports/..._G1.5_Execution_Report_KO_01.md | if PASS: G2.1; if BLOCKED: remediation only |

### 7.6 Candidate A and G2 — Required path

Candidate A는 A0 방향을 상속하되 exact historical Flatten
SMALL_CNN_BASELINE_V1을 자동 재사용하지 않는다. A0 family는
REVISED_COMPACT_CONVENTIONAL_CNN이며 head는 G2에서 결정한다.

| Step ID | Parent Task | Status | Objective | Inputs | Actions | Outputs | Pass Criteria | Fail / Blocked Criteria | Forbidden Actions | Report | Next Step |
|---|---|---|---|---|---|---|---|---|---|---|---|
| G2.1 | G2 / Candidate A | PLANNED | Candidate A exact head와 train-ready architecture 결정 | G1 PASS, A0, H0 requirements | shared Conv stack과 A_HEAD_GAP vs A_HEAD_SPATIAL_RETAIN 비교 후 한 head와 rationale freeze | Candidate A architecture contract | architecture factor, input, ops, head, parameter bound, seed/optimizer interface 하나로 고정 | G1 미통과, head 근거 없음, Flatten 자동 채택이면 BLOCKED | training, data/label/preprocess changes, multi-head search | docs/reports/..._G2.1_Execution_Report_KO_01.md | G2.2 |
| G2.2 | G2 / Candidate A | PLANNED | Candidate A implementation/fingerprint/edge-op contract 검증 | G2.1, t_b1_model.py/t_b2_model.py lineage, G1 input | executable contract, parameter count, fingerprint, tensor shape, built-in op inventory, deterministic initialization fixture 검증 | A train-ready contract and validator | [1,62,80,1]→[1,3], reproducible, no default manifest/runtime change | implementation mismatch, unsupported op, parameter/head drift면 BLOCKED | training, export, runtime selector change | docs/reports/..._G2.2_Execution_Report_KO_01.md | G2.3 |
| G2.3 | G2 | PLANNED | G2 Candidate A Ready gate | G2.1–G2.2, G1 gate | readiness validator, predecessor/claim-boundary audit; exact training authorization for next step만 기록 | G2 gate report | G2 PASS는 train-ready only; trained/winner/production 아님 | contract or G1 invalid이면 BLOCKED | Candidate training in same step, model selection, TFLite/INT8 | docs/reports/..._G2.3_Execution_Report_KO_01.md | A-TRAIN.1 |
| A-TRAIN.1 | G2 / Candidate A | PLANNED | frozen contract 아래 Candidate A float training | G2 PASS, G1 roles, frozen GEO/PRE/SPLIT/LABEL | TRAIN-only fitting/stats, fixed seed/optimizer/early-stop, DEVELOPMENT diagnostic, artifact/provenance 생성 | A float checkpoint/model artifact, report | no locked-test; deterministic; full provenance; float-only; legacy unchanged | missing role, leakage, nonfinite, locked-test, resource failure면 BLOCKED | B/C1 training, tuning bundle, quantization/export, production overwrite | docs/reports/..._A-TRAIN.1_Execution_Report_KO_01.md | G3.1 |

### 7.7 Candidate B and G3 — Conditional path

G3는 A0의 B_JUSTIFIED를 자동 승인하지 않는다. Candidate B는 Candidate
A와 실제로 다른 inductive-bias hypothesis가 필요하다. 최초 tiny
347-parameter depthwise 결과를 그대로 반복하지 않으며, 승인될 경우
CAPACITY_MATCHED_DEPTHWISE_SEPARABLE_CNN을 검토한다.

| Step ID | Parent Task | Status | Objective | Inputs | Actions | Outputs | Pass Criteria | Fail / Blocked Criteria | Forbidden Actions | Report | Next Step |
|---|---|---|---|---|---|---|---|---|---|---|---|
| G3.1 | G3 | CONDITIONAL | distinct second hypothesis가 과학적으로 정당한지 결정 | G1 PASS, A0, H0, Candidate A evidence | A/B inductive bias, capacity, edge rationale, identifiable factor 비교; YES/NO 명시 | G3 justification decision | YES면 separate depthwise hypothesis가 factor-identifiable; NO면 SKIPPED_NOT_JUSTIFIED | distinction이 model count뿐이거나 G1 미통과면 SKIPPED_NOT_JUSTIFIED 또는 BLOCKED | A+data+loss+augmentation mega-bundle, exact 347 rerun 강제 | docs/reports/..._G3.1_Execution_Report_KO_01.md | YES: G3.2; NO: G4.1 |
| G3.2 | G3 / Candidate B | CONDITIONAL | 승인 시 capacity-matched B train-ready contract freeze | G3 YES, G1 contracts, A0 provisional B | Conv/SeparableConv/Pool/GAP/Dense/ReLU/Softmax, parameter bound, fingerprint, same input/pre/labels/optimizer interface 검증 | B contract/validator evidence | materially distinct, capacity-matched, TFLite-simple, deterministic | G3 NO, op/parameter mismatch, contract drift면 SKIPPED_NOT_JUSTIFIED/BLOCKED | historical tiny depthwise copy, B-specific preprocessing/loss/tuning | docs/reports/..._G3.2_Execution_Report_KO_01.md | B-TRAIN.1 |
| B-TRAIN.1 | G3 / Candidate B | CONDITIONAL | approved B float training | G3.2 PASS, G1 data/contract, common protocol | same TRAIN-only/statistics/seed policy로 B만 학습; DEVELOPMENT diagnostic; artifact 분리 | B float artifact, report | no locked-test, deterministic, provenance, legacy unchanged | G3 skipped, leakage, missing role, nonfinite, locked-test면 no-op/BLOCKED | B-specific data/preprocess/loss bundle, export, runtime change | docs/reports/..._B-TRAIN.1_Execution_Report_KO_01.md | G4.1 |

### 7.8 G4 — Common offline evaluation

G4에서 C0는 native historical operational reference로 보고, architecture
factor comparison에는 동일한 미래 contract로 재학습한 C1 control을 사용한다.
Cross-experiment 숫자를 직접 ranking하지 않는다.

| Step ID | Parent Task | Status | Objective | Inputs | Actions | Outputs | Pass Criteria | Fail / Blocked Criteria | Forbidden Actions | Report | Next Step |
|---|---|---|---|---|---|---|---|---|---|---|---|
| G4.1 | G4 | PLANNED | evaluation protocol과 selection rule을 결과 전에 freeze | G1 PASS, G2/G3 decisions, A artifacts/readiness | common data, GEO/PRE/LABEL, optimizer/seed/augmentation, C0/C1 roles, metrics, hard-negative slice, locked-test boundary predeclare | G4 protocol contract | Macro F1, Balanced Accuracy, per-class P/R/F1, full CM, NORMAL→FALL count/rate, FALL→NORMAL, NOT_HUMAN→FALL 포함; test closed | protocol post-hoc 변경, C0/C1 mismatch 미표기면 BLOCKED | threshold/model choice from locked test, metric edits | docs/reports/..._G4.1_Execution_Report_KO_01.md | G4.2 |
| G4.2 | G4 / C1 control | PLANNED | matched pooled-MLP C1 control 생성 | G4.1, G1 frozen dataset/preprocess/labels, C0 identity | current pooled-MLP architecture를 same future contract/seed/optimizer로 train; C0 untouched | C1 model/training artifact and report | C1 differs only by architecture from A/B; no locked-test; legacy unchanged | contract/protocol drift면 BLOCKED and limitation | C0 overwrite, C1 test access, extra tuning factor | docs/reports/..._G4.2_Execution_Report_KO_01.md | G4.3 |
| G4.3 | G4 / Candidate A | PLANNED | Candidate A common-protocol offline evaluation | A float artifact, G4.1, permitted roles | authorized roles predict; all metrics and provenance/source slices; locked-test audit zero | A evaluation report/manifest | metrics complete, deterministic, per-class/source/temporal-static slices, NORMAL→FALL recorded | missing rows, leaked group, schema mismatch면 BLOCKED | locked-test eval, post-result tuning, production selection | docs/reports/..._G4.3_Execution_Report_KO_01.md | if B active G4.4, else G4.5 |
| G4.4 | G4 / Candidate B | CONDITIONAL | B evaluation 또는 explicit skip closure | G3 decision, B artifact if YES, G4.1 | G3 YES면 exact protocol로 B evaluate; NO면 no-artifact skip record | B evaluation or SKIPPED_NOT_JUSTIFIED report | B comparable only with same contract; skip history preserved | approved B artifact missing, protocol drift, locked-test access면 BLOCKED | train B here, alter protocol, erase skip path | docs/reports/..._G4.4_Execution_Report_KO_01.md | G4.5 |
| G4.5 | G4 / hard negatives | PLANNED | hard-negative and failure-metric evaluation | A/B/C1 outputs, H0 taxonomy, D3 roles | explicit standing/sitting/walking/bending/kneeling/near-floor/partial/occlusion slices only where provenance supports; source/domain/label-decision slices | hard-negative evaluation report | no inferred labels; NORMAL→FALL_PROXY primary failure metric; limitations complete | semantic subset not defensible면 NOT_VERIFIABLE, not fabricate | false predictions alone으로 hard-negative 생성, test access | docs/reports/..._G4.5_Execution_Report_KO_01.md | G4.6 |
| G4.6 | G4 | PLANNED | C0/C1/A/B comparison과 G4 gate decision | G4.1–G4.5 | matched A/B/C1 compare; C0 native mismatch report; predeclared rule and false-fall metric 적용; G4 complete/blocked decision | G4 consolidated gate and comparison decision | required metrics/CM/failure metrics/test audit present; invalid cross-lineage claim 없음 | artifact missing, protocol mismatch, leakage, defensible decision 부재면 BLOCKED | scientific final selection, production activation, Team import, test opening | docs/reports/..._G4.6_Execution_Report_KO_01.md | G5.1 if complete; otherwise remediation |

### 7.9 G5 — Standalone prototype readiness

G5의 의미는 standalone prototype artifact readiness뿐이다. scientific final
model, production model, Pi-validated model, device-domain validated model이
아니다.

| Step ID | Parent Task | Status | Objective | Inputs | Actions | Outputs | Pass Criteria | Fail / Blocked Criteria | Forbidden Actions | Report | Next Step |
|---|---|---|---|---|---|---|---|---|---|---|---|
| G5.1 | G5 | PLANNED | G4 결과에 따른 standalone prototype decision | G4 gate, A/B/C1 artifacts, claim boundary | A/B/BOTH/NONE decision; selected identity와 non-selection reason 기록 | prototype decision record | G4 rule을 따르고 rejected/skipped path 보존; production claim 없음 | G4 incomplete 또는 mismatch면 BLOCKED/NONE with reason | test-driven selection, default model replacement | docs/reports/..._G5.1_Execution_Report_KO_01.md | G5.2 |
| G5.2 | G5 | PLANNED | selected float artifact와 standalone contract bundle 준비 | G5.1, checkpoint/model, G1/G4 contracts | metadata, I/O schema, preprocessing identity, checksums, provenance, reproducibility fixture, rollback note package | standalone float prototype bundle | exact artifact/checksum/shape/dtype/class order and shadow-only boundary verified | checksum/schema/claim mismatch면 BLOCKED | default manifest overwrite, runtime selector, Team copy, raw data bundle | docs/reports/..._G5.2_Execution_Report_KO_01.md | G5.3 |
| G5.3 | G5 | CONDITIONAL | separately authorized TFLite/INT8 artifact readiness와 parity 검토 | G5.2, explicit export authorization, edge-op contract | FP32 export first; optional INT8 separate operation; development fixture parity; legacy untouched | export/parity evidence or NOT_EXECUTED | authorization and parity pass; otherwise BLOCKED/NOT_EXECUTED | G1 전 export, production overwrite, Pi claim, test access | docs/reports/..._G5.3_Execution_Report_KO_01.md | G5.4 |
| G5.4 | G5 | PLANNED | G5 standalone prototype gate close | G5.1–G5.3, validators | readiness audit, standalone scope, Team/Pi/device-domain deferral, roadmap update | G5 gate report and standalone pointer | reproducible, shadow/standalone only, no production/default/safety authority | identity/parity/rollback evidence missing면 BLOCKED | Team application, Integration/Pi, scientific final selection | docs/reports/..._G5.4_Execution_Report_KO_01.md | TEAM-APP.1 later |

### 7.10 Explicitly deferred post-G5 paths

| Step ID | Parent Task | Status | Objective | Inputs | Actions | Outputs | Pass Criteria | Fail / Blocked Criteria | Forbidden Actions | Report | Next Step |
|---|---|---|---|---|---|---|---|---|---|---|---|
| TEAM-APP.1 | Team Application | DEFERRED | selected standalone artifact를 Team repo에 later apply | G5 PASS, separate user instruction, updated Team main | collision inventory, explicit path reconciliation, Team branch/import/validation | separate Team report/PR | separate authorization and owner workflow | no authorization, collision, hardware/contract gap | current task에서 Team repo 수정 | separate later report | separate user decision |
| INTEGRATION.1 | Integration | DEFERRED | integration repository application | Team gate and later instruction | deferred until Team application and owners authorize | later integration evidence | separate gate only | current scope 밖 | integration branch/commit/push now | later report | separate user decision |
| PI-DEVICE.1 | device-domain | DEFERRED | Raspberry Pi / MI48 / Thermal-90 controlled validation | standalone/Team artifact, target, capture contract | target measurement, latency/resource/stability, physical validation later | device-domain report | actual target evidence only | no target/provenance/holdout이면 BLOCKED_HARDWARE | desktop substitution, SSH guessing, real-fall claim | later report | separate user decision |
| SCIENTIFIC-FINAL.1 | final selection | DEFERRED | scientific final model selection | independent holdout and device-domain evidence | separate review only | final scientific report | independent evidence and explicit authority | no independent holdout/physical evidence면 blocked | G4/G5 result을 final winner로 표현 | later report | separate user decision |

## 8. CURRENT_NEXT_STEP Update Rules

각 atomic step 종료 시 다음 순서만 허용한다.

1. git branch --show-current가 thermal-v2/stepwise-execution인지 확인한다.
2. git fetch origin 후 git pull --ff-only로 branch를 최신화한다.
3. 이 문서의 CURRENT_STEP, NEXT_STEP, LAST_COMPLETED_REPORT,
   TRAINING_AUTHORIZED를 읽는다.
4. 최신 관련 report, manifest, script, artifact를 읽는다.
5. CURRENT_STEP 하나만 수행한다.
6. 다음 step의 action은 수행하지 않는다.
7. 지정된 report를 작성한다.
8. 이 roadmap에서 완료/blocked/skip history와 machine block을 갱신한다.
9. focused validation, git diff --check, 필요한 upstream regression을
   실행한다.
10. git status, git diff --stat, git log -1 --oneline을 기록한다.
11. 관련 파일만 명시적으로 stage하고 한 step 단위로 commit한다. git add .
    를 사용하지 않는다.
12. origin/thermal-v2/stepwise-execution으로 push한다.

상태 전이는 PLANNED → ACTIVE → DONE 또는 실제 blocker 발생 시
ACTIVE → BLOCKED로 보존한다. BLOCKED_ACCESS, BLOCKED_LICENSE,
SKIPPED_NOT_JUSTIFIED, REJECT는 삭제하거나 성공으로 바꾸지 않는다.

## 9. Per-Step Execution Report Rule

### 9.1 Filename

기존 docs/reports convention을 따르고, 파일이 있으면 덮어쓰지 않고
revision suffix를 증가시킨다.

~~~text
docs/reports/YYYYMMDD_Codex_Thermal_V2_<STEP-ID>_Execution_Report_KO_01.md
~~~

예:

~~~text
docs/reports/20260830_Codex_Thermal_V2_TV2-D1.2_Execution_Report_KO_01.md
~~~

### 9.2 Required header

모든 step report는 다음 field를 포함한다.

~~~text
Document ID
Date
Repository
Branch
Commit base
Step ID
Parent Task
Scope
Status
Training Authorization
Locked-test Access
~~~

### 9.3 Required body

- Objective
- Evidence Reviewed — repository file, official page, paper, repository,
  license page, manifest, script, artifact
- Actions Performed — 실제 수행 명령과 범위
- Findings — 확인된 사실과 source별 status
- Unresolved Items — 추측 없이 미확인 사실
- Artifacts Created / Modified
- Validation
- Decision — PASS, PASS_WITH_LIMITATIONS, BLOCKED, FAIL,
  SKIPPED_NOT_JUSTIFIED 중 해당 값
- Gate Impact
- Next Authorized Step — 다음 step 이름만; 다음 step 자체는 수행하지 않음
- Git Evidence — git status, git diff --stat, git log -1 --oneline

Report가 없거나 Next Authorized Step이 두 개 이상이면 해당 atomic step은
완료로 취급하지 않는다.

## 10. Initial Bootstrap Validation and Delivery

로드맵 문서만 변경한 뒤 다음을 확인한다.

~~~text
git status
git diff --check
git diff --stat
~~~

권장 commit message:

~~~text
docs(thermal-v2): add stepwise execution roadmap
~~~

그 후 현재 branch를 다음처럼 push한다.

~~~text
git push -u origin thermal-v2/stepwise-execution
~~~

이 bootstrap delivery의 종료 조건은 다음과 같다.

- origin/main 최신화와 main clean 확인
- thermal-v2/stepwise-execution branch 생성
- required Thermal V2 docs/evidence/implementation 검토
- D1→D2→D3→G1→G2/G3→G4→G5 atomic table 작성
- PASS/BLOCKED/conditional criteria와 report naming rule 정의
- CURRENT_NEXT_STEP=TV2-D1.1 지정
- TRAINING_AUTHORIZED=NO 유지
- git diff --check 통과
- roadmap commit 및 branch push
- TV2-D1.1 자체는 수행하지 않음

## 11. Stop Boundary After Bootstrap

첫 실행 완료 후에는 이 문서의 CURRENT_NEXT_STEP만 사용자에게 전달하고
중단한다. 다음 실행 요청이 없으면 D1 source page를 조사하거나 dataset을
다운로드하지 않는다.

다음 실행 명령:

~~~text
로드맵을 읽고 CURRENT_NEXT_STEP에 해당하는 단계 1개만 수행해.
결과 보고서를 작성하고 roadmap 상태를 갱신한 뒤 commit/push하고 종료해.
~~~

이 문서의 G5 이후는 별도 Team Application 지시가 있을 때만 활성화한다.
