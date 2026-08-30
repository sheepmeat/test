# SafeNest Thermal V2 — TV2-D1 Source Access, License, Payload, and Grouping Verification

- Worker: Luna 4
- Date: 2026-08-30
- Repository: `sheepmeat/test`
- Phase: `TV2-D1`
- Branch: `thermal-v2/tv2-d1-source-verification-rerun`
- Startup base: `origin/main` at `25863118c06b8c065f4aa2e8d3c85cc9b4799a6a`
- Training authorization: `NONE`
- Dataset merge authorization: `NONE`
- `LOCKED_PUBLIC_TEST_ACCESS`: `0`
- D1 recommendation: `PASS_WITH_LIMITATIONS`

This report resumes TV2-D1 after the TV2-D0 merge. The active [Thermal V2 master map](20260830_SafeNest_Thermal_V2_Master_Execution_Map_01.md) and [TV2-D0 report](20260830_SafeNest_Thermal_V2_TV2-D0_Additional_Dataset_Discovery_01.md) both resolve on the refreshed `origin/main`. The fresh D1 branch was created directly from that ref; `HEAD == origin/main`, `git log origin/main..HEAD` is empty, and the branch had no initial diff.

## 1. Executive Conclusion

TV2-D1 is **`PASS_WITH_LIMITATIONS`**. Three serious sources have enough verified evidence to continue to controlled D2 compatibility work:

- **QUIDA**: the official OSF archive is public and contains timestamped comma-separated numeric thermal rows with exactly 768 values per frame, corresponding to a 32×24 MLX90640, plus subject directories and a `Falls.csv` timing file.
- **eHomeSeniors**: the official MDPI supplementary archive is public and contains both MLX90640 and Omron CSV payloads, subject/group/fall-type file names, timestamped frames, calibrated temperature fields, and additional raw MLX90640 fields.
- **Thermal-IM**: the official public Drive release is accessible and sampled archives contain thermal MP4s, action intervals, pose/extrinsic metadata, and the release’s documented actor/room/scene/split metadata contract. The thermal stream is rendered visual intensity, not a verified physical-temperature matrix.

The strongest verified candidates for the next controlled phase are therefore **QUIDA for native 32×24 Celsius-compatible event data**, **eHomeSeniors for low-resolution calibrated-temperature and raw-sensor handling**, and **Thermal-IM for public normal human-object interaction and motion hard negatives**. This is a D1 compatibility finding, not a claim that any source will reduce false falls or is the best dataset.

Two high-value sources remain access-limited. TF-66’s public repositories expose metadata, helpers, and a license notice, but the actual video payload requires an author email request. IPHPDT posture labels are available from the corresponding author upon reasonable request; the public IPHD base release is separate and provides human boxes, not the posture derivative. Neither source is admitted to D2 until the missing payload/terms/split evidence is resolved.

The current G1 preprocessing hypothesis, `P1_TRAIN_FITTED_GLOBAL_ZSCORE`, remains provisional and is **not frozen**. D1 distinguishes calibrated temperature from rendered intensity but does not select preprocessing, convert intensity to Celsius, train a model, or create a merged dataset.

## 2. Verification Method

The audit followed the required priority order: TF-66, IPHPDT/IPHD, Thermal-IM, QUIDA, and eHomeSeniors. Evidence was taken from official publisher pages, official dataset repositories, official supplemental material, official OSF/Drive metadata, HTTP headers, archive listings, and small representative members. Temporary downloads were kept outside Git-tracked dataset roots and no payload was copied into the repository.

The access classifications used here are exactly:

- `ACCESS_VERIFIED_PUBLIC`
- `ACCESS_VERIFIED_RESTRICTED`
- `ACCESS_REQUIRES_MANUAL_REQUEST`
- `ACCESS_BROKEN`
- `ACCESS_NOT_VERIFIABLE`

The asset-term classifications distinguish dataset rights from paper publication rights:

- `DATASET_LICENSE_VERIFIED`
- `DATASET_TERMS_LIMITED`
- `DATASET_TERMS_AMBIGUOUS`
- `DATASET_LICENSE_NOT_VERIFIABLE`

Payload inspection recorded the official origin, filename, byte size, SHA-256 where a representative file was downloaded, container/format, dtype or bit depth where observable, shape/resolution, sample count, timestamp/label fields, and grouping fields. A full IPHD thermal archive was not downloaded because the official training ZIP is approximately 1.70 GB and the official schema plus HTTP headers are sufficient for this D1 access decision. TF-66 video payload was not downloaded because the official release instructs researchers to request access by email.

No model training, architecture work, prediction, ranking, preprocessing freeze, dataset merge, SafeNest capture use, Team-repository change, Raspberry Pi work, or locked-test access occurred.

## 3. TF-66

### Identity and access

