# SafeNest Thermal B6-R B6R-P0 Public SDT Materialization 실행 보고서

## 1. 작업 개요

- 날짜: `2026-08-26`
- Stage: `B6R-P0 — Public SDT Dataset Materialization & Split Contract`
- 작업 브랜치: `feature/thermal-b6r-development`
- 시작 HEAD: `5acd86516630d8b7b729e17bebe03fc2eb3a20ad`
- 결과 상태: `PASS_WITH_LIMITATIONS`
- 생성 모델: `NONE` — 이 stage는 dataset materialization만 수행
- 원본 archive 변경: `NO`
- 기존 B6R-0~14 상태 변경: `NO`

## 2. 기존 로드맵에 없던 단계를 추가한 이유

기존 B6R 본선은 권위 MI48 snapshot을 전제로 한다. 현재 `RP-X0_O2.6_MI48_FIELD_SNAPSHOT`을 저장소·Git 원격·mount된 workspace에서 찾지 못했고, `B6R-1`은 `INCONCLUSIVE`, `B6R-2`는 `BLOCKED` 상태다. 따라서 B6R-3 이후의 robust-relative/physical/competition 경로로 진행할 수 없다.

반면 workspace의 `열화상_dataset` archive 6개는 checksum과 ZIP 구조를 확인할 수 있었고, 사용자는 physical/MI48 C 계열을 당장 수행하지 않고 public data로 모델을 먼저 만드는 보조 경로를 승인했다. 이에 기존 B6R-0~14를 수정하거나 우회 통과시키지 않고 `B6R-P*` public-data 전용 흐름을 추가했다.

이 stage의 성공 의미는 다음으로 제한된다.

```text
가능: public SDT 학습 입력 생성 → 별도 승인 시 public-only 모델 학습
불가: MI48 검증으로 승격 → 기본 모델 교체 → 안전 권한 → physical/competition lock
```

## 3. Stage 실행 계약

| 항목 | 계약 |
|---|---|
| source access | archive 6개를 read-only로 열며 source directory에 압축 해제하지 않음 |
| included payload | `image_t_{index}.png`와 같은 index의 `labels.txt` record |
| excluded payload | `image_d` 전체 |
| split | train 32,000 / validation 8,000 / test 8,000 원본 역할 보존 |
| roles | `TRAIN` / `DEVELOPMENT` / `LOCKED_PUBLIC_TEST` |
| preprocessing | `480×640` I;16 → PIL bilinear `(62,80)` → frame-wise min-max `[0,1]` float32 |
| label mapping | 3→NOT_HUMAN, 1·2→HUMAN_NORMAL, 0→HUMAN_FALL_PROXY |
| test policy | materialization·무결성·provenance 확인만 허용; model selection·tuning·metric 금지 |
| Git policy | contract·검증 evidence만 추적; 약 1GB materialized payload는 local-only |

## 4. 수행한 작업

1. 기존 B6R roadmap, B6R-0~2 보고서·manifest, runtime과 legacy `thermal_prep.py`/`thermal_train.py`를 재검토했다.
2. 기존 `thermal_prep.py`가 세 split을 한 배열로 병합하고 기존 `thermal_train.py`가 이를 무작위 80:20으로 다시 나누며 legacy model을 덮어쓰는 것을 확인해 B6R-P0/P1 경로에서 사용하지 않도록 금지했다.
3. `config/thermal/b6r_p0_public_sdt_contract.json`에 source archive identity, split, label mapping, preprocessing, test lock, claim boundary를 고정했다.
4. multipart train ZIP을 포함한 6개 archive를 source extraction 없이 stream으로 열어 `image_t`와 label만 처리했다.
5. split별 `images.npy`, `labels.npy`, `source_labels.npy`, `sample_index.jsonl`, `split_manifest.json`을 생성했다.
6. 48,000개 sample마다 source archive/member/CRC32/PNG SHA-256, label record/index/SHA-256, target label, preprocessing identity, derived tensor SHA-256을 기록했다.
7. 전수 materialization을 논리적으로 한 번 더 재실행하여 tensor, target/source label, provenance stream hash가 split별로 모두 동일함을 확인했다.
8. 처리 전·후 원본 6개 파일의 size, mtime, SHA-256을 다시 계산하여 모두 동일함을 확인했다.
9. standalone validator로 배열 contract, 전수 tensor-provenance 대응, split accounting, ID 비중복, artifact registry, 절대경로 미기록을 검증했다.
10. roadmap과 development index에 보조 흐름의 이유, 완료 내용, 후속 작업의 상속 규칙을 추가했다.

