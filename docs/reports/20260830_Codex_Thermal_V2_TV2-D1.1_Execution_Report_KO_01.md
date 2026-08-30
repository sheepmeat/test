# SafeNest Thermal V2 — TV2-D1.1 Source Evidence Ledger Freeze

- Document ID: `THERMAL_V2_TV2_D1_1_EXECUTION_REPORT_KO_01`
- Date: `2026-08-30`
- Repository: `sheepmeat/test`
- Branch: `thermal-v2/stepwise-execution`
- Commit base: `dd945c07e61e7235a80e86d681fb8f7038496b56`
- Step ID: `TV2-D1.1`
- Parent Task: `TV2-D1`
- Scope: D0 source inventory와 source-by-source D1 evidence ledger freeze; public landing-page metadata만 검토
- Status: `PASS_WITH_LIMITATIONS`
- Training Authorization: `NO`
- Locked-test Access: `0`

## 1. Objective

TV2-D0가 독립 source 또는 독립 source군으로 보존한 항목을 누락 없이
stable `source_id`에 연결하고, D1.2–D1.6의 source-specific 검증 및 D1.7의
정규화에 사용할 canonical evidence ledger를 고정한다.

이 보고서의 ledger는 source를 승인하거나 ranking을 상향하는 문서가 아니다.
공식 metadata로 확인된 사실과 후속 payload/terms/grouping 검증이 필요한
사실을 분리하며, 확인되지 않은 값은 빈칸이나 추측 대신 명시적인 상태로
보존한다.

## 2. Scope and Non-goals

수행 범위:

- D0, Master Map, stepwise roadmap, G1 foundation, H0, T-A0 source identity 읽기
- D0 전체의 serious/reference/low-value/rejected/unresolved source crosswalk 작성
- official paper/project/repository/archive landing page와 공개 license 문구 확인
- paper, code, dataset/asset license 경계 분리
- source별 identity, access, representation, grouping, label evidence와 다음 step 고정

수행하지 않은 작업:

- raw archive, video, image, CSV, annotation 또는 dataset payload 다운로드
- Google Drive, OSF, Figshare, Zenodo archive hydration/추출
- access 신청, 이메일 발송, CAPTCHA 해결, account 생성, terms/waiver 수락
- dataset/canonical/split/manifest 변경 또는 derived artifact 생성
- training, evaluation, tuning, export, model/runtime selector 변경
- `LOCKED_PUBLIC_TEST`, Team repository, Integration repository 접근 또는 변경
- `TV2-D1.2` 이후의 source-specific gate 판정

## 3. Evidence Reviewed

### 3.1 Repository evidence

| Evidence | D1.1에 사용한 내용 |
|---|---|
| `docs/thermal/20260830_SafeNest_Thermal_V2_Stepwise_Execution_Roadmap_KO_01.md` | `CURRENT_STEP=NEXT_STEP=TV2-D1.1`, `TRAINING_AUTHORIZED=NO`, D1.2–D1.6 source order와 D1 field boundary |
| `docs/thermal/20260830_SafeNest_Thermal_V2_Master_Execution_Map_01.md` | G0 PASS, standalone repository boundary, no-training/no-final-selection boundary |
| `docs/thermal/20260830_SafeNest_Thermal_V2_TV2-D0_Additional_Dataset_Discovery_01.md` | canonical D0 source inventory, classification, intended roles, official links, limitations |
| `docs/thermal/20260830_SafeNest_Thermal_V2_G1_Model_Contract_Foundation_01.md` | source/group/split/label/provenance required fields와 static/event proxy boundary |
| `docs/thermal/20260830_SafeNest_Thermal_V2_TV2-H0_SDT_Hard_Negative_Audit_01.md` | SDT reference role, missing hard-negative taxonomy, proxy-claim boundary |
| `docs/reports/20260810_Codex_T-A0_Thermal_Dataset_Selection_Source_Identity_01.md` | SDT와 local Family A/screenshot tree의 identity/provenance/access history |

### 3.2 Official public sources accessed on 2026-08-30