The source is [Thermal Fall 66](https://doi.org/10.1016/j.engappai.2025.111819), with a public [dataset/helper repository](https://github.com/Christopher-Silver/TF-66) and a public [benchmark repository](https://github.com/Christopher-Silver/thermal-fall-benchmark). The public helper repository exposes `Final Dataset.xlsx`, `DataGenerator.py`, `License.txt`, and README instructions. Its README states that access to the dataset requires emailing the primary author, Chris Silver, at `crsilver@lakeheadu.ca`, and that the dataset is for non-commercial use.

`TF66_D1_STATUS = ACCESS_REQUIRES_MANUAL_REQUEST`.

The exact request procedure is: email the named primary author. No request form or additional required fields are specified in the inspected README. The stated use condition is non-commercial. No request was sent on the user’s behalf.

### License boundary

The public data repository’s [License.txt](https://github.com/Christopher-Silver/TF-66/blob/main/License.txt) explicitly names **Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0)** and states that commercial use is not allowed. The benchmark repository also identifies the TF-66 dataset as CC BY-NC 4.0. The publisher article is open access under a Creative Commons license, but that paper license is not used as a substitute for the dataset terms.

`DATASET_TERMS_LIMITED` — the dataset license is explicit, but access is request-gated and the actual release/consent/redistribution scope was not independently confirmed. Attribution and citation are required. The evidence is not a legal conclusion about whether a particular derived artifact may be redistributed or used commercially.

### Payload, labels, and grouping

The inspected [Final Dataset.xlsx](https://github.com/Christopher-Silver/TF-66/blob/main/Final%20Dataset.xlsx) is metadata, not the thermal video payload:

- file size: 97,270 bytes
- SHA-256: `08e43cc1b0d00307d649c2a1f66f9cba951353807b16d854b0fce60296fb36ba`
- format: XLSX workbook
- rows: 812 recordings
- recording type: 562 `Fall`, 250 `Non Fall`
- volunteers: 66 explicit IDs
- rooms: 9 explicit IDs; room heights represented as 8, 9, and 10 feet
- fields: sample ID, volunteer ID, recording name, video length, recording type, free-text action, start/first-fall/last-frame fields, frames before/after fall, room ID, and room height
- duplicate recording names: none in the inspected workbook

The accompanying [DataGenerator.py](https://github.com/Christopher-Silver/TF-66/blob/main/DataGenerator.py) is helper code; its SHA-256 was `c696cc2037b14c44787c3f1f1251007ecc3acfa44c7a03cc6a9d6ddbe76e2582`. It expects cached `.avi`-derived frames and uses the workbook’s fall-frame fields. The paper/preprint describes Calumino CTS-EVK capture at native 35×15 and 4 FPS, with a 140×60 stored/upscaled representation in the described workflow, but the actual released video was not obtained. Therefore:

- representation: `UNKNOWN`
- physical compatibility: `UNKNOWN`
- file-level status: metadata inspected; actual `.avi`/codec/bit depth/channels/radiometric encoding not verified
- timestamp evidence: frame indices and video lengths are present; no wall-clock timestamp field was verified
- label evidence: free-text action plus fall start/end frame fields; staged temporal fall evidence is present
- grouping: `GROUPING_PARTIAL`
- subject-disjoint split later: `POSSIBLY`

Volunteer ID, room ID, and recording name provide useful grouping keys. Session IDs and a complete accessible Train/Test membership inventory were not verified. The workbook’s 80:20-style split description does not prove subject isolation.

### Semantic inventory and D1 decision

Verified original action text includes walking, sitting, standing, laying, crawling, empty-room/non-fall activity, falls from chairs/beds/standing/walking, collapse, trip, faint-like collapse, and post-fall rolling or squirming in some recordings. The source supports these SafeNest inventory classes where the text is explicit: `NO_HUMAN` for explicit empty-room recordings, `NORMAL_UPRIGHT`, `NORMAL_SEATED`, `WALKING`, `STATIC_LYING`, `CRAWLING`, `TEMPORAL_FALL`, `POST_FALL`, and `OTHER`. The free text is heterogeneous and must remain provenance, not be flattened into a clinical label.

The fall recordings are staged/simulated events, not clinical or natural falls. Static laying/lying text is not itself a fall event. The 250 non-fall recordings are useful potential hard negatives, but the actual thermal payload and complete split cannot be checked until access is granted.

**D1 source decision: `HOLD_PENDING_ACCESS`.** TF-66 is a high-value candidate, but no D2 payload admission is made without the requested video release, asset terms, payload encoding, and participant-disjoint split audit.

## 4. IPHPDT / IPHD

### Separate the base release from the posture derivative

The sources are the [IPHPDT paper](https://doi.org/10.3390/s23010092) and the underlying official [ChaLearn IPHD page](https://chalearnlap.cvc.uab.cat/dataset/34/description/). They must not be treated as one interchangeable release.

| Layer | Access evidence | Classification | What is available |
|---|---|---|---|
| IPHD base thermal release | Official `thermal0-train.zip` returned HTTP 200, `application/zip`, `content-length: 1696560416`, and ETag `"5eefd6f6-651f7520"`; the page also exposes validation/test links. | `ACCESS_VERIFIED_PUBLIC` | Base thermal/depth-aligned or original thermal images and human-box files according to the selected release. The full training ZIP was not downloaded. |
| IPHPDT posture derivative | The paper’s Data Availability Statement says the data are available from the corresponding author upon reasonable request. | `ACCESS_REQUIRES_MANUAL_REQUEST` | Four posture labels and boxes are paper-described, but the labeled derivative was not obtained. |

### License boundary

The IPHPDT paper is an open-access Sensors article under the journal’s **CC BY 4.0 paper license**. The ChaLearn IPHD page requires citation but does not state an asset license for the base thermal files. The IPHPDT paper does not supply a separate dataset license for the labeled derivative in the accessible source material.

`DATASET_LICENSE_NOT_VERIFIABLE` for both the IPHD base assets and IPHPDT posture derivative. Citation is required. The paper’s CC BY status does not establish redistribution, model-training, consent, or derived-artifact rights for the dataset files.

### Payload evidence

The official ChaLearn page describes one-channel 16-bit PNG thermal images from a FLIR Lepton v3:

- original thermal size: 160×120, undistorted and unregistered to depth
- registered thermal-to-depth size: 213×120, with zero lateral bands added
- stored type: one-channel 16-bit PNG
- value convention: absolute temperature in Kelvin multiplied by 100
- invalid/missing encoding: zero-valued pixels can arise from depth-registration errors; interpolation around invalid mappings can create near-zero or intermediate non-plausible values
- labels: YOLO-style human boxes with constant class ID 0 on the base release
- sequence evidence: images originated in videos, but frame order was removed; the video ID remains in the filename
- example filename structure: video identifier plus frame identifier, such as `vid00057_8vpTIK5t`

The paper reports that IPHPDT selects and re-annotates IPHD images and uses four posture labels: the original names are `standing`, `sitting`, `lying`, and `bending`. It also describes image processing/inpainting, but no labeled derivative file, mask, exact processed bit depth, or compression stream was inspected. Consequently:

- IPHD base representation: `CALIBRATED_TEMPERATURE_MATRIX`
- IPHPDT derivative representation: `UNKNOWN` until the requested asset is obtained
- physical compatibility: IPHD `POTENTIALLY_CELSIUS_COMPATIBLE`; IPHPDT `POTENTIALLY_CELSIUS_COMPATIBLE` by source encoding claim but not payload-verified
- full payload status: `FULL_PAYLOAD_NOT_REQUIRED_FOR_D1`; the public base archive is too large for an unnecessary full download

### Grouping, semantics, and D1 decision

The base release exposes recording/video ID plus frame ID, but not a subject/session identity mapping. The data came from video and the frame order was intentionally removed, so correlated-frame leakage is likely if records are split as independent images. The IPHPDT train/test construction is reported as an 8:2 split after sampling and swapping; subject-disjointness is not established.

- grouping: `GROUPING_PARTIAL` for the base release because video ID/frame ID exist but subject/session fields were not verified; `GROUPING_WEAK` for the derivative’s accessible public evidence
- subject-disjoint split later: `NOT_VERIFIABLE`
- verified semantic inventory: `NORMAL_UPRIGHT` (`standing`), `NORMAL_SEATED` (`sitting`), `STATIC_LYING` (`lying`), `BENDING` (`bending`), and `PARTIAL_HUMAN`/human-box evidence where a visible person is boxed
- event evidence: `STATIC_LYING_POSTURE`, `NON_FALL_ACTIVITY_OR_POSTURE`, and `UNKNOWN`; no temporal-fall annotation was verified

`lying` is a static posture label, never a fall label. The base IPHD scripted examples include sitting on a sofa, laying on the floor, cooking, eating, computer work, and phone use, but the base boxes do not provide the IPHPDT posture labels.

**D1 source decisions:**

- IPHD base: `REFERENCE_ONLY` — public thermal and human-box evidence is useful for representation reference, but posture labels and asset terms are not verified.
- IPHPDT derivative: `HOLD_PENDING_ACCESS` — high-value bending/sitting/lying hard-negative semantics remain request-gated, and subject-disjoint use is not established.

## 5. Thermal-IM

### Identity, access, and license

The official sources are the [Thermal-IM repository](https://github.com/ZitianTang/Thermal-IM), its [CVPR paper](https://arxiv.org/abs/2304.13651), and the repository-linked [Google Drive release](https://drive.google.com/drive/folders/1oH3uHXeQAIfeHAsz2CFRxPKUJmC-x9sx?usp=share_link).

The public Drive folder listing exposed 50 ZIP archives. Two small official archives were downloaded for inspection:

| Official archive | Size | SHA-256 | Selected contents |
|---|---:|---|---|
| `20220613_7_split6.zip` | 15,167,944 bytes | `9f3a941629f6ec92c03e5434ca34a6562b17e55d87aebb0bed4660ac5ab735c4` | 63 depth `.npy` arrays, RGB/depth MP4s, `RGBT_T.mp4`, `annotation.json`, `info.npz` |
| `20220613_9_split7.zip` | 13,613,265 bytes | `56cde94b5db00c1b95ad7db3fe42be213f77b769333b9e9145c14728442bce5b` | 52 depth `.npy` arrays, RGB/depth MP4s, `RGBT_T.mp4`, `annotation.json`, `info.npz` |

`ACCESS_VERIFIED_PUBLIC`.

The repository README explicitly states that the dataset is released under **BSD-3-Clause**, and the official [LICENSE](https://github.com/ZitianTang/Thermal-IM/blob/main/LICENSE) contains the BSD-3-Clause terms. The paper publication license is separate from the dataset release notice. `DATASET_LICENSE_VERIFIED`; retain the required copyright/conditions/notice and citation when reusing or redistributing permitted derivatives.

### Actual thermal payload inspection

The inspected thermal member was `20220613_7_split6/RGBT_T.mp4`:

- file size: 119,801 bytes
- SHA-256: `668269bb2609e1144374ec463d78e750c4362da9f5754ed357b0c3a527eef783`
- container: ISO Base Media MP4
- video sample entry: `mp4v`
- visual sample entry: 384×288 pixels, 24-bit visual depth field
- timing: 63 frames over 4.2 seconds at 15 FPS; no wall-clock timestamps
- sample encoding: variable compressed sample sizes; no thermal numeric array or physical-unit metadata was present in the inspected container
- color/physical metadata: no embedded `colr` or palette metadata was found; the channel layout was not inferred beyond the visual sample entry

The README calls the stream `RGBT_T.mp4` and describes it as 288×384 at 15 FPS (height×width). The observed file therefore supports:

- representation: `NON_RADIOMETRIC_THERMAL_INTENSITY`
- physical compatibility: `INTENSITY_ONLY`
- no Celsius conversion: rendered intensity must not be converted into fabricated Celsius values

The selected archive’s `annotation.json` was 67 bytes, SHA-256 `26f970896b59c857b2ef2674050d579583a5480cb2b4dfd1be6f05bb68602db8`, with one interval: `start=0.63`, `end=1.35`, `action="touch"`, `object="book"`. The selected split7 archive also contained an empty `annotation.json` (`[]`, 2 bytes), demonstrating that an empty interaction list is not equivalent to a `NO_HUMAN` label.

The selected `info.npz` was 64,682 bytes, SHA-256 `d471717b44715e5805d9bb3d3cff32762fe6ca98b58f782a72a2c0663a6a7ff4`. It contains pose/extrinsic arrays including `pose_2d` with shape `(63,25,2)` and `pose_3d` with shape `(63,25,3)`, both float64 in the inspected file. The selected `RGBD_D_0.npy` is a NumPy array with dtype `<u2` and shape `(480,640)`; it is depth evidence, not thermal temperature evidence.

### Action vocabulary and grouping

The repository’s official occurrence chart and the inspected annotations establish the following original action-object vocabulary. Original names are retained here rather than converted into a new label taxonomy:

`touch phone`, `sit sofa`, `sit chair`, `touch bottle`, `touch book`, `sit stool`, `touch chair`, `sit desk`, `lie sofa`, `touch cabinet`, `take-off shoes`, `push-ups yoga mat`, `touch others`, `sit-ups yoga mat`, `step scale`, `leg-stretching yoga mat`, `touch yoga mat`, `touch laptop`, `touch cup`, `touch box`, `touch desk`, `touch clothes`, `touch dispenser`, `take-off clothes`, and `touch stool`.

The verified source inventory maps these to `NORMAL_SEATED` for the `sit ...` labels, `RECLINING`/`STATIC_LYING` for the explicit `lie sofa` label, and `OTHER` for object interactions and exercise/garment actions. `WALKING`, `BENDING`, `CROUCHING`, and `KNEELING` were not present in the exact action-object vocabulary verified from the official chart/selected annotations. No temporal-fall or post-fall label was verified. `lie sofa` is a static reclining posture proxy, not a fall event.

The README documents release-level `meta.csv` fields for actor, room, scene, and train/validation/test split, as well as a clip-level annotation contract. The two selected ZIP members did not include `meta.csv`, so the full actor count, exact split membership, and complete actor/room overlap audit remain open. Clip archive names provide a recording/clip identifier; there is no verified session ID or wall-clock time field.

- grouping: `GROUPING_PARTIAL`
- subject-disjoint split later: `POSSIBLY`
- leakage risk: high if frames are windowed without actor, room, scene, and clip grouping

**D1 source decision: `ADMIT_TO_D2_WITH_LIMITATIONS`.** The public payload and representation are sufficiently verified for controlled D2 compatibility analysis as a normal-motion/hard-negative source. It is not a positive fall source, and release-level actor/split metadata must be audited before any model-use decision.

## 6. QUIDA

### Identity, access, and terms

The official sources are the [PeerJ paper](https://doi.org/10.7717/peerj.19004), the [OSF project record](https://doi.org/10.17605/OSF.IO/YJGDV), and its public [OSF file record](https://osf.io/yjgdv/files/osfstorage/66d1364504fc5f45c5b0316c). The OSF API record was public, had `access_requests_enabled=true`, and reported `node_license=null`. The one `dataset.zip` file was public and had an OSF-reported size of 114,960,620 bytes.

`ACCESS_VERIFIED_PUBLIC`.

The downloaded official archive measured 114,960,620 bytes and had SHA-256:

`c312975bb91d436dcf5bec1c57dc1a857de0cef3c1a04c70d5267f50e662b47b`

The archive contained 55 members: five top-level sensor/timing files plus 10 subject directories, each with `accelerometer.csv`, `ir_camera.csv`, `LIDAR.csv`, and `radar.csv`. No license, licence, README, or terms file was present in the archive, and the OSF node’s `node_license` was null.

`DATASET_LICENSE_NOT_VERIFIABLE`.

The PeerJ paper’s publication terms are not treated as a grant of dataset rights. The paper requires citation and reports ethics approval under Universidad Andrés Bello Approval Act 032/2023. Redistribution, commercial use, derived-artifact scope, and local model-training permission remain unverified at the asset level.

### Actual thermal payload inspection

The representative file `subject_1/ir_camera.csv` was inspected directly from the official archive:

- member size: 25,288,322 bytes
- SHA-256: `9a167f2e80e9a8364892c3d2bf0757d7e7ac71d9d1498f3b17b9b75f0b05217a`
- format: comma-separated text, no header
- rows: 1,785
- fields per row: 769
- dtype/serialization: first field float Unix timestamp; remaining 768 fields decimal numeric text
- shape interpretation: exactly 32×24 = 768 thermal values per frame
- sample values: first-file observed range 20.2156–30.3393; across all 10 subject files, observed numeric extrema were approximately 2.90–928.26, indicating that later quality handling must account for extreme/outlier readings even when parsing succeeds
- invalid values: no non-finite or parse-failure values in the inspected rows; all 10 subject thermal files had uniform width 769 and no parse failures in the audit
- total thermal frames: 11,877 across the 10 subject files
- sampling: median inter-frame period 0.3845 seconds; observed 5th–95th percentile approximately 0.218–0.478 seconds

The paper identifies the thermal stream as a Melexis MLX90640 32×24 FIR camera and reports Celsius units. The actual file contains numeric values consistent with that contract, but the CSV has no embedded unit metadata. D1 classification is:

- representation: `CALIBRATED_TEMPERATURE_MATRIX`
- physical compatibility: `CANONICAL_CELSIUS_COMPATIBLE` based on the paper’s explicit Celsius convention plus actual 768-value thermal rows
- timestamp availability: Unix time in the first column
- compression: none in the CSV member
- missing sample handling: no missing rows or non-finite values observed in the audited thermal files; variable timing remains a quality field

The top-level `falls.csv` was also inspected:

- member size: 1,110 bytes
- SHA-256: `291ff714f1e3d1057091077afa8e7e8765cc706829754833bfe17c286063ca5d`
- shape: 10 rows × 10 columns
- semantics: each column is one subject and each row is one fall event timestamp, matching the paper’s description
- event count: 100 marked fall timestamps across 10 subjects
- correspondence: all 100 timestamps fell within the corresponding subject thermal recording range

### Semantics and grouping

The paper describes a protocol of walking without falling followed by 10 different simulated fall types. The source therefore supplies `TEMPORAL_FALL` evidence and limited `WALKING`/`NON_FALL_ACTIVITY_OR_POSTURE` context. It does not supply a rich independently labeled ADL/posture taxonomy. The 10 subject folders are explicit (`subject_1` through `subject_10`), the thermal recording is explicit by filename, and event timestamps are explicit in `falls.csv`.

- verified inventory: `WALKING`, `TEMPORAL_FALL`, and `OTHER` for the paper-described fall-type protocol
- event evidence: `TEMPORAL_FALL_EVIDENCE` plus limited `NON_FALL_ACTIVITY_OR_POSTURE`
- grouping: `GROUPING_PARTIAL` — subject, recording, frame/time are present; session/scene and an official split are absent
- subject-disjoint split later: `YES` — the explicit subject directories permit a deterministic subject-level split without inventing identity; no final split is defined here
- leakage risk: high under random windows because each subject contributes long contiguous recordings

These are simulated laboratory falls by young participants, not clinical or natural falls. No claim is made that the source reduces false falls.

**D1 source decision: `ADMIT_TO_D2_WITH_LIMITATIONS`.** The actual Celsius-compatible thermal payload and subject/event provenance are sufficiently verified for controlled D2 compatibility analysis, subject to asset-term confirmation, outlier/quality policy, and a later subject-level split.

## 7. eHomeSeniors

### Identity, access, and terms

The official sources are the [Sensors paper](https://doi.org/10.3390/s19204565), the [publisher supplementary page](https://www.mdpi.com/1424-8220/19/20/4565/s1), the [direct MDPI ZIP archive](https://mdpi-res.com/d_attachment/sensors/sensors-19-04565/article_deploy/sensors-19-04565-s001.zip), and the linked [Figshare record](https://figshare.com/s/753cc0df15197b0b9572).

The direct MDPI supplementary URL returned HTTP 200 with `application/zip` and `content-length: 278096147`. The archive was downloaded and inspected. The linked Figshare record currently reports **CC BY 4.0** but also displays “This item is shared privately” and returned a WAF challenge to a direct header request. The official publisher archive remained accessible, so the Figshare access issue does not block the publisher route.

`ACCESS_VERIFIED_PUBLIC` through the official MDPI supplementary route.

The archive measured 278,096,147 bytes and had SHA-256:

`e0b158800478b4e6f979bbc650c2fb51b171b6f872d537f0ad9de8d682a1773a`

The archive contained 362 members: 180 CSV files and 180 MATLAB `.mat` files. The package itself contained no separate license/readme/terms file. The linked asset record names CC BY 4.0; the article is also a CC BY 4.0 open-access publication. Therefore the asset classification is `DATASET_LICENSE_VERIFIED` with an operational limitation: preserve citation/attribution and confirm that the same CC BY scope applies to every raw field before redistribution. This is not a legal conclusion.

### Actual payload inspection

The representative MLX90640 file `eHomeSeniors dataset/melexis sensor/melexis-G1-1-f01.csv` was inspected:

- member size: 7,970,087 bytes
- SHA-256: `097b671be3ac30924cfc4b8d3cbc5b891985e2d5e10dfe057b3f7294a072c9b9`
- format: pipe-delimited text
- rows: 882, consisting of a metadata row, a field-label row, and 880 data rows
- data-row width: 1,668 fields; the field-label row is 1,604 fields and the initial metadata row is 22 fields, so the file is not a uniform header/data table
- first fields: timestamp, sensor model, 768 calibrated temperature fields, and additional raw sensor fields
- timestamp form: `HH:MM:SS`; the 880 data rows in the representative file have 57 unique second-level timestamps, so sub-second timing is not preserved in that field
- sample calibrated-temperature range in inspected data rows: approximately 14.09–27.31 °C in the representative file
- representation: `MIXED_REPRESENTATION` at source level because calibrated 32×24 temperature fields coexist with raw MLX90640 words and a parallel MATLAB release
- physical compatibility: `MIXED`; the calibrated temperature portion is Celsius-compatible, while raw fields require the documented sensor decoding and are not a second temperature matrix by assumption

The representative Omron file `eHomeSeniors dataset/omron sensor/omron-G1-1-f01.csv` was also inspected:

- member size: 99,807 bytes
- SHA-256: `007dc20def45f9ccaa4e764c77f603effc87850454e1c2bcb2932cb8e2ced20a`
- format: semicolon-delimited text
- rows: 323
- fields per row: 33 — one timestamp plus 32 temperature values representing the four 8-pixel sensor arrays described by the paper
- timestamps: human-readable date/time, from `2019-05-14 10:00:05` to `2019-05-14 10:01:10` in this representative file
- sample values: approximately 18.4–19.5 °C in the first three rows
- invalid values: no parse failures or non-finite values in the inspected sample
- representation: calibrated low-resolution temperature array, with source-level classification remaining `MIXED_REPRESENTATION`

The supplement contains 90 MLX90640 CSVs and 90 Omron CSVs, plus corresponding `.mat` files. File names follow the original form `sensor-GX-Y-fZZ`: sensor, group, volunteer number, and fall-type number. There are two groups, three volunteers per group, and 15 fall-type IDs per sensor. The paper defines group 1 as performing artists assisted to emulate older-adult fall characteristics and group 2 as healthy young people. Each file contains five falls except `omron-G2-3-f15`, which contains three, yielding the paper’s reported 448 falls.

### Semantics and grouping

The original source labels are file-name fall-type IDs `f01` through `f15`, not a per-frame normal/posture label. The paper documents 15 staged fall types and says ordinary activity immediately before a fall may include standing, walking, sitting, or lying down. That context is not independently labeled in the files. The verified source inventory is therefore `TEMPORAL_FALL` for the file/event protocol and `UNKNOWN`/`NON_FALL_ACTIVITY_OR_POSTURE` for unlabelled preceding context. No independent normal ADL class is admitted from that context.

- event evidence: `TEMPORAL_FALL_EVIDENCE` from the per-file fall protocol; `NON_FALL_ACTIVITY_OR_POSTURE` only as unlabelled preceding context
- grouping: `GROUPING_PARTIAL` — group/volunteer/fall-type and recording file are explicit; frame timestamps exist, but no session ID, scene field, or official split is supplied
- subject-disjoint split later: `YES` — volunteer IDs are explicit in every file name; no final split is defined here
- repetition evidence: five falls per file except the documented three-fall exception; individual repetition IDs are not a separate label field
- leakage risk: high if frames or files are randomly split across a volunteer

These are staged falls by volunteers, not clinical or natural falls. A file’s fall-type ID is not a clinical label, and preceding standing/walking/sitting/lying context must not be used as independently labeled hard-negative data without a later annotation decision.

**D1 source decision: `ADMIT_TO_D2_WITH_LIMITATIONS`.** The official payload, numeric temperature fields, raw-field presence, and subject/file grouping are verified. D2 must preserve the mixed representation, confirm asset-level terms for raw fields, apply a subject-level split, and keep unlabelled context separate from labeled fall events.

## 8. Access / License Matrix

### Compact D1 summary

| Source | Access | License | Representation | Grouping | Semantic value | D1 decision |
|---|---|---|---|---|---|---|
| TF-66 | `ACCESS_REQUIRES_MANUAL_REQUEST` | `DATASET_TERMS_LIMITED` | `UNKNOWN` | `GROUPING_PARTIAL`; later `POSSIBLY` subject-disjoint | Staged temporal falls plus free-text normal/ADL context | `HOLD_PENDING_ACCESS` |
| IPHD base | `ACCESS_VERIFIED_PUBLIC` | `DATASET_LICENSE_NOT_VERIFIABLE` | `CALIBRATED_TEMPERATURE_MATRIX` | `GROUPING_PARTIAL`; later `NOT_VERIFIABLE` subject-disjoint | Human boxes and scripted posture/context reference | `REFERENCE_ONLY` |
| IPHPDT derivative | `ACCESS_REQUIRES_MANUAL_REQUEST` | `DATASET_LICENSE_NOT_VERIFIABLE` | `UNKNOWN` until payload access | `GROUPING_WEAK`; later `NOT_VERIFIABLE` subject-disjoint | `standing`, `sitting`, `lying`, `bending` posture labels | `HOLD_PENDING_ACCESS` |
| Thermal-IM | `ACCESS_VERIFIED_PUBLIC` | `DATASET_LICENSE_VERIFIED` | `NON_RADIOMETRIC_THERMAL_INTENSITY` | `GROUPING_PARTIAL`; later `POSSIBLY` subject-disjoint | Normal human-object interactions and motion hard negatives | `ADMIT_TO_D2_WITH_LIMITATIONS` |
| QUIDA | `ACCESS_VERIFIED_PUBLIC` | `DATASET_LICENSE_NOT_VERIFIABLE` | `CALIBRATED_TEMPERATURE_MATRIX` | `GROUPING_PARTIAL`; later `YES` subject-disjoint | Timestamped simulated falls plus walking/no-fall context | `ADMIT_TO_D2_WITH_LIMITATIONS` |
| eHomeSeniors | `ACCESS_VERIFIED_PUBLIC` | `DATASET_LICENSE_VERIFIED` | `MIXED_REPRESENTATION` | `GROUPING_PARTIAL`; later `YES` subject-disjoint | Staged falls; preceding normal context is not independently labeled | `ADMIT_TO_D2_WITH_LIMITATIONS` |

| Source | Access classification and tested evidence | Paper publication license | Dataset asset license / terms | Model training / redistribution status |
|---|---|---|---|---|
| TF-66 | `ACCESS_REQUIRES_MANUAL_REQUEST`; public metadata/helper repos, actual video README requires email to Chris Silver | Publisher article is open access under a Creative Commons license | `DATASET_TERMS_LIMITED`; CC BY-NC 4.0 plus request gate and non-commercial statement | Not independently confirmed for a particular local or redistributed derivative; request terms first |
| IPHD base | `ACCESS_VERIFIED_PUBLIC`; official thermal ZIP returned HTTP 200 | IPHPDT paper is CC BY 4.0; this does not license the base assets | `DATASET_LICENSE_NOT_VERIFIABLE`; citation requested, asset license absent on inspected page | Not verified |
| IPHPDT derivative | `ACCESS_REQUIRES_MANUAL_REQUEST`; corresponding-author request stated in paper | CC BY 4.0 for the paper | `DATASET_LICENSE_NOT_VERIFIABLE` | Not verified; request labels and terms |
| Thermal-IM | `ACCESS_VERIFIED_PUBLIC`; official Drive listing and two archive downloads succeeded | CVPR paper publication terms are separate | `DATASET_LICENSE_VERIFIED`; repository states BSD-3-Clause for the dataset | Reuse is subject to BSD notice/conditions; no additional consent scope was stated in the repository |
| QUIDA | `ACCESS_VERIFIED_PUBLIC`; public OSF node/file and official ZIP download succeeded | PeerJ paper publication terms are separate | `DATASET_LICENSE_NOT_VERIFIABLE`; OSF `node_license=null`, no archive terms file | Not verified; obtain asset terms before redistribution or training release |
| eHomeSeniors | `ACCESS_VERIFIED_PUBLIC`; official MDPI supplementary ZIP returned HTTP 200 and was inspected | CC BY 4.0 open-access Sensors paper | `DATASET_LICENSE_VERIFIED` from linked asset metadata reporting CC BY 4.0; package has no embedded license file | Preserve attribution; confirm raw-field scope before public redistribution |

Paper open-access status, dataset asset terms, participant consent/privacy scope, local model-training permission, and permission to redistribute raw or derived data are separate questions. This matrix deliberately does not infer one from another.

## 9. Payload Representation Matrix

| Source | Sensor / native representation | Stored representation inspected or verified | Resolution / dtype / units | Timing / invalid encoding | D1 representation class |
|---|---|---|---|---|---|
| TF-66 | Calumino CTS-EVK; paper reports native 35×15, 4 FPS | Actual video unavailable; public helper expects `.avi`/cached frames | Reported 140×60 stored/upscaled workflow; actual bit depth/codec/radiometric state unverified | Frame indices and video lengths in XLSX; actual timestamps/invalid encoding unverified | `UNKNOWN` |
| IPHD base | FLIR Lepton v3 thermal | One-channel 16-bit PNG per official page | Original 160×120; registered 213×120; K×100 | Video order removed; zero values from registration/depth errors | `CALIBRATED_TEMPERATURE_MATRIX` |
| IPHPDT | IPHD-derived thermal images with processing/inpainting described in paper | Labeled derivative not obtained | Source K×100 claim; processed dtype/mask/bit depth unverified | Image-level derivative; sequence details unverified | `UNKNOWN` |
| Thermal-IM | RGB-T thermal camera | `RGBT_T.mp4`, actual `mp4v` visual stream | 384×288 observed (README states 288×384); 24-bit visual sample-entry field; no units | 63 frames/4.2 s/15 FPS; no wall-clock timestamps; no physical-unit metadata | `NON_RADIOMETRIC_THERMAL_INTENSITY` |
| QUIDA | Melexis MLX90640 FIR array | Comma-separated numeric CSV | 32×24 = 768 decimal values; paper identifies °C | Unix timestamp; no invalid parses in audited files; timing variable | `CALIBRATED_TEMPERATURE_MATRIX` |
| eHomeSeniors | MLX90640 plus four-array Omron D6T-8L-06 system | Pipe-delimited MLX CSV with temperature and raw fields; semicolon-delimited Omron CSV; matching `.mat` files | MLX 32×24 temperature fields plus raw words; Omron 32 values; paper reports °C | Timestamp fields, no compression; mixed header/data widths in MLX file | `MIXED_REPRESENTATION` |

Rendered thermal video is not automatically radiometric. No source was converted to Celsius during D1.

## 10. Grouping / Leakage Matrix

| Source | Subject | Session | Recording/video | Scene/room | Frame/window/time | Grouping class | Subject-disjoint split later |
|---|---|---|---|---|---|---|---|
| TF-66 | Volunteer ID explicit in metadata workbook | Not verified | Recording name and frame fields | Room ID and height explicit | Frame start/first/last and before/after fields | `GROUPING_PARTIAL` | `POSSIBLY` |
| IPHD/IPHPDT | Not verified in public asset evidence | Not verified | Video ID plus frame ID in filename; frame order removed | Not verified | Frame ID only; no temporal order | `GROUPING_PARTIAL` base / `GROUPING_WEAK` derivative evidence | `NOT_VERIFIABLE` |
| Thermal-IM | Actor field documented in release README; full file not obtained | Not verified | Clip/archive identifier and per-clip files | Room and scene fields documented; exact full inventory not inspected | Start/end seconds in `annotation.json`; no wall-clock timestamps | `GROUPING_PARTIAL` | `POSSIBLY` |
| QUIDA | `subject_1`–`subject_10` explicit | Not explicit | Sensor file per subject | Not explicit; one lab geometry described | Unix timestamps and `Falls.csv` event times | `GROUPING_PARTIAL` | `YES` |
| eHomeSeniors | Group/volunteer ID explicit in file names | Not explicit | Sensor + volunteer + fall-type file | Not explicit; common lab setup | Timestamped rows, five-fall file protocol, no repetition field | `GROUPING_PARTIAL` | `YES` |

No random frame split is authorized. Later windows must be grouped by subject and, where available, session, recording, room/scene, and event lineage before any D2 evaluation.

## 11. Semantic Inventory

The following table preserves source wording and uses only demonstrated or explicitly described semantics. It does not treat static posture as a fall and does not upgrade staged events to clinical/natural falls.

| Source | Original source labels / demonstrated semantics | SafeNest inventory classes | Event evidence |
|---|---|---|---|
| TF-66 | Free-text actions including walking, sitting, standing, laying, crawling, empty room, chair/bed/standing/walking falls, collapse, trip, faint-like collapse, and occasional roll/squirm after fall | `NO_HUMAN`, `NORMAL_UPRIGHT`, `NORMAL_SEATED`, `WALKING`, `STATIC_LYING`, `CRAWLING`, `TEMPORAL_FALL`, `POST_FALL`, `OTHER` | `TEMPORAL_FALL_EVIDENCE`, `POST_FALL` context where text says roll/squirm; staged only |
| IPHD base | Scripted sit-sofa, lay-floor, cooking/eating/computer/phone examples; human boxes with base class 0 | `NORMAL_SEATED`, `STATIC_LYING`, `OTHER`, `PARTIAL_HUMAN` where box visibility is partial | `STATIC_LYING_POSTURE`, `NON_FALL_ACTIVITY_OR_POSTURE`; no temporal fall |
| IPHPDT | Exact posture labels `standing`, `sitting`, `lying`, `bending` | `NORMAL_UPRIGHT`, `NORMAL_SEATED`, `STATIC_LYING`, `BENDING` | `STATIC_LYING_POSTURE`, `NON_FALL_ACTIVITY_OR_POSTURE`; no event timing |
| Thermal-IM | `touch phone`, `sit sofa`, `sit chair`, `touch bottle`, `touch book`, `sit stool`, `sit desk`, `lie sofa`, `take-off shoes`, `push-ups yoga mat`, `step scale`, and other exact action-object pairs | `NORMAL_SEATED`, `RECLINING`, `STATIC_LYING`, `OTHER`; empty annotation is `UNKNOWN`, not `NO_HUMAN` | `NON_FALL_ACTIVITY_OR_POSTURE`; no temporal fall label |
| QUIDA | Walking without falling followed by 10 paper-described simulated fall types; `Falls.csv` gives event timestamps, not posture names | `WALKING`, `TEMPORAL_FALL`, `OTHER` | `TEMPORAL_FALL_EVIDENCE` and limited walking/no-fall context |
| eHomeSeniors | File labels `f01`–`f15`; paper-described fall types; preceding standing/walking/sitting/lying context is not separately labeled | `TEMPORAL_FALL`, `UNKNOWN`, `OTHER` | `TEMPORAL_FALL_EVIDENCE`; preceding context remains unlabelled |

## 12. Celsius / Intensity Compatibility Matrix

This is advisory feedback only. It does not freeze `P1_TRAIN_FITTED_GLOBAL_ZSCORE` or define final preprocessing.

| Source | Celsius-compatible? | Intensity-only? | Shared P1 plausibility | Advisory finding |
|---|---|---|---|---|
| TF-66 | `NOT_VERIFIABLE` | `NOT_VERIFIABLE` | `NOT_VERIFIABLE` | Actual release representation is required; do not assume the described `.avi` is Celsius or intensity without inspection. |
| IPHD base | `POTENTIALLY_CELSIUS_COMPATIBLE` | `NO` | `REQUIRES_D2` | K×100 is documented, but zero registration errors and registered/unregistered variants require a D2 quality/mask policy. |
| IPHPDT | `POTENTIALLY_CELSIUS_COMPATIBLE` | `NO` | `REQUIRES_D2` | Source encoding is described, but the processed/inpainted labeled payload is not inspected. |
| Thermal-IM | `NO` | `YES` | `NOT_PLAUSIBLE` across physical-temperature sources without a domain boundary | Actual `mp4v` visual stream has no physical temperature metadata. Do not manufacture Celsius values. |
| QUIDA | `YES` | `NO` | `PLAUSIBLE` within the calibrated-array lane; cross-source use still requires D2 | Actual 768-value CSV rows and paper Celsius convention align; outlier/variable-timing policy remains. |
| eHomeSeniors | `YES` for calibrated MLX/Omron fields; raw fields are separate | `NO` for calibrated fields | `REQUIRES_D2` | Calibrated values are compatible, but source-level raw/calibrated mixture and timestamp serialization require explicit D2 handling. |

The immediate PRE implication is a representation boundary: QUIDA and the calibrated portions of eHomeSeniors can be considered for a physical-temperature lane; Thermal-IM is an intensity-only lane; TF-66 and IPHPDT remain unresolved or partially verified. A shared P1 across these sources is not established by D1.

## 13. D1 Source Decisions

| Source | Decision | Reason |
|---|---|---|
| TF-66 | `HOLD_PENDING_ACCESS` | High semantic value and strong metadata, but actual video release, encoding, asset scope, and subject-isolated split remain request-gated. |
| IPHD base | `REFERENCE_ONLY` | Public K×100 thermal/base boxes are useful reference evidence, but posture labels and asset license are not verified. |
| IPHPDT derivative | `HOLD_PENDING_ACCESS` | Paper-described bending/sitting/lying labels are valuable, but the labeled payload and terms require author request and subject isolation is not proven. |
| Thermal-IM | `ADMIT_TO_D2_WITH_LIMITATIONS` | Public thermal payload and interval annotations are verified; it is intensity-only, lacks a verified fall label, and release-level split metadata remains incomplete. |
| QUIDA | `ADMIT_TO_D2_WITH_LIMITATIONS` | Public 32×24 numeric temperature payload, timestamps, subject directories, and fall event times are verified; asset terms, outliers, limited no-fall semantics, and split remain. |
| eHomeSeniors | `ADMIT_TO_D2_WITH_LIMITATIONS` | Official supplement, numeric calibrated fields, raw fields, source IDs, and staged-fall file protocol are verified; normal context is not independently labeled and asset scope/raw-field handling require care. |

No source receives `ADMIT_TO_D2` without limitations. D1 admission is not training authorization.

## 14. Unresolved Access Actions

1. **TF-66:** email the named primary author using the procedure in the public README only if the owner authorizes that request. Ask for the actual video/cache release, payload bit depth/codec/radiometric status, consent and redistribution terms, participant/room/session inventory, and the exact Train/Test subject overlap. No request was submitted here.
2. **IPHPDT:** request the labeled derivative, box/pose label schema, inpainting/mask details, source video/frame mapping, asset terms, and subject/session split metadata from the corresponding author. Do not infer access from the public IPHD base link.
3. **IPHD:** before D2 use, confirm the base asset terms and whether K×100 values are allowed for local model training and derived-data publication. Preserve zero/error masks rather than treating zeros as normal temperature.
4. **Thermal-IM:** obtain or locate the release-level `meta.csv` and audit actor counts, room/scene overlap, split membership, and clip IDs before any window extraction. Keep its `NON_RADIOMETRIC_THERMAL_INTENSITY` boundary explicit.
5. **QUIDA:** confirm asset-level terms with the OSF record/owners, document the outlier policy for values outside plausible room/body ranges, and define a later subject-level split without changing source IDs.
6. **eHomeSeniors:** confirm that the CC BY 4.0 asset record covers both calibrated and raw MLX90640 fields in the publisher ZIP; preserve original file names, group/volunteer IDs, fall-type IDs, and the documented three-fall exception.

## 15. Limitations

- TF-66 video payload was not accessible without a manual author request; only public metadata/helper files were inspected.
- IPHD’s official thermal training archive is approximately 1.70 GB and was not downloaded; the official schema and HTTP header evidence were sufficient for the D1 access/representation classification. IPHPDT’s labeled derivative was not obtained.
- The Thermal-IM release-level `meta.csv` was documented by the official README but was not present in the two selected clip archives, so full actor/room/split membership was not independently audited.
- QUIDA’s OSF node has no asset license in API metadata and no terms file in the archive. Numeric parsing succeeded, but extreme values were observed and require later quality handling.
- eHomeSeniors’ direct publisher archive is accessible, while its linked Figshare record currently reports a private/WAF state. The archive has no embedded license file; the CC BY 4.0 finding comes from the linked asset record and paper/publisher metadata.
- Source-level payload classes can conceal subrepresentations. eHomeSeniors is explicitly mixed; IPHD has registered and unregistered variants; TF-66 and IPHPDT remain partly unresolved.
- No final subject split, window duration, resampling, Celsius conversion, normalization, label remapping, quality exclusion, or preprocessing profile was selected.
- All fall evidence reviewed here is staged/simulated or paper-described; none is clinical or natural-fall evidence. Static lying/reclining is not a fall event.
- No result in this report demonstrates a reduction in false falls, model performance, Raspberry Pi performance, MR60 validation, clinical performance, or real-home generalization.
- Existing SafeNest captures remain reference-only and were not used. `LOCKED_PUBLIC_TEST_ACCESS` remains `0`.

## 16. TV2-D1 Gate Recommendation

**`PASS_WITH_LIMITATIONS`**

The gate passes with limitations because QUIDA, eHomeSeniors, and Thermal-IM provide independently verified, materially useful payload evidence for controlled D2 compatibility work. The gate is constrained by:

- TF-66 actual payload access requiring a manual request;
- IPHPDT posture-label access requiring a manual request;
- unresolved asset-level terms for IPHD and QUIDA;
- intensity-only Thermal-IM representation;
- mixed calibrated/raw eHomeSeniors representation;
- incomplete release-level split verification for Thermal-IM and no official split for QUIDA/eHomeSeniors;
- no subject-disjoint proof for IPHD/IPHPDT;
- no preprocessing freeze.

The next authorized phase may perform controlled D2 compatibility analysis on the admitted sources while preserving source, subject, session, recording, timestamp/window, extraction profile, original label, mapped semantic class, split, and quality provenance. D2 must not silently merge Celsius-compatible matrices with rendered intensity video, must not use random frame splits, and must not treat D1 as permission to train or modify model artifacts.

### Explicit exclusions

`NO TRAINING` · `NO DATASET MERGE` · `NO MODEL CHANGE` · `NO LOCKED TEST ACCESS` · `NO TEAM REPO CHANGE` · `NO INTEGRATION CHANGE` · `NO PI WORK` · `NO EXECUTION MAP UPDATE`
