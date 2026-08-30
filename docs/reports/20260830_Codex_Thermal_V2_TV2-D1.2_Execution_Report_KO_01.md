# SafeNest Thermal V2 — TV2-D1.2 TF-66 Access / License / Provenance Contract Verification

- Document ID: `THERMAL_V2_TV2_D1_2_EXECUTION_REPORT_KO_01`
- Date: `2026-08-30`
- Repository: `sheepmeat/test`
- Branch: `thermal-v2/stepwise-execution`
- Commit base: `a1a3fcb239f65b82ebb5e952a2968bee32d0dd21`
- Step ID: `TV2-D1.2`
- Parent Task: `TV2-D1`
- Scope: Thermal Fall 66의 official identity, access route, license scope, release identity, payload form, grouping, split, label semantics 검증
- Status: `PASS_WITH_LIMITATIONS`
- Training Authorization: `NO`
- Locked-test Access: `0`

## 1. Objective

TV2-D1.1 ledger의 `TF_66` record를 공식 paper, Lakehead thesis, thesis에
포함된 project hyperlink, official GitHub repository와 helper metadata에
연결한다. public-vs-request 표현을 해소하고, dataset asset와 repository
helper의 license 범위를 분리하며, payload/grouping/label/split 사실과 남은
blocker를 추측 없이 고정한다.

이 단계는 dataset access request를 제출하거나 raw TF-66 payload를 받는
단계가 아니다. 확인된 계약은 후속 D1.7/D2에서 source eligibility를 판단하기
위한 evidence이고 training authorization이 아니다.

## 2. Scope and Non-goals

수행 범위:

- D0, D1.1 ledger, current roadmap와 repository policy 재검토
- publisher article와 Lakehead thesis의 TF-66 identity/access/grouping 확인
- thesis PDF hyperlink annotation에서 official repository URL 복구
- official repository의 README, license, metadata spreadsheet, generator/cache
  helper만 읽기 전용 확인
- current repository HEAD, tag/release 유무와 access contact 확인
- participant/video/room key와 published validation split의 participant overlap 점검

수행하지 않은 작업:

- TF-66 raw dataset, JPG frame tree, video/archive 또는 owner-delivered payload 수신
- `crsilver@lakeheadu.ca`로 이메일 발송 또는 access request 제출
- terms/waiver 수락, 계정 생성, CAPTCHA/approval 우회
- frame을 canonical/training pool에 추가하거나 cache 생성
- dataset/manifest/split/model/runtime/source code 변경
- training, evaluation, tuning, export, final ranking
- `LOCKED_PUBLIC_TEST`, Team repository, Integration repository 접근 또는 변경
- `TV2-D1.3` action 선행

## 3. Evidence Reviewed

### 3.1 Repository evidence

| Evidence | 사용한 내용 |
|---|---|
| `docs/thermal/20260830_SafeNest_Thermal_V2_Stepwise_Execution_Roadmap_KO_01.md` | 현재 step, D1.2 pass/block boundary, no-training/no-download 규칙 |
| `docs/thermal/20260830_SafeNest_Thermal_V2_TV2-D0_Additional_Dataset_Discovery_01.md` | TF-66 D0 identity, counts, semantic value, 당시 unresolved access/license/payload fields |
| `docs/reports/20260830_Codex_Thermal_V2_TV2-D1.1_Execution_Report_KO_01.md` | stable `source_id=TF_66`, D1.2 입력 ledger와 unresolved boundary |
| repository-local `AGENTS.md` | standalone repository, provenance, explicit staging, no authority inflation 규칙 |

### 3.2 Official external evidence accessed on 2026-08-30