| Official source | 확인한 내용 |
|---|---|
| [TF-66 publisher article](https://doi.org/10.1016/j.engappai.2025.111819) | paper identity, authors/publisher, 66 participants, 9 environments, 562 fall/250 non-fall videos, CTS-EVK 35×15 at 4 FPS, public/non-commercial wording와 request wording의 불일치 |
| [IPHPDT paper](https://doi.org/10.3390/s23010092) | IPHPDT derivative identity, four posture classes, 약 75k images, author-request availability, paper-level open-access boundary |
| [IPHD official ChaLearn page](https://chalearnlap.cvc.uab.cat/dataset/34/description/) | underlying IPHD identity, thermal/depth variants, 160×120 original thermal, challenge partitions/file links, video ID evidence; IPHPDT posture labels와의 별도 권한 경계 |
| [Thermal-IM official repository](https://github.com/ZitianTang/Thermal-IM) | dataset identity, dataset BSD-3-Clause statement, Google Drive route, 783 clips, `meta.csv`, actor/room/scene/split fields, `RGBT_T.mp4` 288×384 15 FPS, annotation schema |
| [Thermal-IM paper](https://openaccess.thecvf.com/content/CVPR2023/html/Tang_What_Happened_3_Seconds_Ago_Inferring_the_Past_With_Thermal_CVPR_2023_paper.html) | paper identity와 normal indoor human-object interaction scope |
| [QUIDA PeerJ/PMC article](https://pmc.ncbi.nlm.nih.gov/articles/PMC11970414/) | OSF data route, 10 subjects, simulated fall protocol, per-subject directories, FIR CSV 32×24 °C, Unix timestamps, `Falls.csv`; paper license와 dataset terms 분리 필요 |
| [QUIDA OSF DOI](https://doi.org/10.17605/OSF.IO/YJGDV) | official archive identity/access route; asset-level license는 landing metadata에서 확정하지 못함 |
| [eHomeSeniors paper](https://pmc.ncbi.nlm.nih.gov/articles/PMC6832422/) | six volunteers, 15 fall types, 448 retained falls, MLX90640/Omron sensor forms, 180 CSV files, subject/sensor/fall-type naming |
| [eHomeSeniors supplement](https://www.mdpi.com/1424-8220/19/20/4565/s1) / [officially linked Figshare package](https://figshare.com/s/753cc0df15197b0b9572) | public supplement route; Figshare page는 이 실행 환경에서 403으로 metadata 확인 불가, 따라서 asset terms 미확정 |
| [SDT official CVL page](https://cvl.tuwien.ac.at/research/cvl-databases/sdt-icip/) / [Zenodo record](https://doi.org/10.5281/zenodo.4124309) | 40k synthetic + 8k real, lying/sitting/standing/empty, FLIR Lepton 3.5, non-commercial research/citation terms; Zenodo landing은 429로 재확인 제한 |
| [MUVIM official repository](https://github.com/MUVIM/FallDetection) / [paper](https://arxiv.org/abs/2206.12740) | four modalities, email request fields, privacy waiver, corruption/lost-trial warnings; dataset license 부재 |
| [TSF official repository](https://github.com/ivineetm007/Fall-detection) / [paper](https://arxiv.org/abs/2004.08352) | 9 ADL + 35 fall/other-normal thermal videos, 640×480, email request; repository code license가 dataset license라는 근거는 없음 |
| [LWIRPOSE official repository](https://github.com/avinres/LWIRPOSE) / [paper](https://arxiv.org/abs/2404.10212) | request form, 2,400+ LWIR images, seven actors, daily activities/pose scope; dataset license 미표시 |
| [TADAR official repository](https://github.com/aiot-lab/TADAR) / [paper DOI](https://doi.org/10.1145/3641512.3686357) | thermal-array ranging source, linked archive route, code MIT; dataset/asset license와 SafeNest posture/fall label contract 미확정 |
| [TsetFall official repository](https://github.com/ppgia-unifor/TsetFall_dataset) | JPEG/MP4/CSV structure, four-camera visible-image activity/fall semantics, key-request form; thermal source가 아님 |
| [TST IEEE DataPort DOI](https://doi.org/10.21227/H2QP48) | depth/skeleton/accelerometer fall dataset identity; thermal modality가 아님 |

검색 결과 snippet이나 제3자 재배포 페이지는 license 또는 permission의 최종
근거로 사용하지 않았다. 직접 열리지 않은 official archive는 해당 사실 자체를
`ACCESS_NOT_VERIFIABLE`로 기록했다.

## 4. Actions Performed

1. `git status --short --branch`, branch, remote, HEAD를 확인했다.
2. `git fetch origin`과 `git pull --ff-only origin thermal-v2/stepwise-execution`을 수행했고 시작 HEAD `dd945c07...`가 원격과 동일함을 확인했다.
3. repository-local `AGENTS.md`와 필수 문서 5개 및 D0가 직접 참조한 T-A0 source identity 보고서를 읽었다.
4. D0의 표, heading, 본문, rejected/low-value section을 구조적으로 대조하여 17개 ledger record를 만들었다.
5. 공식 paper/project/repository/archive/license landing metadata만 확인했다. raw payload는 열거나 다운로드하지 않았다.
6. IPHPDT derivative와 underlying IPHD를 별도 `source_id`로 분리했다.
7. canonical normalized ledger, D0 crosswalk, 후속 source order, deferred user-action queue를 작성했다.

## 5. Stable Source-ID Policy

- `source_id`는 대문자 ASCII와 underscore만 사용한다.
- 공식 약칭이 명확하면 재사용한다: `SDT`, `TF_66`, `IPHD`, `QUIDA`.
- display name/역사적 이름/철자 변형은 `aliases`에 보존하고 ID를 바꾸지 않는다.
- derivative와 underlying source의 permission boundary가 다르면 별도 ID를 준다:
  `IPHPDT`와 `IPHD`.
- local identity 불명 artifact와 D0가 묶은 비열화상 source군은 하나의 공개
  dataset으로 추측하지 않는다. 각각 `LOCAL_*` 또는 `*_SOURCE_GROUP` ID로
  inventory history만 보존한다.
- source가 후속 단계에서 REJECT/REFERENCE_ONLY가 되어도 ID를 재사용하거나
  삭제하지 않는다.

## 6. Canonical D1 Evidence Ledger

이 절의 다섯 표는 `source_id`를 primary key로 하는 하나의 normalized
canonical ledger다. 표 A의 source ID 집합은 표 B–E와 정확히 같아야 한다.
빈 값은 허용하지 않으며 `UNRESOLVED`, `ACCESS_NOT_VERIFIABLE`,
`LICENSE_UNRESOLVED`, `REFERENCE_ONLY`, `REJECT`, 또는 후속 step 상태로
채운다.

### 6.1 Ledger A — identity, classification, role

| source_id | Source name | Aliases | D0 classification | D0 intended role | Owner / publisher | Official identity |
|---|---|---|---|---|---|---|
| `TF_66` | Thermal Fall 66 | TF-66 | `HIGH_VALUE`; operational `D1-BLOCKED` | broad temporal fall + ADL/non-fall candidate | Christopher Silver et al.; Elsevier paper; dataset owner boundary `PENDING_TV2-D1.2` | DOI article identifies a 66-participant ceiling-mounted thermal fall dataset |
| `IPHPDT` | Identity-Preserved Human Posture Detection in Thermal Images dataset | IPHPDT | `PROMISING_WITH_ADAPTATION` | static bending/sitting/lying posture hard-negative derivative | Yongping Guo et al.; MDPI/Sensors; corresponding-author distribution | paper-defined posture-labeled derivative built from thermal human images; permission boundary differs from IPHD |
| `IPHD` | Identity-Preserved Human Detection dataset | ChaLearn LAP IPHD | linked underlying source; `PROMISING_WITH_ADAPTATION` boundary evidence | underlying thermal frames/detection annotations; not automatically IPHPDT labels | ChaLearn LAP / CVC-UAB challenge | official ChaLearn dataset 34, depth and thermal human-detection challenge data |
| `THERMAL_IM` | Thermal Indoor Motion Dataset | Thermal-IM | `PROMISING_WITH_ADAPTATION` | normal-motion and posture/context hard negatives | Zitian Tang et al.; official GitHub repository | CVPR 2023 Thermal-IM synchronized RGB/thermal/depth indoor-motion dataset |
| `QUIDA` | Multi-Sensor Fall Detection dataset | QUIDA; Multi-Sensor Fall Detection | `PROMISING_WITH_ADAPTATION` | low-resolution calibrated-temperature temporal fall/event reference | Miguel Pineiro et al.; OSF; PeerJ | PeerJ article and OSF DOI identify a 10-subject multisensor simulated-fall dataset |
| `EHOME_SENIORS` | eHomeSeniors Dataset | eHomeSeniors | `REFERENCE_ONLY` to `PROMISING_WITH_ADAPTATION` | MLX90640/Omron schema and staged-fall temporal/sensor reference | F. Riquelme et al.; MDPI/Sensors; linked Figshare package | paper-defined six-volunteer infrared thermal fall dataset and supplement |
| `SDT` | Synthetic Depth & Thermal Dataset | SDT; Simulated/real thermal fall posture data | `REFERENCE_ONLY` for additional-data lane | current baseline/source and sensor/label reference | TU Wien Computer Vision Lab; Pramerdorfer et al.; Zenodo | official CVL SDT: 40k synthetic + 8k real depth/thermal posture images |
| `MUVIM` | Multi Visual Modality Fall Detection Dataset | MUVIM | `UNRESOLVED`; access restricted | multimodal fall/ADL scientific reference; not current top candidate | University of Toronto authors / MUVIM repository | paper/repository identify IR, depth, RGB, thermal fall dataset |
| `TSF` | Thermal Simulated Fall | TSF; Thermal Simulated Fall dataset | `REFERENCE_ONLY` / `LOW_VALUE` | historical thermal fall method reference | Vineet Mehta et al.; official Fall-detection repository | repository-defined 9 ADL and 35 fall/other-normal thermal videos |
| `LWIRPOSE` | LWIRPOSE dataset | LWIRPOSE | `REFERENCE_ONLY` | LWIR pose/occlusion/activity reference, not fall-positive source | Avinash Upadhyay et al.; official repository | paper/repository identify 2,400+ LWIR annotated 2D-pose images from seven actors |
| `TADAR` | Thermal Array-based Detection and Ranging dataset | TADAR | `LOW_VALUE` / `REFERENCE_ONLY` | thermal-array/ranging representation reference | HKU AIoT Lab; ACM paper | official repository/paper identify thermal-array multi-user ranging dataset |
| `LOCAL_FAMILY_A` | Local Family A | Family A | `REJECT` | provenance failure history only | `UNRESOLVED` | local RGB/colorized thermal rendering tree; no official public identity recovered |
| `LOCAL_SCREENSHOT_TREE` | Local human/not-human screenshot tree | screenshot tree; additional human/not-human tree | `REJECT` | provenance failure history only | `UNRESOLVED` | local RGB/RGBA screenshots/exports with polygon annotations; public identity unresolved |
| `TSETFALL` | TsetFall dataset | TsetFall | `REJECT` for thermal lane | visible-image fall-source exclusion witness | PPGIA/Universidade de Fortaleza authors | official repository identifies a four-camera JPEG/MP4 fall dataset, not a thermal dataset |
| `TST_FALL` | TST Fall Detection Dataset v2 | TST; TST Fall detection | `REJECT` for thermal lane | depth/skeleton/accelerometer exclusion witness | Enea Cippitelli et al.; IEEE DataPort | DOI identifies Kinect/depth, skeleton and wearable acceleration fall data, not thermal |
| `RGB_ONLY_FALL_SOURCE_GROUP` | D0 grouped RGB-only fall corpora | RGB-only fall corpora | `REJECT` | modality-exclusion history; no individual source approval | multiple / not a single source | D0 intentionally grouped non-thermal RGB-only fall sources; not collapsed into a fabricated dataset identity |
| `AMBIENT_IR_DEPTH_SOURCE_GROUP` | D0 grouped ambient-IR/depth-only sources | ambient-IR sources; depth-only sources | `REJECT` | modality-exclusion history; no individual source approval | multiple / not a single source | D0 intentionally grouped non-thermal-radiance ambient IR/depth sources |

### 6.2 Ledger B — URLs, access, and license boundaries

| source_id | Paper URL | Project URL | Repository URL | Archive / access URL | Access route | Dataset/asset license state | Paper license state | Code license state |
|---|---|---|---|---|---|---|---|---|
| `TF_66` | [DOI](https://doi.org/10.1016/j.engappai.2025.111819) | `UNRESOLVED` (paper references GitHub-TF-66 but current official URL not recovered) | `UNRESOLVED` | publisher article / corresponding-author route | paper says public non-commercial; data-availability wording says on request | `LICENSE_UNRESOLVED`; non-commercial use statement is not a complete asset license/redistribution grant | publisher shows Creative Commons/open access; exact variant `UNRESOLVED` | `UNRESOLVED` |
| `IPHPDT` | [Sensors DOI](https://doi.org/10.3390/s23010092) | paper page | `UNRESOLVED` | corresponding author on reasonable request | request-only for labeled derivative | `LICENSE_UNRESOLVED`; paper license does not cover derivative data | MDPI article `CC BY 4.0` | `UNRESOLVED` |
| `IPHD` | [challenge paper reference](https://chalearnlap.cvc.uab.cat/challenge/34/description/) | [ChaLearn dataset page](https://chalearnlap.cvc.uab.cat/dataset/34/description/) | `UNRESOLVED` | official ChaLearn file links | public challenge-era links; exact current terms require D1.3 | `LICENSE_UNRESOLVED`; challenge availability is not redistribution permission | challenge/paper reuse `UNRESOLVED` | download helper code license `UNRESOLVED` |
| `THERMAL_IM` | [CVPR paper](https://openaccess.thecvf.com/content/CVPR2023/html/Tang_What_Happened_3_Seconds_Ago_Inferring_the_Past_With_Thermal_CVPR_2023_paper.html) | [official repository](https://github.com/ZitianTang/Thermal-IM) | [GitHub](https://github.com/ZitianTang/Thermal-IM) | [repository-linked Google Drive folder](https://drive.google.com/drive/folders/1oH3uHXeQAIfeHAsz2CFRxPKUJmC-x9sx?usp=share_link) | public linked folder; raw not opened | repository explicitly states Thermal-IM Dataset `BSD-3-Clause`; archive-member scope still `PENDING_TV2-D1.4` | CVF open-access paper; reuse variant `UNRESOLVED` | repository `BSD-3-Clause` |
| `QUIDA` | [PeerJ DOI](https://doi.org/10.7717/peerj.19004) | [PMC article](https://pmc.ncbi.nlm.nih.gov/articles/PMC11970414/) | `UNRESOLVED` | [OSF DOI](https://doi.org/10.17605/OSF.IO/YJGDV) | public OSF project; landing license not verifiable in this run | `LICENSE_UNRESOLVED`; paper availability statement does not specify asset redistribution/derived-artifact terms | `CC BY-NC 4.0` as stated by PeerJ article | capture/tool code `UNRESOLVED` |
| `EHOME_SENIORS` | [Sensors/PMC](https://pmc.ncbi.nlm.nih.gov/articles/PMC6832422/) | [supplement](https://www.mdpi.com/1424-8220/19/20/4565/s1) | `UNRESOLVED` | [Figshare package](https://figshare.com/s/753cc0df15197b0b9572) | public supplement route; Figshare metadata returned 403 here | `LICENSE_UNRESOLVED`; release-level terms not verified | MDPI article `CC BY 4.0` | `UNRESOLVED` |
| `SDT` | [IEEE DOI](https://doi.org/10.1109/ICIP40778.2020.9191284) | [CVL page](https://cvl.tuwien.ac.at/research/cvl-databases/sdt-icip/) | `UNRESOLVED` | [Zenodo DOI](https://doi.org/10.5281/zenodo.4124309) | public non-commercial research download/citation; Zenodo page rate-limited here | official CVL terms: non-commercial research use + citation; redistribution/derived release `LICENSE_UNRESOLVED` | IEEE paper license `UNRESOLVED` | `UNRESOLVED` |
| `MUVIM` | [arXiv](https://arxiv.org/abs/2206.12740) | [official repository](https://github.com/MUVIM/FallDetection) | [GitHub](https://github.com/MUVIM/FallDetection) | email request described in repository | title/email/work address/affiliation + privacy waiver | `LICENSE_UNRESOLVED`; request/waiver only | arXiv paper distribution; reuse license `UNRESOLVED` | no explicit repository license verified |
| `TSF` | [arXiv](https://arxiv.org/abs/2004.08352) | [official repository](https://github.com/ivineetm007/Fall-detection) | [GitHub](https://github.com/ivineetm007/Fall-detection) | contact author per README | email affiliation and purpose | `LICENSE_UNRESOLVED` | arXiv paper distribution; reuse license `UNRESOLVED` | repository has a code LICENSE; exact SPDX/scope `PENDING_TV2-D1.7`, not dataset terms |
| `LWIRPOSE` | [arXiv](https://arxiv.org/abs/2404.10212) | [official repository](https://github.com/avinres/LWIRPOSE) | [GitHub](https://github.com/avinres/LWIRPOSE) | [official request form](https://forms.gle/1hU2yVtq49qrwvSa7) | user-submitted Google Form | `LICENSE_UNRESOLVED` | arXiv page exposes paper license link; exact reuse scope `UNRESOLVED` | no code license verified |
| `TADAR` | [ACM DOI](https://doi.org/10.1145/3641512.3686357) | [official repository](https://github.com/aiot-lab/TADAR) | [GitHub](https://github.com/aiot-lab/TADAR) | repository-linked external archive | public link; raw not opened | `LICENSE_UNRESOLVED`; MIT code license does not automatically cover data | ACM paper license `UNRESOLVED` | `MIT` |
| `LOCAL_FAMILY_A` | `UNRESOLVED` | `UNRESOLVED` | `UNRESOLVED` | local-only historical tree | no defensible access route | `LICENSE_UNRESOLVED` | `UNRESOLVED` | `UNRESOLVED` |
| `LOCAL_SCREENSHOT_TREE` | `UNRESOLVED` | `UNRESOLVED` | `UNRESOLVED` | local-only historical tree | no defensible access route | `LICENSE_UNRESOLVED` | `UNRESOLVED` | `UNRESOLVED` |
| `TSETFALL` | official repository publication links | [official repository](https://github.com/ppgia-unifor/TsetFall_dataset) | [GitHub](https://github.com/ppgia-unifor/TsetFall_dataset) | repository download + decoder-key form | form/key request; no action taken | `LICENSE_UNRESOLVED`; irrelevant to thermal lane | publication license `UNRESOLVED` | repository license `UNRESOLVED` |
| `TST_FALL` | [IEEE DataPort DOI](https://doi.org/10.21227/H2QP48) | IEEE DataPort record | `UNRESOLVED` | IEEE DataPort | record/access terms; no download | asset terms `UNRESOLVED`; irrelevant to thermal lane | related paper license `UNRESOLVED` | `UNRESOLVED` |
| `RGB_ONLY_FALL_SOURCE_GROUP` | `UNRESOLVED` (group, not one work) | `UNRESOLVED` | `UNRESOLVED` | `UNRESOLVED` | no access planned for thermal lane | `LICENSE_UNRESOLVED`; `REJECT` by modality independently of license | `UNRESOLVED` | `UNRESOLVED` |
| `AMBIENT_IR_DEPTH_SOURCE_GROUP` | `UNRESOLVED` (group, not one work) | `UNRESOLVED` | `UNRESOLVED` | `UNRESOLVED` | no access planned for thermal lane | `LICENSE_UNRESOLVED`; `REJECT` by modality independently of license | `UNRESOLVED` | `UNRESOLVED` |

### 6.3 Ledger C — provenance, payload, sensor, and grouping

| source_id | Provenance state | Payload representation | Sensor / resolution / temporal form | Expected grouping key | Subject/session/recording evidence |
|---|---|---|---|---|---|
| `TF_66` | official paper metadata verified; release/version/checksum pending | rendered thermal video provisionally; radiometric/codec/bit depth unresolved | Calumino CTS-EVK native 35×15, paper describes 4 FPS and converted/upsampled thermal video | participant, then session/video, then environment | 66 participants, 9 environments; folder naming reportedly carries participant ID; published Train/Test subject isolation not proven |
| `IPHPDT` | paper-defined derivative; asset/version provenance pending request | processed/inpainted posture images with boxes; serialization/masks unresolved | underlying FLIR Lepton v3 thermal; paper-level image dataset, not verified temporal stream | subject, then original video ID if derivative preserves it | final image train/test counts reported; subject/session isolation not established |
| `IPHD` | official ChaLearn dataset metadata verified | registered thermal-to-depth images and original 160×120 thermal images; temperature encoding requires D1.3 confirmation | FLIR Lepton v3, original thermal 160×120; source videos had ordering removed but video ID retained | authoritative video ID; subject if official metadata supplies it | >100k aligned frames; train/validation/test and video IDs documented; subject-role isolation unresolved |
| `THERMAL_IM` | official repo structure verified; actual release/member checksums pending | `RGBT_T.mp4`, rendered/non-radiometric thermal intensity pending payload confirmation | thermal video 288×384 at 15 FPS; synchronized RGB/depth side streams | actor, then room/scene, then clip | `meta.csv` includes actor/room/scene and paper split; two actor/room generalization structure described; exact membership pending |
| `QUIDA` | paper + OSF DOI verified; OSF asset metadata/license not directly verified | FIR CSV: Unix timestamp + 768 Celsius values; serialization/missing values pending | MLX90640 32×24, approximately 384 ms / ~2.6 Hz temporal series | subject, then recording/fall event | 10 subject directories; four sensor CSVs and root `Falls.csv`; no official ML split |
| `EHOME_SENIORS` | paper/supplement route verified; Figshare package metadata inaccessible in run | CSV and MAT; MLX temperature + raw fields, Omron temperatures | MLX90640 32×24 ~16 FPS; four Omron 1×8 sensors ~5 FPS | volunteer, then sensor/fall type/file, then repetition/event | six volunteers, two groups, 15 fall types, five repetitions; filename encodes subject/sensor/fall type; no official subject-disjoint split |
| `SDT` | official CVL identity and local T-A0 checksum lineage verified | 16-bit encoded thermal images + depth/labels; canonical local representation documented elsewhere | FLIR Lepton 3.5 thermal, distributed 480×640 single frames; synthetic + real | official source partition only; subject/session absent | train/validation/real-test membership exists; no trusted subject/session/sequence identity |
| `MUVIM` | paper/repository verified; retained trial inventory and release version pending request | encoded thermal video plus IR/depth/RGB/wearable modalities | three FLIR ONE Gen 3 thermal cameras; paper reports 8.7 FPS and rendered video; corruption/loss noted | subject, then ADL/fall trial/recording | 30 healthy adults fall/ADL plus 10 older adults ADL in paper; exact retained thermal trials/split unresolved |
| `TSF` | repository metadata verified; payload/release provenance pending contact | thermal video | 640×480; FPS/codec/orientation unresolved; temporal | actor, then video | D0/literature says narrow single-actor/single-room design; official README does not establish subject/session split |
| `LWIRPOSE` | paper/repository identity verified; requested release uninspected | LWIR still images with 2D pose annotations | 640×480 LWIR images per D0; image-level | subject (seven actors), then capture/activity grouping | seven actors and 12 activities reported by D0/paper; official subject split details pending request |
| `TADAR` | repository/paper identity verified; archive metadata uninspected | thermal array sensor data + generated ranging outputs | thermal array temporal samples; exact array schema/orientation not verified here | subject/session/recording if present; otherwise `UNRESOLVED` | multi-user case-study identity exists; posture/fall grouping and split not verified |
| `LOCAL_FAMILY_A` | provenance unresolved; historical local counts only | RGB colorized thermal-like PNG plus placeholders | readable subset mainly RGB 230×226 still images; underlying sensor/unit unknown | none defensible | labels, subject, session, recording all unresolved |
| `LOCAL_SCREENSHOT_TREE` | provenance unresolved; historical local tree only | RGB/RGBA screenshots/exports + JSON polygons | still screenshots; underlying sensor/unit unknown | none defensible | presence polygons exist; subject/session/recording identity unresolved |
| `TSETFALL` | official repo structure verified | JPEG frames, MP4 video, CSV boxes/classes | four visible-light cameras; thermal sensor not claimed | sequence/camera, then actor if metadata exists | 36 described sequences; subject/session evidence not needed because modality `REJECT` |
| `TST_FALL` | official DOI identity verified | Kinect depth, skeleton joints, timestamps, two accelerometer streams | depth/wearable temporal data; no thermal | subject, then activity repetition | 11 volunteers, activities repeated three times; modality `REJECT` |
| `RGB_ONLY_FALL_SOURCE_GROUP` | D0 group-level provenance only | RGB image/video family | visible-light only by D0 definition | source-specific only; no shared invented key | not evaluated; group is rejected before thermal compatibility |
| `AMBIENT_IR_DEPTH_SOURCE_GROUP` | D0 group-level provenance only | ambient IR presence/depth images or streams | no calibrated/image-form thermal evidence by D0 definition | source-specific only; no shared invented key | not evaluated; group is rejected before thermal compatibility |

### 6.4 Ledger D — labels and semantic boundary

| source_id | Label semantics | Fall / non-fall / posture semantics | Known limitations |
|---|---|---|---|
| `TF_66` | fall videos, non-fall/ADL videos, fall start/end context | 12 staged fall templates plus preceding/succeeding frames; not natural/clinical fall | access wording conflict, asset license, participant-isolated split, radiometric status, payload encoding unresolved |
| `IPHPDT` | standing, sitting, lying, bending with boxes | static posture only; bending is normal hard-negative candidate; lying is not temporal fall | derivative access/terms, original identity propagation, subject isolation, processed-image masks/encoding unresolved |
| `IPHD` | human detection boxes, public/private/wild/scripted activities | sitting/lying/ADL context exists but IPHPDT four-class labels are not automatically part of IPHD | challenge terms, temperature encoding, subject identity and derivative linkage unresolved |
| `THERMAL_IM` | action intervals with action/object fields; exact vocabulary pending payload | normal indoor interaction/motion only; no verified fall/lying positive label | rendered thermal, small actor set/generalization design, annotation vocabulary and archive license scope pending |
| `QUIDA` | walking/no-fall and manually timed simulated fall events | ten staged fall types; temporal proxy candidate, not clinical/natural fall | young 10-subject lab sample, weak ADL diversity, no official split, asset license/missing-sample policy unresolved |
| `EHOME_SENIORS` | 15 staged fall types; pre-fall ordinary context not independently rich-labeled | staged falls by six volunteers; pre-fall standing/walking/sitting/lying context; not clinical fall | small single-person lab design, no official split, normal posture labels weak, supplement terms inaccessible here |
| `SDT` | LYING/SITTING/STANDING/EMPTY_ROOM | static lying maps only to `HUMAN_FALL_PROXY`; sitting/standing normal; no temporal fall event | no subject/session/sequence, current baseline family not an additional source, non-commercial restriction |
| `MUVIM` | fall and ADL trials across modalities | staged temporal falls and ADLs; retained thermal label inventory pending | request/waiver, no public asset license, corrupted/lost trials, exact thermal split/grouping unresolved |
| `TSF` | normal ADL and thermal fall/other-normal videos | staged temporal fall reference | very small/narrow, contact-gated, no dataset license, actor/session grouping weak |
| `LWIRPOSE` | 2D pose annotations and activities such as sitting/eating/walking | no verified fall/lying labels; pose/occlusion reference only | request form, dataset license absent, no fall-positive role |
| `TADAR` | detection/ranging outputs | no verified posture/fall label contract | source purpose differs, dataset license and grouping unresolved, code license not data license |
| `LOCAL_FAMILY_A` | unknown | cannot establish fall/non-fall/posture semantics | identity, license, sensor, provenance, labels all unresolved; `REJECT` |
| `LOCAL_SCREENSHOT_TREE` | human/not-human presence polygons only | no defensible fall/posture semantics | identity, license, sensor provenance and grouping unresolved; `REJECT` |
| `TSETFALL` | NF/FN/FG/confounding boxes and varied activities | useful fall semantics but RGB/visible-image source | non-thermal modality; cannot substitute for thermal evidence |
| `TST_FALL` | ADL and fall actions with skeleton/depth/acceleration | temporal fall/ADL but no thermal representation | non-thermal modality; cannot substitute for thermal evidence |
| `RGB_ONLY_FALL_SOURCE_GROUP` | source-specific fall/ADL labels not inventoried | visible-light semantics cannot establish thermal compatibility | deliberately grouped reject; no shared identity/license/grouping inference |
| `AMBIENT_IR_DEPTH_SOURCE_GROUP` | source-specific labels not inventoried | ambient presence/depth semantics cannot establish thermal radiance/temperature | deliberately grouped reject; no modality equivalence |

### 6.5 Ledger E — evidence status and routed next step

| source_id | Evidence URLs | Evidence access date | Field status | Next detailed verification step |
|---|---|---|---|---|
| `TF_66` | [publisher DOI](https://doi.org/10.1016/j.engappai.2025.111819) | `2026-08-30` | `PENDING_TV2-D1.2`; access/license/payload/grouping unresolved | `TV2-D1.2` |
| `IPHPDT` | [paper DOI](https://doi.org/10.3390/s23010092) | `2026-08-30` | `PENDING_TV2-D1.3`; `LICENSE_UNRESOLVED` | `TV2-D1.3` |
| `IPHD` | [ChaLearn page](https://chalearnlap.cvc.uab.cat/dataset/34/description/) | `2026-08-30` | `PENDING_TV2-D1.3`; underlying/derivative boundary explicit | `TV2-D1.3` |
| `THERMAL_IM` | [repository](https://github.com/ZitianTang/Thermal-IM); [paper](https://openaccess.thecvf.com/content/CVPR2023/html/Tang_What_Happened_3_Seconds_Ago_Inferring_the_Past_With_Thermal_CVPR_2023_paper.html) | `2026-08-30` | `PENDING_TV2-D1.4`; official metadata verified, member scope pending | `TV2-D1.4` |
| `QUIDA` | [paper](https://pmc.ncbi.nlm.nih.gov/articles/PMC11970414/); [OSF DOI](https://doi.org/10.17605/OSF.IO/YJGDV) | `2026-08-30` | `PENDING_TV2-D1.5`; OSF license `ACCESS_NOT_VERIFIABLE` | `TV2-D1.5` |
| `EHOME_SENIORS` | [paper](https://pmc.ncbi.nlm.nih.gov/articles/PMC6832422/); [supplement](https://www.mdpi.com/1424-8220/19/20/4565/s1); [Figshare](https://figshare.com/s/753cc0df15197b0b9572) | `2026-08-30` | `PENDING_TV2-D1.6`; Figshare metadata `ACCESS_NOT_VERIFIABLE` | `TV2-D1.6` |
| `SDT` | [CVL](https://cvl.tuwien.ac.at/research/cvl-databases/sdt-icip/); [Zenodo](https://doi.org/10.5281/zenodo.4124309) | `2026-08-30` | `REFERENCE_ONLY`; known non-commercial terms, derived release unresolved | `TV2-D1.7` normalization |
| `MUVIM` | [repository](https://github.com/MUVIM/FallDetection); [paper](https://arxiv.org/abs/2206.12740) | `2026-08-30` | `UNRESOLVED`; request/waiver and `LICENSE_UNRESOLVED` | `TV2-D1.7` normalization; separate access decision only if later authorized |
| `TSF` | [repository](https://github.com/ivineetm007/Fall-detection); [paper](https://arxiv.org/abs/2004.08352) | `2026-08-30` | `REFERENCE_ONLY`; `LICENSE_UNRESOLVED` | `TV2-D1.7` normalization |
| `LWIRPOSE` | [repository](https://github.com/avinres/LWIRPOSE); [paper](https://arxiv.org/abs/2404.10212) | `2026-08-30` | `REFERENCE_ONLY`; request-only and `LICENSE_UNRESOLVED` | `TV2-D1.7` normalization |
| `TADAR` | [repository](https://github.com/aiot-lab/TADAR); [paper DOI](https://doi.org/10.1145/3641512.3686357) | `2026-08-30` | `REFERENCE_ONLY`; dataset license/labels unresolved | `TV2-D1.7` normalization |
| `LOCAL_FAMILY_A` | repository [T-A0 report](20260810_Codex_T-A0_Thermal_Dataset_Selection_Source_Identity_01.md) | `2026-08-30` | `REJECT`; `LICENSE_UNRESOLVED` / provenance unresolved | `TV2-D1.7` preserve rejection |
| `LOCAL_SCREENSHOT_TREE` | repository [T-A0 report](20260810_Codex_T-A0_Thermal_Dataset_Selection_Source_Identity_01.md) | `2026-08-30` | `REJECT`; `LICENSE_UNRESOLVED` / provenance unresolved | `TV2-D1.7` preserve rejection |
| `TSETFALL` | [repository](https://github.com/ppgia-unifor/TsetFall_dataset) | `2026-08-30` | `REJECT` for thermal lane | `TV2-D1.7` preserve modality rejection |
| `TST_FALL` | [IEEE DataPort DOI](https://doi.org/10.21227/H2QP48) | `2026-08-30` | `REJECT` for thermal lane | `TV2-D1.7` preserve modality rejection |
| `RGB_ONLY_FALL_SOURCE_GROUP` | D0 report section 6 | `2026-08-30` | `REJECT`; grouped source class, not one dataset | `TV2-D1.7` preserve grouped rejection |
| `AMBIENT_IR_DEPTH_SOURCE_GROUP` | D0 report section 6 | `2026-08-30` | `REJECT`; grouped source class, not one dataset | `TV2-D1.7` preserve grouped rejection |

## 7. D0-to-D1 Crosswalk

| D0 occurrence | Ledger source_id | Preservation result |
|---|---|---|
| Existing lead: SDT | `SDT` | preserved `REFERENCE_ONLY` |
| Existing lead / serious candidate: eHomeSeniors | `EHOME_SENIORS` | preserved, routed to D1.6 |
| Existing lead: MUVIM | `MUVIM` | preserved `UNRESOLVED` |
| Existing lead / top candidate: Thermal Fall 66 | `TF_66` | preserved, routed to D1.2 |
| Existing lead: TSF | `TSF` | preserved `REFERENCE_ONLY/LOW_VALUE` |
| Existing lead: Local Family A / screenshot tree | `LOCAL_FAMILY_A`, `LOCAL_SCREENSHOT_TREE` | historical combined D0 row expanded using T-A0's two independent local identities; both remain `REJECT` |
| New/top candidate: Thermal-IM | `THERMAL_IM` | preserved, routed to D1.4 |
| New/top candidate: IPHPDT / IPHD | `IPHPDT`, `IPHD` | permission boundary split, both routed to D1.3 |
| New/top candidate: QUIDA | `QUIDA` | preserved, routed to D1.5 |
| Rejected/reference: LWIRPOSE | `LWIRPOSE` | preserved `REFERENCE_ONLY` |
| Rejected/reference: TADAR | `TADAR` | preserved `LOW_VALUE/REFERENCE_ONLY` |
| Rejected grouped row: TsetFall | `TSETFALL` | independently preserved `REJECT` |
| Rejected grouped row: TST | `TST_FALL` | independently preserved `REJECT` |
| Rejected grouped row: RGB-only fall corpora | `RGB_ONLY_FALL_SOURCE_GROUP` | group history preserved without invented dataset identity |
| Rejected grouped row: ambient-IR/depth-only sources | `AMBIENT_IR_DEPTH_SOURCE_GROUP` | group history preserved without modality equivalence |

Crosswalk result: D0의 모든 독립 이름과 명시적으로 묶은 source군이 17개의
stable record에 보존되었다. serious candidate 5개는 ledger 상 6개 record다.
이는 IPHPDT derivative와 IPHD underlying source의 permission boundary를
의도적으로 분리했기 때문이다.

## 8. Source Order for D1.2–D1.6

| Order | Step | Source record(s) | Frozen question boundary |
|---:|---|---|---|
| 1 | `TV2-D1.2` | `TF_66` | official project/access route, public-vs-request wording, asset license, participant/video grouping, payload form |
| 2 | `TV2-D1.3` | `IPHPDT`, `IPHD` | derivative/underlying ownership, request and challenge terms, Kelvin×100/processed encoding, group identity |
| 3 | `TV2-D1.4` | `THERMAL_IM` | BSD-3 asset/member scope, annotations, rendered thermal representation, actor/room/scene split |
| 4 | `TV2-D1.5` | `QUIDA` | OSF asset license, CSV schema/missing values, timestamps, subject/event provenance |
| 5 | `TV2-D1.6` | `EHOME_SENIORS` | Figshare package metadata/terms, sensor fields/serialization, subject/fall-event grouping |

SDT와 D0 reference/rejected/unresolved records는 삭제하지 않고 D1.7
정규화 입력으로 유지한다. 이 보고서는 D1.2–D1.6의 실제 action을 수행하지
않았다.

## 9. Findings

1. D0 inventory는 17개 stable record로 완전 보존할 수 있다.
2. serious 후보 5개는 complementary하다. TF-66은 broad temporal lane,
   IPHPDT/IPHD는 static posture boundary, Thermal-IM은 normal motion,
   QUIDA/eHomeSeniors는 low-resolution temperature-array temporal reference다.
3. IPHPDT와 IPHD는 연결되어 있지만 동일 asset가 아니다. open-access paper,
   author-request derivative, challenge-era underlying download를 하나의 license로
   합칠 수 없다.
4. Thermal-IM은 official repository가 dataset BSD-3-Clause를 명시하는 가장
   명확한 public-license lead다. 그래도 linked Drive의 모든 archive member와
   annotations가 같은 scope인지 D1.4에서 확인해야 한다.
5. TF-66의 paper는 public/non-commercial access와 on-request wording을 함께
   제공하고 official project repository URL을 현재 metadata review에서
   복구하지 못했다. D1.2의 우선 blocker다.
6. QUIDA paper와 eHomeSeniors paper의 공개 라이선스는 dataset asset license로
   자동 확대되지 않는다. OSF/Figshare landing terms를 각각 D1.5/D1.6에서
   확인해야 한다.
7. SDT는 현재 baseline/source family이므로 additional candidate로 재승인하지
   않고 `REFERENCE_ONLY`로 유지한다.
8. TsetFall/TST와 grouped RGB/ambient-IR/depth sources는 fall semantics가 있어도
   thermal radiance/temperature evidence가 아니므로 rejection을 보존한다.

## 10. Unresolved Items

- `TF_66`: official GitHub/project URL, current access endpoint, asset license,
  redistribution/derived-artifact rule, codec/bit depth/radiometric status,
  subject-isolated split.
- `IPHPDT` / `IPHD`: labeled derivative delivery terms, IPHD challenge terms,
  derivative-to-underlying member mapping, temperature/processed serialization,
  subject/session isolation.
- `THERMAL_IM`: linked archive member list/checksums, BSD-3 scope across every asset,
  exact `annotation.json` vocabulary, actor/room/scene membership.
- `QUIDA`: OSF project asset license, file listing/version, CSV missing-sample behavior,
  authoritative event/recording IDs beyond subject and `Falls.csv`.
- `EHOME_SENIORS`: Figshare package license/version/file list, CSV/MAT serialization,
  event boundaries and official split absence.
- reference/request-only sources: MUVIM/TSF/LWIRPOSE asset licenses and release
  inventories remain unresolved; this does not block the D1.1 inventory freeze.
- local sources and D0 grouped rejection classes have no recoverable official identity;
  their `REJECT` history is the correct non-guessing state.

## 11. User Action Queue

현재 TV2-D1.1을 완료하기 위해 사용자가 해야 할 일은 없다. 아래 항목은
해당 후속 step이 별도로 승인된 뒤에만 활성화되는 deferred queue다.

| Deferred item | 필요한 이유 | Official URL | 사용자가 입력/확인할 항목 | Codex에 전달할 결과 | 이 단계 완료 가능? | 후속 step |
|---|---|---|---|---|---|---|
| TF-66 official access route 확인 또는 owner request | public-vs-request와 dataset terms 해소 | [publisher DOI](https://doi.org/10.1016/j.engappai.2025.111819) | paper가 가리키는 current project URL; 요청이 필요하면 연구 목적/소속/비상업 사용 조건 | exact project/access URL, owner reply, terms text; raw data 자체는 전달하지 않음 | 예, D1.1은 완료 가능 | `TV2-D1.2` |
| IPHPDT labeled derivative request | posture labels와 derivative license/identity 확인 | [paper DOI](https://doi.org/10.3390/s23010092) | corresponding-author contact, 소속, 합리적 연구 요청, 허용된 use/redistribution/derived-artifact 조건 | 승인/거절과 license/terms 전문, release/version 정보 | 예 | `TV2-D1.3` |
| MUVIM access/waiver decision | request-only reference의 retained thermal inventory 확인 | [official repository](https://github.com/MUVIM/FallDetection) | title, email, work address, affiliation, privacy waiver; 사용자가 직접 수락해야 함 | owner reply, waiver/terms, release inventory; raw payload 불필요 | 예 | D1.7 이후 별도 승인 시 |
| TSF access email decision | contact-gated reference의 dataset terms 확인 | [official repository](https://github.com/ivineetm007/Fall-detection) | affiliation과 research purpose | owner reply와 dataset license/terms | 예 | D1.7 이후 별도 승인 시 |
| LWIRPOSE request form decision | dataset license와 subject/activity grouping 확인 | [official form](https://forms.gle/1hU2yVtq49qrwvSa7) | form이 요구하는 소속/목적/개인정보와 terms 직접 확인 | form 완료 결과, access terms, release/version metadata | 예 | D1.7 이후 별도 승인 시 |

본 실행에서는 어떤 request, email, form, waiver도 제출하지 않았다.

## 12. Artifacts Created / Modified

- Created: `docs/reports/20260830_Codex_Thermal_V2_TV2-D1.1_Execution_Report_KO_01.md`
- Modified: `docs/thermal/20260830_SafeNest_Thermal_V2_Stepwise_Execution_Roadmap_KO_01.md`
- Not created: 별도 ledger file. 기존 convention이 명확하지 않아 이 보고서
  section 6을 canonical ledger로 사용한다.
- Not modified: dataset, manifest, model, runtime, source code, Team/Integration
  repository.

## 13. Validation

검증 대상:

- required header 11개와 required body section 17개 존재
- serious candidates: `TF_66`, `IPHPDT`/`IPHD`, `THERMAL_IM`, `QUIDA`,
  `EHOME_SENIORS` 존재
- D0 reference/rejected/unresolved crosswalk와 17개 stable source record 존재
- ledger A–E가 같은 source ID 집합을 사용하고 identity table의 ID가 unique
- required field는 official evidence 또는 explicit status를 가짐; 빈칸 없음
- 다음 source-specific step은 D1.2–D1.6 순서로 하나씩 연결
- roadmap의 단일 `NEXT_STEP`은 `TV2-D1.2`
- `TRAINING_AUTHORIZED: NO`, locked-test access `0`
- raw/binary/dataset/model/runtime artifact 추가 없음
- 변경 파일은 report와 roadmap 두 개로 제한
- `git diff --check`와 Markdown table delimiter/column-count focused check 수행

검증 결과는 `PASS_WITH_LIMITATIONS`다. limitations는 license/access/payload
metadata의 후속 검증 필요성이지 D0 source 누락이 아니다.

## 14. Decision

`PASS_WITH_LIMITATIONS`

통과 근거:

- D0 serious 5개 후보와 reference/rejected/unresolved source를 모두 보존했다.
- 17개 record 모두 stable `source_id`와 explicit field status를 갖는다.
- IPHPDT/IPHD permission boundary를 분리했다.
- source별 다음 detailed verification step을 하나로 연결했다.
- raw payload, training, model/data/runtime mutation, locked-test 접근이 없다.

제한:

- dataset/asset license가 확정된 source는 Thermal-IM official repository
  statement가 가장 명확하며, 나머지 serious source는 전부 일부 license/access
  field가 unresolved다.
- official archive landing의 일부는 이 실행 환경에서 403/429 또는 metadata
  미노출이었고 추측하지 않았다.

## 15. Gate Impact

- `TV2-D1.1`: `DONE_WITH_LIMITATIONS / PASS_WITH_LIMITATIONS`
- `TV2-D1.2`: `NEXT`
- Parent `TV2-D1`: 계속 진행 중; D1 gate PASS가 아님
- `G1`: 계속 `PLANNED / BLOCKED_BY_D1_D2_D3`
- Training authorization: `NO`
- Locked-test access count: `0`

## 16. Next Authorized Step

`TV2-D1.2`

## 17. Git Evidence

Execution start:

~~~text
branch: thermal-v2/stepwise-execution
HEAD: dd945c07e61e7235a80e86d681fb8f7038496b56
origin/thermal-v2/stepwise-execution: dd945c07e61e7235a80e86d681fb8f7038496b56
starting worktree: clean
pull: Already up to date (fast-forward only)
~~~

Pre-commit change set is intentionally limited to the report and roadmap listed
in section 12. Delivery commit and pushed remote equality are verified after the
report content is frozen; no future commit hash is guessed in this document.

~~~text
git status --short
 M docs/thermal/20260830_SafeNest_Thermal_V2_Stepwise_Execution_Roadmap_KO_01.md
?? docs/reports/20260830_Codex_Thermal_V2_TV2-D1.1_Execution_Report_KO_01.md

git diff --stat
..._Thermal_V2_Stepwise_Execution_Roadmap_KO_01.md | 35 ++++++++++++++++++----
1 file changed, 29 insertions(+), 6 deletions(-)

git log -1 --oneline
dd945c0 docs(thermal-v2): add stepwise execution roadmap
~~~

`git diff --stat` does not include the untracked new report before staging; the
explicit status above records it. The staged diff is checked separately before
commit so both intended Markdown files are included and nothing else is staged.