## 5. Materialization 결과

| Split | Role | Samples | Source class 0/1/2/3 | Target NOT_HUMAN / NORMAL / FALL_PROXY | Shape |
|---|---|---:|---|---|---|
| train | `TRAIN` | 32,000 | 8,000 / 8,000 / 8,000 / 8,000 | 8,000 / 16,000 / 8,000 | `(32000,62,80,1)` |
| validation | `DEVELOPMENT` | 8,000 | 2,000 / 2,000 / 2,000 / 2,000 | 2,000 / 4,000 / 2,000 | `(8000,62,80,1)` |
| test | `LOCKED_PUBLIC_TEST` | 8,000 | 2,000 / 2,000 / 2,000 / 2,000 | 2,000 / 4,000 / 2,000 | `(8000,62,80,1)` |
| 합계 | - | 48,000 | 12,000 / 12,000 / 12,000 / 12,000 | 12,000 / 24,000 / 12,000 | - |

- materialized file 수: `16`
- materialized local payload 크기: `995,606,483 bytes` (약 `949.5 MiB`)
- tensor 범위: 모든 split `0.0`~`1.0`
- tensor dtype: `float32`
- sample provenance: `48,000/48,000`
- tensor↔provenance SHA-256 일치: `48,000/48,000`
- split 간 sample ID 교집합: `0`

## 6. 결정론 및 원본 불변 결과

| Split | Tensor logical stream SHA-256 | 재실행 일치 |
|---|---|---|
| train | `4077d73c81a02da9a59f282e43fce306fbc8680a28d60c0a56b9309d70d978fb` | PASS |
| validation | `2a3f1bd1143355144caf96ec85c9b0f35b72b28799dd518d02f570161b250273` | PASS |
| test | `d9e2febe1d9f262b1ab18056056d7d99105eade5d14938896c7ac88138319cfa` | PASS |

target label, source label, sample provenance stream도 1차/재실행 hash가 split별로 모두 일치했다. 원본 archive 6개는 처리 전·후 size·mtime·SHA-256이 모두 같고 기존 B6R-1/B6R-2 source registry와 `6/6` 일치했다.

## 7. 구현 및 Artifact

- `config/thermal/b6r_p0_public_sdt_contract.json` — public dataset, split, preprocessing, label, test, claim 계약.
- `scripts/materialize_thermal_b6r_p0_public_sdt.py` — read-only ZIP stream materializer와 deterministic repeat audit.
- `scripts/validate_thermal_b6r_p0_public_sdt.py` — 전수 배열/provenance/split/artifact validator.
- `tests/test_thermal_b6r_p0_public_sdt.py` — label mapping, normalization, constant frame, multipart stream, deterministic JSON 단위 검증.
- `datasets/thermal/manifests/B6R-P0_public_sdt_materialization/` — tracked contract evidence, checksum, validation result.
- `datasets/thermal/materialized/B6R-P0_public_sdt_v1/` — local-only materialized payload; Git 미추적.

## 8. 검증 및 테스트

| Test | Actual | Result |
|---|---|---|
| Python compile | materializer, validator, focused test compile 성공 | PASS |
| focused unittest | `5 tests`, 모두 성공 | PASS |
| source registry | archive 6/6 size·SHA 일치 | PASS |
| materialization accounting | 48,000 = 32,000 + 8,000 + 8,000 | PASS |
| 전수 tensor provenance | 48,000/48,000 SHA 일치 | PASS |
| split sample ID isolation | 세 교집합 모두 0 | PASS |
| deterministic repeat | 3 split × 4 logical stream hash 모두 동일 | PASS |
| source immutability | 처리 전·후 6/6 size·mtime·SHA 동일 | PASS |
| artifact registry | local materialized artifact 전부 size·SHA 일치 | PASS |
| path policy | machine-readable artifact에 절대경로 없음 | PASS |
| B6R-P0 validator | `PASS_WITH_LIMITATIONS` | PASS |