| Official source | 확인한 내용 |
|---|---|
| [Elsevier article DOI](https://doi.org/10.1016/j.engappai.2025.111819) | TF-66 paper identity; Christopher Silver와 Thangarajah Akilan; 66 participants, 9 rooms, 562 fall/250 non-fall videos; 35×15, 4 FPS CTS-EVK; 140×60 rendered frames; staged-fall/non-fall protocol; 80:20 video/frame split; GitHub–TF-66와 request wording |
| [Lakehead thesis record](https://knowledgecommons.lakeheadu.ca/handle/2453/5421) / [official PDF](https://knowledgecommons.lakeheadu.ca/bitstreams/5bc4a511-bebd-4a06-9b95-384f888c36c4/download) | university-hosted provenance; room/participant table; `X-Y-Z` recording naming; Train/Test structure; non-fall activities; embedded project hyperlink |
| [Official TF-66 repository](https://github.com/Christopher-Silver/TF-66) | public helper repository, request contact, non-commercial condition, helper inventory |
| [README at observed commit](https://github.com/Christopher-Silver/TF-66/blob/bc1678d5e9f6fa262b9744b5fd72489c3351b0aa/README.md) | access requires email to Chris Silver at `crsilver@lakeheadu.ca`; dataset is non-commercial only; red spreadsheet rows are validation selection |
| [License at observed commit](https://github.com/Christopher-Silver/TF-66/blob/bc1678d5e9f6fa262b9744b5fd72489c3351b0aa/License.txt) | repository work/software states CC BY-NC 4.0 and no commercial use |
| [Metadata spreadsheet](https://github.com/Christopher-Silver/TF-66/blob/bc1678d5e9f6fa262b9744b5fd72489c3351b0aa/Final%20Dataset.xlsx) | 812 video rows, Volunteer/Recording/label/action/fall-frame/room/height fields, summary split counts, red validation markings |
| [DataGenerator.py](https://github.com/Christopher-Silver/TF-66/blob/bc1678d5e9f6fa262b9744b5fd72489c3351b0aa/DataGenerator.py) / [Create_Cache.ipynb](https://github.com/Christopher-Silver/TF-66/blob/bc1678d5e9f6fa262b9744b5fd72489c3351b0aa/Create_Cache.ipynb) | `.jpg` frame lookup, `<participant>-<Fall\|NonFall>-<sequence>` labels, grayscale 256×256 helper transform, float32 `/255`, local `.npz` cache |
| [Observed repository commit](https://github.com/Christopher-Silver/TF-66/commit/bc1678d5e9f6fa262b9744b5fd72489c3351b0aa) | `main` HEAD snapshot; no tag/release was advertised or returned by refs inspection |

Search-result snippets, third-party mirrors, guessed repository names, paper-level
open-access badges는 dataset permission의 최종 근거로 사용하지 않았다.

## 4. Actions Performed

1. branch/remote/HEAD/worktree를 확인하고 origin branch와 fast-forward 동기화했다.
2. D0, D1.1, roadmap, repository policy를 다시 읽고 D1.2 boundary를 확인했다.
3. publisher article과 Lakehead official thesis를 검토했다.
4. thesis PDF의 hyperlink annotation을 읽어 official project URL
   `https://github.com/Christopher-Silver/TF-66`를 복구했다.
5. official repository README/license/helper inventory와 Git refs/API metadata를
   읽기 전용으로 확인했다.
6. raw dataset 대신 repository의 공개 helper files만 observed commit SHA에
   고정해 임시 검토했다.
7. official spreadsheet의 값과 표시 style을 읽기 전용으로 점검하여 split
   counts, group key, participant overlap을 계산했다.
8. cache instruction PDF는 text extraction과 rendered page를 교차 확인했다.
9. 어떤 access email도 보내지 않았고 dataset payload/cache를 생성하지 않았다.

## 5. TF-66 Contract Evidence Row

| Field | Verified state | Evidence / limitation |
|---|---|---|
| `source_id` | `TF_66` | D1.1 stable ID 유지 |
| official name | Thermal Fall 66 (TF-66) | article, thesis, official repository가 일치 |
| authors / maintainer | Christopher Silver; Thangarajah Akilan; repository account `Christopher-Silver` | primary author/contact와 maintainer는 확인; dataset의 법적 owner/licensor 명시는 별도 없음 |
| publisher / institution | Elsevier, *Engineering Applications of Artificial Intelligence*; Lakehead University thesis repository | publisher는 paper에 대한 주체이며 dataset owner로 확대하지 않음 |
| official project route | `https://github.com/Christopher-Silver/TF-66` | thesis embedded hyperlink로 provenance 연결 |
| access class | `REQUEST_ONLY / NON_COMMERCIAL_ONLY` | README가 `crsilver@lakeheadu.ca` 이메일 요청을 요구; public GitHub는 helper 공개이지 raw dataset direct download가 아님 |
| current direct payload access | `NO` | public archive/download URL 없음; request를 제출하지 않았으므로 payload 미수신 |
| observed version | helper repo `main@bc1678d5e9f6fa262b9744b5fd72489c3351b0aa`; commit date `2025-09-14` | tag/release 없음; delivered dataset version/checksum/manifest는 `UNRESOLVED` |
| helper license | `CC-BY-NC-4.0` statement present | `License.txt`가 “this work/software”에 적용된다고 서술 |
| dataset asset license | `LICENSE_UNRESOLVED` | README의 non-commercial restriction은 확인되지만 요청 전달 payload의 복제·수정·재배포·파생 artifact 조건과 License.txt의 dataset scope가 명시되지 않음 |
| capture identity | Calumino CTS-EVK, ceiling-mounted, native 35×15, 4 FPS | article/thesis evidence |
| distributed payload form | `PROVISIONAL_RENDERED_JPG_FRAME_TREE` | official helper가 Train/Validation 아래 `.jpg`를 순회하고 repository path가 `TF66_Colour`을 사용; 실제 delivered payload를 열지 않아 exact member list/codec/bit depth는 미확인 |
| thermal representation | `RENDERED_THERMAL_INTENSITY`, radiometric status `UNRESOLVED/NOT_ESTABLISHED` | article/thesis는 140×60 display image와 static 0–30 °C playback range를 설명; JPEG pixel이 Celsius/raw radiometry라는 근거는 없음 |
| helper transform | grayscale, resize 256×256, float32 `/255`, compressed local NPZ | source payload contract가 아니라 optional cache/training helper transform |
| strongest group key | `Volunteer ID` | IDs `01`–`66`; recording name의 첫 component와 일치 |
| recording key | `<VolunteerID>-<Fall\|NonFall>-<sequence>` | video/sequence identity는 명시; 별도 session ID는 없음 |
| environment key | `Room ID` + room height | 9 rooms; participant-to-room mapping은 thesis/spreadsheet에 존재 |
| label semantics | staged `Fall` video vs `NonFall` activity video | fall onset/context frame fields 존재; natural/clinical falls가 아님 |
| published split | about 80:20 balanced by video count and frame/time volume | participant-disjoint 기준이 아님; repository는 Train/Validation naming도 사용하여 paper의 Train/Test 표현과 명칭 차이 존재 |
| SafeNest role | `CANDIDATE_EVIDENCE_ONLY`; no training inclusion | access/asset-license/representation/split contract가 완결되기 전 training pool 추가 금지 |

## 6. Access and License Findings

1. **Public wording가 direct public download를 뜻하지 않는다.** 논문과 thesis는
   publicly available/non-commercial로 표현하지만 official README의 현재
   실행 절차는 primary author에게 이메일을 보내는 request-only 방식이다.
2. **정확한 access route는 복구되었다.** official repository와
   `crsilver@lakeheadu.ca`가 확인되어 D1.1의 project/access URL blocker는
   해소됐다. 그러나 request는 사용자 소속·목적과 외부 통신을 수반하므로 이
   단계에서 대신 제출하지 않았다.
3. **helper license와 dataset asset permission은 분리한다.** License.txt는
   CC BY-NC 4.0과 non-commercial restriction을 명시하지만 “work/software”
   표현을 사용하고 raw dataset은 repository에 없다. 따라서 helper의
   CC-BY-NC statement는 verified지만 owner-delivered payload의 asset-level
   license는 `LICENSE_UNRESOLVED`로 유지한다.
4. **non-commercial은 완전한 license가 아니다.** attribution, copying,
   redistribution, modified/derived dataset, model/artifact release, recipient
   sharing 조건은 현재 public page에서 완결되지 않는다.
5. **release identity는 immutable하지 않다.** helper repository의 observed
   commit은 고정할 수 있지만 dataset tag/release/version/checksum/file manifest는
   없다. owner delivery 시 별도 release identity를 받아야 한다.

## 7. Payload and Representation Findings

- Capture source는 ceiling-mounted Calumino CTS-EVK이며 native resolution은
  35×15, 4 FPS다.
- paper/thesis는 vendor playback의 4× upscale로 140×60 image를 만들고 static
  color range를 0–30 °C로 설정했다고 설명한다.
- official helper는 directory의 `.jpg` frame을 읽는다. cache helper는 이를
  grayscale 256×256으로 resize하고 float32 `/255`로 정규화하여 local compressed
  NPZ에 넣는다.
- 그러므로 확인된 distribution-facing representation은 raw/radiometric matrix가
  아니라 **rendered JPG frame tree**로 잠정 분류한다. palette/channel order,
  JPEG bit depth, compression quality, exact 140×60 member shape, orientation,
  invalid-pixel semantics와 temperature recoverability는 실제 payload 전에는
  확정할 수 없다.
- cache helper의 256×256 grayscale float는 원본 dataset 특성이 아니라
  downstream preprocessing 예시다. 이를 SafeNest canonical 62×80 contract로
  오인하지 않는다.

## 8. Grouping and Split Audit

Official spreadsheet는 812개 recording row를 가지며 summary는 다음을 기록한다.

| Split evidence | Fall | NonFall | Total |
|---|---:|---:|---:|
| all videos | 562 | 250 | 812 |
| spreadsheet summary validation | 113 | 50 | 163 |
| spreadsheet summary train | 449 | 200 | 649 |
| red-row style audit | 112 | 50 | 162 |

확인된 split 제한:

- README는 red rows가 validation set이라고 설명하지만 현재 spreadsheet style
  audit는 summary보다 fall validation 1개가 적다. 어느 recording이 의도된
  validation member인지 owner clarification이 필요하다.
- red-row markings 기준 validation에는 58명 participant가 있고, 그 58명 모두
  training에도 나타난다. training에는 66명 전원이 나타난다.
- 따라서 published 80:20 split은 명백히 participant-disjoint가 아니다. correlated
  frames/windows가 같은 video boundary를 넘어 섞이지 않더라도 subject leakage를
  막는 split으로 사용할 수 없다.
- 가장 강한 future split unit는 `Volunteer ID`다. recording name을 video key로,
  Room ID를 environment audit key로 보존해야 한다. 별도 session identity는
  제공되지 않는다.
- 기존 red split은 paper result reproduction reference로만 보존하고 SafeNest
  generalization split으로 자동 채택하지 않는다.

## 9. Label and Event Semantics

- TF-66의 fall은 참가자가 수행한 staged/simulated fall이다. thesis/paper의
  protocol은 다양한 fall templates와 physiotherapist-informed review를 다루지만
  natural 또는 clinical incident truth는 아니다.
- recording label은 filename과 spreadsheet에서 `Fall`/`NonFall`로 일치한다.
- fall rows는 `First Fall Frame of Video`, `framesBeforeFall`, `framesAfterFall`을
  제공하므로 temporal event window 구성 evidence가 있다.
- non-fall에는 walking, sitting, cleaning과 같은 ADL 및 15초 이상 motionless인
  sequence가 포함된다. 이는 hard-negative 가치가 있지만 row의 action text를
  SafeNest class로 자동 relabel할 권한은 아니다.
- static lying, fall aftermath, intentional floor activity와 ambiguous transition을
  source의 binary video label만으로 완전히 분리할 수 없다. D2 label mapping 전에는
  `HUMAN_FALL_PROXY` 이상의 임상적 의미를 부여하지 않는다.

## 10. Findings

1. D1.1에서 미확정이던 official project URL은 thesis PDF의 embedded hyperlink로
   복구했고 official repository identity와 일치한다.
2. 현재 access는 exact request route가 있는 `REQUEST_ONLY`; public helper
   repository가 raw dataset direct access를 제공하는 것은 아니다.
3. helper repository에는 CC BY-NC 4.0 statement가 있지만 request-delivered
   dataset asset에 대한 license scope와 redistribution/derived-artifact 권한은
   계속 `LICENSE_UNRESOLVED`다.
4. helper source는 JPG frame tree와 optional grayscale/cache transform을 확인해
   주지만 actual payload member/codec/bit depth/radiometry를 완전히 검증하지 못한다.
5. participant/video/room grouping은 강하게 식별되지만 session ID는 없다.
6. published 80:20 split은 video/frame balance 기준이고 participant leakage가
   존재한다. red-row marker와 summary에도 1개 fall-video 불일치가 있다.
7. TF-66은 broad staged-fall/ADL temporal source로 의미가 있으나 현재 evidence는
   access request, asset terms, representation test와 subject-disjoint resplit 전의
   training inclusion을 승인하지 않는다.

## 11. Unresolved Items

- owner-delivered dataset payload에 적용되는 exact license/terms 전문
- dataset legal owner/licensor와 License.txt의 raw payload 적용 범위
- permitted copying, redistribution, derived dataset/model/artifact release 조건
- access request 승인 기준, delivery mechanism, current dataset version/date
- immutable archive ID, tag, checksum, complete file manifest
- actual JPG dimensions/channel order/palette/bit depth/compression/orientation
- raw radiometric values 또는 Celsius recoverability 여부
- spreadsheet summary 대비 누락된 red fall-validation row 1개의 identity
- 별도 session ID와 repeated capture/session boundary
- exact participant demographics와 consent/secondary-use restriction의 delivery terms

이 항목은 숨기거나 성공으로 상향하지 않는다. 특히 asset license는
`LICENSE_UNRESOLVED`, payload는 `ACCESS_NOT_INSPECTED_REQUEST_REQUIRED`로 남는다.

## 12. User Action Queue

TV2-D1.2 문서 완료를 위해 즉시 필요한 사용자 action은 없다. 실제 TF-66을
후속 단계에서 training candidate로 검토하려면 사용자가 다음 external action을
명시적으로 승인하고 필요한 소속/연구 목적을 직접 제공해야 한다.

| Action | Official route | 요청 시 확인해야 할 항목 | Codex에 필요한 결과 |
|---|---|---|---|
| dataset access/terms 문의 | `crsilver@lakeheadu.ca` ([official README](https://github.com/Christopher-Silver/TF-66/blob/bc1678d5e9f6fa262b9744b5fd72489c3351b0aa/README.md)) | non-commercial research purpose, affiliation, exact asset license, redistribution/derived-output rights, version/checksum, split marker discrepancy | owner reply와 terms/version text; raw frames 자체는 D1 evidence에 불필요 |

본 실행에서는 이메일을 작성·발송하거나 request를 제출하지 않았다.

## 13. Artifacts Created / Modified

- Created: `docs/reports/20260830_Codex_Thermal_V2_TV2-D1.2_Execution_Report_KO_01.md`
- Modified: `docs/thermal/20260830_SafeNest_Thermal_V2_Stepwise_Execution_Roadmap_KO_01.md`
- Temporary read-only review material: official paper/helper metadata under ignored
  `tmp/`; Git change set에는 포함하지 않음
- Not modified: dataset, split, manifest, source code, model, runtime, Team/Integration
  repository

## 14. Validation

검증 항목:

- required header 11개와 required body section 존재
- official paper → Lakehead thesis → embedded GitHub URL → repository README/license
  provenance chain 연결
- observed helper repository SHA와 no-tag/no-release state 기록
- public helper vs request-only dataset access 문구 분리
- helper license vs dataset asset license scope 분리; `LICENSE_UNRESOLVED` 보존
- payload route, representation certainty, participant/video/room grouping과 label
  semantics에 evidence 또는 explicit unresolved status 존재
- spreadsheet 812 rows 및 562/250 totals 확인
- summary split 113/50과 red-style 112/50 discrepancy 확인
- red validation participant 58명 전원이 training과 overlap함을 확인
- raw dataset 수신, cache 생성, training, model/data/runtime mutation 없음
- roadmap의 단일 next step이 `TV2-D1.3`, training authorization은 `NO`
- 변경 파일이 report와 roadmap 두 개로 제한
- Markdown focused check, `git diff --check`, explicit staged diff 검증 수행

검증 결과는 `PASS_WITH_LIMITATIONS`다. limitation은 access/asset-license/payload와
split integrity의 명시적 미해결 상태이며 D1.2 evidence contract에서 숨기지 않았다.

## 15. Decision

`PASS_WITH_LIMITATIONS`

통과 근거:

- exact official project와 request route를 복구했다.
- helper license statement와 dataset asset license uncertainty를 분리했다.
- observed release snapshot, payload route, strongest group key, fall/non-fall
  semantics와 published split limitation을 source-specific evidence로 고정했다.
- direct payload를 받을 수 없는 상태를 `REQUEST_ONLY`로 정확히 기록했고,
  `LICENSE_UNRESOLVED`를 성공으로 위장하지 않았다.
- forbidden download/import/training/locked-test action이 없다.

제한:

- owner-delivered dataset의 asset-level license와 release manifest가 없다.
- 실제 payload를 검토하지 않아 exact representation/codec/radiometry는 provisional이다.
- existing validation split은 participant-disjoint가 아니며 marker discrepancy가 있다.

## 16. Gate Impact

- `TV2-D1.2`: `DONE_WITH_LIMITATIONS / PASS_WITH_LIMITATIONS`
- `TF_66`: official identity와 request route verified; asset license
  `LICENSE_UNRESOLVED`; payload `REQUEST_REQUIRED_NOT_INSPECTED`
- `TV2-D1.3`: `NEXT`
- Parent `TV2-D1`: 계속 진행 중; D1 gate PASS가 아님
- `G1`: 계속 `PLANNED / BLOCKED_BY_D1_D2_D3`
- Training authorization: `NO`
- Locked-test access count: `0`

## 17. Next Authorized Step

`TV2-D1.3`

## 18. Git Evidence

Execution start:

~~~text
branch: thermal-v2/stepwise-execution
HEAD: a1a3fcb239f65b82ebb5e952a2968bee32d0dd21
origin/thermal-v2/stepwise-execution: a1a3fcb239f65b82ebb5e952a2968bee32d0dd21
starting worktree: clean
pull: Already up to date (fast-forward only)
~~~

Pre-commit change set은 section 13의 report와 roadmap으로만 제한한다. delivery
commit과 pushed remote equality는 content freeze 후 검증하며 아직 존재하지 않는
future commit hash를 본문에 추측해 쓰지 않는다.

~~~text
git status --short
 M docs/thermal/20260830_SafeNest_Thermal_V2_Stepwise_Execution_Roadmap_KO_01.md
?? docs/reports/20260830_Codex_Thermal_V2_TV2-D1.2_Execution_Report_KO_01.md

git log -1 --oneline
a1a3fcb docs(thermal-v2): freeze source evidence ledger
~~~

새 report는 staging 전 `git diff --stat`에 나타나지 않으므로 explicit status와
staged diff를 함께 검증한다. `git add .`는 사용하지 않는다.
