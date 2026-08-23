# Thermal B6-R Development Index

이 문서는 Thermal / MI48 B6-R 작업의 단일 탐색 지점이다. 과학적 판정은 각 stage 보고서를 우선하며, 이 인덱스는 보고서를 대체하지 않는다.

## Current Active Branch

`feature/thermal-b6r-development`

모든 B6-R 단계 작업은 사용자가 승인한 한 stage 또는 한 wave만 이 브랜치에서 수행한다. stage별 브랜치를 새로 만들지 않는다.

## Authoritative Roadmap

`docs/20260822_Codex_Thermal_B6R_Robust_Relative_FP32_Parallel_Roadmap_KO_01.md`

## Repository Main Documentation

`docs/README.md`

## Stage Status

| Stage | Status | Report | Artifact | Commit | Notes |
|---|---|---|---|---|---|
| B6R-0 | `FAIL` | `docs/reports/20260822_LunaMax_Agent2_Thermal_B6R0_Asset_Baseline_Verification_01.md` | `datasets/thermal/manifests/B6R-0_asset_baseline_verification/` | source `ee966f9186915a2364e81f944f45aabf22b7b71c`; merge `c70d994ecd4be666dd46e0b7b06872ee8f97f0f2` | B5 checkpoint와 B5 candidate binary가 materialize되지 않았고 TensorFlow/LiteRT 및 Pi 증거가 없다. |
| B6R-1 | `INCONCLUSIVE` | `docs/reports/20260822_LunaMax_Agent1_Thermal_B6R1_MI48_Inventory_01.md` | `datasets/thermal/manifests/B6R-1_mi48_inventory/` | source `d87d452372cc890e85ec6c4d5ec117052be865df`; merge `d0c0c911eb2e27cf91d8f057d1cc9f9360c7fb6a` | authoritative MI48 snapshot을 찾지 못했고 MI48 eligible frame은 0이다. profiler와 focused test는 보존했다. |
| B6R-2 | `NOT_STARTED` | - | - | - | B6R-1 data gate가 충족되지 않았다. |
| B6R-3 | `NOT_STARTED` | - | - | - | - |
| B6R-4 | `NOT_STARTED` | - | - | - | - |
| B6R-5 | `NOT_STARTED` | - | - | - | - |
| B6R-6 | `NOT_STARTED` | - | - | - | - |
| B6R-7 | `NOT_STARTED` | - | - | - | - |
| B6R-8 | `NOT_STARTED` | - | - | - | - |
| B6R-9 | `NOT_STARTED` | - | - | - | - |
| B6R-10 | `NOT_STARTED` | - | - | - | - |
| B6R-11 | `NOT_STARTED` | - | - | - | - |
| B6R-12 | `NOT_STARTED` | - | - | - | - |
| B6R-13 | `NOT_STARTED` | - | - | - | - |
| B6R-14 | `NOT_STARTED` | - | - | - | - |

## Historical Source Branches

| Branch | Original tip SHA | Related PR | Unified branch preservation | Deletion status |
|---|---|---|---|---|
| `codex/thermal-b6r0-asset-baseline-audit` | `ee966f9186915a2364e81f944f45aabf22b7b71c` | #125, `OPEN` at audit time | full `--no-ff` merge; report and manifest directory preserved | local `NOT_DELETED_WORKTREE_IN_USE`; remote `NOT_DELETED_APPROVAL_REJECTED` |
| `codex/thermal-b6r1-mi48-inventory-v2` | `d87d452372cc890e85ec6c4d5ec117052be865df` | #124, `OPEN` at audit time | full `--no-ff` merge; report, manifest directory, profiler, and test preserved | local `DELETED`; remote `NOT_DELETED_APPROVAL_REJECTED` |
| `docs/thermal-b6r-robust-relative-roadmap` | `37f5b2dd914654a12539149317b0895cdf47c00b` | #117, `MERGED` | already an ancestor of `origin/main`; authoritative main copy retained | local `DELETED`; remote `NOT_DELETED_APPROVAL_REJECTED` |
| `codex/thermal-b6r1-mi48-inventory` | `bb5d7fd1518b50297e46858365540cf60ce9e740` | 확인된 전용 PR 없음 | already an ancestor of `origin/main`; unique work 없음 | local `DELETED` |
| `thermal/b6r-1-mi48-inventory` | `bb5d7fd1518b50297e46858365540cf60ce9e740` | 확인된 전용 PR 없음 | already an ancestor of `origin/main`; unique work 없음 | local `DELETED` |

PR #124와 #125는 통합 브랜치로 대체되는 기존 개발 경로다. 감사 시 GitHub CLI 인증 토큰이 유효하지 않아 PR 댓글 또는 종료 작업은 수행하지 않았다. 원격 구브랜치 삭제 요청도 열린 PR의 협업·복구 위험에 대한 별도 명시 승인이 필요하다는 안전 검토로 거부되어 재시도하지 않았다.

## Current Blockers

- B6R-0: B5 FLOAT checkpoint와 B5 FP32/FULL INT8 binary가 현재 환경에 materialize되지 않았다.
- B6R-0: TensorFlow/LiteRT runtime과 Raspberry Pi 하드웨어 증거가 없어 load, parity, latency, memory, stability를 검증할 수 없다.
- B6R-1: authoritative MI48 raw snapshot이 접근 가능한 경로에 없고 외부 `SafeNestssd`가 mount되지 않았다.
- B6R-1: 후보 archive의 MI48 identity가 해소되지 않았으며 식별된 eligible MI48 frame은 0이다.
- B6R-2: session/label/split/holdout 계약을 만들 data gate가 충족되지 않았다.

## Next Authorized Stage

`WAITING_FOR_USER_INSTRUCTION`

통합 작업은 B6R-2 또는 이후 stage를 승인하지 않는다.

## Required Reading Order for Future Agents

1. `docs/README.md`
2. `docs/20260822_Codex_Thermal_B6R_Robust_Relative_FP32_Parallel_Roadmap_KO_01.md`
3. `docs/thermal/B6R_DEVELOPMENT_INDEX.md`
4. 실행하려는 stage의 직접 선행 stage 보고서
5. 직접 선행 stage의 manifest와 artifact
6. roadmap이 요구하는 stage-specific source, test, runtime 파일

## Working Rules

1. `git fetch origin` 후 `feature/thermal-b6r-development`로 진입하고 `git pull --ff-only origin feature/thermal-b6r-development`를 수행한다.
2. 작업 트리가 깨끗한지 확인하고 사용자가 승인한 한 stage 또는 한 wave만 실행한다.
3. 역사적 `FAIL` 또는 `INCONCLUSIVE` 보고서를 덮어쓰거나 `PASS`로 바꾸지 않는다. 재실행은 새 revision 보고서로 남긴다.
4. stage별 전용 보고서를 `docs/reports/`에 생성하고 명시적 경로만 stage한다.
5. stage 결과와 정확한 commit SHA를 이 인덱스에 반영한 뒤 같은 활성 브랜치에 push하고 멈춘다.
6. `main` 통합 PR은 사용자가 milestone 범위를 명시적으로 승인할 때만 준비한다.