실행 환경은 Python `3.12.13`, NumPy `2.3.5`, Pillow `12.3.0`, Windows이다.

## 9. 기존 보고서 및 본선 상태와의 관계

- B6R-0 `FAIL`은 변경하지 않았다. B5 model bytes/runtime/Pi 증거는 여전히 없다.
- B6R-1 `INCONCLUSIVE`를 변경하지 않았다. public SDT는 MI48가 아니다.
- B6R-2 `BLOCKED`를 변경하지 않았다. subject/session/recording group과 independent MI48 holdout이 없다.
- B6R-3~14는 시작하지 않았다.
- B6R-11·13·14의 independent physical/competition lock은 수행할 수 없다.
- legacy model, `models/model_manifest.json`, runtime selector, safety/risk subsystem은 수정하지 않았다.

## 10. 제한 사항과 금지되는 주장

- source PNG는 `480×640` 16-bit image이며 native MI48 `(62,80)` raw capture가 아니다.
- subject/session/recording metadata가 없으므로 source archive split을 보존했지만 group isolation을 주장하지 않는다.
- source token 0은 lying/fallen posture proxy이며 실제 낙상 사건 검출 근거가 아니다.
- test label은 요청된 materialization과 무결성 확인을 위해 기록했지만 B6R-P0에서 성능 metric을 계산하지 않았다.
- 이 결과로 MI48 성능, Raspberry Pi 성능, physical 성능, 안전 기능 권한, 기본 모델 교체, competition candidate lock을 주장할 수 없다.

## 11. 앞으로 작업 시 반드시 반영할 규칙

다음 public stage 후보는 `B6R-P1 — Public SDT Controlled Training`이며 별도 사용자 승인이 필요하다.

1. P1은 exact `PUBLIC_SDT_48000_THERMAL_ONLY_V1`과 `PUBLIC_SDT_BILINEAR_62X80_FRAME_MINMAX_V1`을 입력 identity로 사용한다.
2. TRAIN만 model parameter fitting에 사용하고 DEVELOPMENT만 epoch/model/threshold 선택에 사용한다.
3. `LOCKED_PUBLIC_TEST`는 모델 선택·튜닝에 사용하지 않는다. 별도 최종 public 평가 승인이 있을 때까지 metric 경로에서 열지 않는다.
4. model ID, checkpoint, TFLite, manifest를 legacy와 별도 경로에 저장하고 기존 기본 model/manifest를 덮어쓰지 않는다.
5. `default_activation=false`, `safety_authority=false`, `deployment_mode=SHADOW_ONLY`를 유지한다.
6. public 결과를 MI48·physical·실제 낙상 성능으로 표현하지 않는다.
7. 본선 재개는 권위 MI48 payload/provenance를 복구한 뒤 B6R-1 새 revision과 B6R-2를 다시 통과하는 별도 작업이다.

## 12. Stage Gate 판정

최종 판정: `PASS_WITH_LIMITATIONS — PUBLIC_DATA_ONLY`

B6R-P0의 목표인 read-only materialization, split role lock, preprocessing/label identity, sample provenance, 결정론, 원본 불변 검증은 완료됐다. 제한은 stage 실패가 아니라 public SDT가 MI48·physical 안전 근거를 제공하지 않는다는 명시적 범위다.

## 13. Rollback / STOP

tracked 변경은 신규 public contract, scripts/tests, manifest evidence, roadmap/index/report뿐이다. local materialized payload는 Git에 포함하지 않았다. delivery commit은 일반 `git revert`로 되돌릴 수 있으며 legacy runtime/model 동작에는 영향이 없다.

`STOP — B6R-P1은 새 사용자 승인 없이 실행하지 않는다.`
