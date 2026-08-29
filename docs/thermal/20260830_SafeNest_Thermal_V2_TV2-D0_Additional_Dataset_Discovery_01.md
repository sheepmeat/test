# SafeNest Thermal V2 — TV2-D0 Additional Thermal Dataset Discovery

- Worker: Luna 1
- Date: 2026-08-30
- Repository: `sheepmeat/test`
- Phase: `TV2-D0`
- Scope: additional thermal/infrared dataset discovery only
- Recommendation: `PASS_WITH_LIMITATIONS`
- Training authorization: `NONE`
- Locked-test access: `0`

This report is a source-discovery and triage artifact. No model was trained, no existing dataset was modified, no raw archive was downloaded, and `LOCKED_PUBLIC_TEST` was not opened or used. A source described as a fall dataset may contain staged temporal falls; that does not make it a clinical or natural-fall dataset. SafeNest's `HUMAN_FALL_PROXY` remains a derived proxy label.

## 1. Search Scope

The search was performed against official dataset pages, papers, project repositories, and repository-linked download/access pages available on 2026-08-30. The target failure mode was `HUMAN_NORMAL -> HUMAN_FALL_PROXY` false positive. Priority therefore went to sources containing one or more of:

- bending, crouching, kneeling, sitting, reclining, lying, walking, near-floor posture, partial visibility, occlusion, unusual orientation, or scene variation;
- actual temporal fall transitions, while keeping them distinct from static lying/post-fall images;
- low-resolution thermal arrays or calibrated temperature values that could be adapted to the SafeNest thermal input contract;
- subject/session/sequence metadata and a defensible split protocol.

The triage scale is:

- `HIGH_VALUE`: strong semantic fit, subject to explicit D1 access/representation validation;
- `PROMISING_WITH_ADAPTATION`: useful for a defined hard-negative or temporal lane, with adaptation or evidence gaps;
- `REFERENCE_ONLY`: useful for sensor/label/method reference but weak as a training candidate;
- `LOW_VALUE`: technically related but unlikely to address this false-positive mode;
- `REJECT`: provenance, modality, or relevance is insufficient;
- `UNRESOLVED`: potentially useful, but access or evidence is not currently verifiable.

No source was ranked on reported model accuracy. The relevant questions are whether the source supplies semantically useful thermal evidence and whether its provenance, license, grouping, and representation can be validated in a later D1/D2 phase.

## 2. Existing Lead Re-check

The current thermal baseline and historical T-A0 evidence were re-read before searching. The baseline uses the SDT family and the current execution map remains unchanged. The historical source-identity report is [T-A0 source identity](../reports/20260810_Codex_T-A0_Thermal_Dataset_Selection_Source_Identity_01.md); the active authority is the [Thermal V2 master execution map](20260830_SafeNest_Thermal_V2_Master_Execution_Map_01.md).

| Existing lead | Current evidence and exact identity | Re-check result |
|---|---|---|
| SDT / Simulated/real thermal fall posture data | Official [CVL SDT page](https://cvl.tuwien.ac.at/research/cvl-databases/sdt-icip/) and [Zenodo record](https://doi.org/10.5281/zenodo.4124309). The current T-A0 material contains empty/sitting/standing/lying examples, FLIR Lepton 3.5 thermal plus depth, and non-commercial research terms. Subject/session identity is not sufficient for a new subject-disjoint enrichment lane. | `REFERENCE_ONLY` for this task. It is the current baseline family, not an additional candidate; no re-ranking or retraining is authorized here. |
| eHomeSeniors | Official [Sensors paper](https://pmc.ncbi.nlm.nih.gov/articles/PMC6832422/) and its [supplementary data link](https://www.mdpi.com/1424-8220/19/20/4565/s1), which currently points to a public [Figshare package](https://figshare.com/s/753cc0df15197b0b9572). MLX90640 is a 32×24 FIR array at about 16 FPS with numeric temperature fields; Omron D6T-8L-06 is a much lower-resolution 1×8 array reported with upper/lower readings. Six volunteers perform 15 fall types, five repetitions each, with 448 recorded falls after the reported exclusions. The paper reports 180 CSV files organized by sensor/subject/fall type. The same recording context includes ordinary activity before a fall, but normal posture labels are not a strong, independent class. Files are per subject/sensor/fall type, but no official subject-disjoint split is supplied. Exact numeric bit depth/serialization, camera orientation per file, and compression details require supplement inspection. | `REFERENCE_ONLY` to `PROMISING_WITH_ADAPTATION`. Public access is now a viable re-check lead, but the small six-person, largely single-room/staged-fall design and absent official split make it a sensor/temporal reference until D1 validates the supplement and grouping. |
| MUVIM | Official [FallDetection repository](https://github.com/MUVIM/FallDetection) and [paper](https://arxiv.org/abs/2206.12740). The dataset combines infrared, depth, RGB, thermal, and wearable modalities; the repository requires an email request, a stated subject, affiliation/contact details, and a data privacy waiver. The repository also warns that some trials were lost to corruption and that some RGB fall trials were included erroneously. The paper describes fall/ADL trials from 30 healthy adults plus ADL from 10 older adults. | `UNRESOLVED` / access-restricted. It remains scientifically interesting, but a direct public thermal download, dataset license, retained thermal trial inventory, and subject-isolated split were not verified. Do not treat the repository or paper as permission to obtain or redistribute data. |
| Thermal Fall 66 / TF-66 | Official [Engineering Applications of Artificial Intelligence article](https://doi.org/10.1016/j.engappai.2025.111819). The paper reports 66 participants, nine indoor environments, 562 fall videos/57,694 frames, and 250 non-fall videos/90,921 frames from a ceiling-mounted Calumino CTS-EVK at native 35×15 and 4 FPS. It describes 12 staged fall templates, preceding and succeeding frames, and non-fall activity capture. The article says public/non-commercial access through the project, while its data-availability wording says data will be made available on request; no current direct project download was located. Public payload bit depth/codec/compression, exact orientation metadata, and radiometric status are not yet verified. | `HIGH_VALUE` semantically, `D1-BLOCKED` operationally. This is the strongest broad candidate if access, file representation, and subject split are confirmed. The public/test split is video/frame based and participant isolation is not explicitly guaranteed. |
| TSF / Thermal Simulated Fall | Official [Fall-detection repository](https://github.com/ivineetm007/Fall-detection). The repository describes 9 normal-activity videos and 35 thermal fall/other-normal videos and asks researchers to contact the author. No dataset license is stated. Literature describes a very small, staged, single-actor/single-room collection; the repository does not provide enough metadata to independently validate subject/session grouping. | `REFERENCE_ONLY` / `LOW_VALUE`. It is useful for historical method comparison only and is too small and narrow to be a credible TV2 hard-negative source. |
| Local Family A / screenshot tree | The historical T-A0 report identifies these as local RGB/colorized thermal screenshot material with unresolved identity, provenance, and license. No exact public dataset identity or official download was recovered. | `REJECT`. Do not use as an additional dataset lead. |

## 3. New Sources

### 3.1 Thermal-IM — strongest accessible hard-negative lead

**Identity and official source.** “What Happened 3 Seconds Ago? Inferring the Past with Thermal Imaging,” Zitian Tang et al., CVPR 2023. Official [paper](https://arxiv.org/abs/2304.13651) and [project repository](https://github.com/ZitianTang/Thermal-IM).

**Access and license.** The official repository exposes a dataset download link to [Google Drive](https://drive.google.com/drive/folders/1oH3uHXeQAIfeHAsz2CFRxPKUJmC-x9sx?usp=share_link) and states that the dataset is available under BSD-3-Clause. The release-level terms and whether every linked asset is covered should still be checked before any derived-data work or redistribution.

**Thermal representation.** The repository describes synchronized RGB, thermal, and depth videos. The thermal stream is `RGBT_T.mp4`, 288×384 at 15 FPS. It is distributed as thermal video rather than a verified radiometric temperature matrix; classify it as `NON_RADIOMETRIC_THERMAL_INTENSITY` until D1 inspects the actual files. The video codec/compression, bit depth, exact camera orientation metadata, and temperature encoding are not established from the public repository; the varied viewing angles are a scene attribute, not a substitute for sensor-pose metadata.

**Human semantics.** The dataset contains 783 clips, approximately 560,000 frames, and about 10.4 hours. Each clip has 0–9 annotated human-object interactions. The action inventory includes walking, sitting, and kneeling, with room/furniture/viewpoint variation; whether individual clips provide usable partial visibility or interaction occlusion must be verified from the files. No official fall, lying, or reclining label was verified. This is therefore a normal-behavior/hard-negative source, not a fall-positive source.

**Grouping and leakage.** The repository provides `meta.csv` fields for actor, room, scene, and train/validation/test split, and describes held-out actor/room components. Exact actor/session counts and a complete subject-isolation guarantee were not verified from the public repository. Clip/frame correlation remains high if windows are sampled without actor/scene grouping.

**TV2 value.** `PROMISING_WITH_ADAPTATION`. It is the best directly accessible lead for normal thermal motion and posture context. It needs temporal/window extraction, actor/scene grouping audit, and adaptation to the SafeNest 62×80 contract. It does not by itself supply a positive fall-proxy lane.

### 3.2 IPHPDT / IPHD — strongest static posture hard-negative lead

**Identity and official source.** “Identity-Preserved Human Posture Detection in Infrared Thermal Images,” Yongping Guo et al., Sensors 2023. Official [paper](https://doi.org/10.3390/s23010092) and underlying [ChaLearn IPHD dataset page](https://chalearnlap.cvc.uab.cat/dataset/34/description/).

**Access and license.** The IPHPDT paper states that its data are available from the corresponding author upon reasonable request. The underlying IPHD page exposes challenge-era thermal downloads, but that does not establish that the IPHPDT posture labels are included or that either asset may be redistributed. The paper's open-access license applies to the paper, not automatically to the dataset. Dataset license: `NOT_VERIFIABLE`.

**Thermal representation.** IPHD uses FLIR Lepton v3 thermal frames at 160×120; the paper describes each pixel as absolute temperature in Kelvin multiplied by 100. IPHPDT applies processing/inpainting to address zero-valued registration errors. Classify the source thermal values as `CALIBRATED_TEMPERATURE_MATRIX`, with a required D1 check for the processed image encoding and any zero/inpaint mask. Processed-image bit depth/serialization, compression, capture orientation, and sequence/fps metadata are not established; this is an image-level source rather than a verified temporal stream.

**Human semantics.** The paper reports approximately 75,000 posture images with boxes and four classes: standing, sitting, lying, and bending. Bending is directly relevant to `HUMAN_NORMAL -> HUMAN_FALL_PROXY`; the paper also discusses confusion from shallow bend angles, sitting occlusion, clothing, ambient temperature, clutter, and public/private/wild capture conditions. The data are image-level, not a temporal fall sequence, so “lying” must not be interpreted as a fall event.

**Grouping and leakage.** The reported final train/test counts are 62,010 and 13,267 images after sampling/swapping. Subject, session, and sequence isolation are not established by the public paper; an image split may contain correlated frames or identities. This is a D1 blocker for any training use.

**TV2 value.** `PROMISING_WITH_ADAPTATION`. It is the clearest posture-hard-negative lead, particularly for bending and near-floor/lying ambiguity, but access to the labeled derivative and a defensible subject split must be resolved first.

### 3.3 QUIDA — sensor-compatible temperature/event reference

**Identity and official source.** “Multimodal dataset for sensor fusion in fall detection,” Taramasco et al., 2025. Official [PeerJ paper](https://doi.org/10.7717/peerj.19004) and [OSF data record](https://doi.org/10.17605/OSF.IO/YJGDV).

**Access and license.** The paper points to the public OSF record and the record is currently discoverable. An asset-level license could not be verified consistently from the official article/OSF presentation; do not assume unrestricted redistribution. Record license as `NEEDS_D1_CONFIRMATION`.

**Thermal representation.** The thermal stream uses a Melexis MLX90640 32×24 FIR array, positioned about 1 m above the floor and 1.5 m from the fall area, at about 2.6 Hz (384 ms). The paper describes CSV files with Unix timestamps and temperature values in °C. Classify it as `CALIBRATED_TEMPERATURE_MATRIX` pending a D1 file check. CSV numeric serialization/bit depth, exact camera orientation, and any compression or missing-sample behavior require inspection of the OSF files; the timestamp rate is the reported sampling interval, not a guaranteed clean video FPS.

**Human semantics.** Ten young adult subjects (8 male, 2 female) perform ten simulated fall types, including tripping, fainting, sit-down, knee-flexion, and forward/backward/lateral variants. Fall times are manually marked and the source includes temporal fall/no-fall segments; no-fall material is mainly outside the fall windows and follows a walking protocol rather than a rich ADL/posture protocol. These are simulated events, not clinical or natural falls.

**Grouping and leakage.** The OSF organization uses individual subject directories and a `Falls.csv` timing file, which is useful for subject grouping. No official train/validation/test split was identified. Window correlation is high if a random window split is used; D1 must make a subject-level split.

**TV2 value.** `PROMISING_WITH_ADAPTATION`. It is unusually compatible with the current 32×24 temperature-array lineage and supplies temporally marked fall/no-fall material, but has weak normal hard-negative diversity, one lab geometry, ten subjects, young participants, and unresolved dataset-level terms.

## 4. Comparative Table

| Candidate | Thermal form / sensor | Normal and fall semantics | Subjects, sessions, and split evidence | Access / license state | TV2-D0 value and main D1 blocker |
|---|---|---|---|---|---|
| [Thermal Fall 66](https://doi.org/10.1016/j.engappai.2025.111819) | Calumino CTS-EVK; native 35×15, 4 FPS. Public payload may be rendered `.avi`; radiometric status is not yet verified, so `NON_RADIOMETRIC_THERMAL_INTENSITY` provisionally. | 250 non-fall videos plus 562 staged temporal fall videos; nine environments and 12 fall templates. Strongest normal/fall context. | 66 participants; participant IDs reportedly exist in folders. `Train`/`Test` is 80/20 by videos/frames; subject isolation not proven. | Article says public/non-commercial, while data availability says request; direct download not located. | `HIGH_VALUE` semantically. D1 must obtain the release, reconcile access wording, inspect payload, and prove subject grouping. |
| [IPHPDT / IPHD](https://doi.org/10.3390/s23010092) | FLIR Lepton v3, 160×120, Kelvin×100 source values; processed/inpainted posture images; `CALIBRATED_TEMPERATURE_MATRIX`. | Standing, sitting, lying, bending; excellent static hard-negative coverage, no event timing. | About 75k images; final train/test 62,010/13,267. Subject/session isolation not verifiable. | Labels by reasonable request; underlying IPHD download has separate challenge terms; dataset license unresolved. | `PROMISING_WITH_ADAPTATION`. D1 must secure labeled derivative, terms, masks, and subject-disjoint grouping. |
| [Thermal-IM](https://github.com/ZitianTang/Thermal-IM) | `RGBT_T.mp4`, 288×384, 15 FPS; rendered video, `NON_RADIOMETRIC_THERMAL_INTENSITY`. | 783 clips, ~10.4 h, walking/sitting/kneeling and object interactions; no verified fall/lying labels. | Actor/room/scene metadata and train/validation/test fields; exact actor count and full isolation not verified. | Public repository download; repository states BSD-3-Clause. | `PROMISING_WITH_ADAPTATION`. D1 must audit actor/scene splits and extract hard-negative windows. |
| [QUIDA](https://doi.org/10.7717/peerj.19004) | Melexis MLX90640, 32×24, ~2.6 Hz, °C CSVs; `CALIBRATED_TEMPERATURE_MATRIX`. | Ten simulated fall types with manually marked temporal windows; limited walking/no-fall context. | 10 subjects with subject directories; no official split. | Public OSF record; asset-level license needs confirmation. | `PROMISING_WITH_ADAPTATION`. D1 must validate files/terms and define subject-level windows. |
| [eHomeSeniors](https://pmc.ncbi.nlm.nih.gov/articles/PMC6832422/) | MLX90640 32×24, ~16 FPS numeric temperatures plus raw fields; Omron low-resolution array; `CALIBRATED_TEMPERATURE_MATRIX`. | 448 staged falls and ordinary activity preceding falls; normal posture labeling is weak. | Six volunteers, per-subject/per-sensor files; no official subject-disjoint split. | Supplement is publicly linked; article is open access/non-commercial research, but release-level terms need D1 confirmation. | `REFERENCE_ONLY` / `PROMISING_WITH_ADAPTATION`. D1 should validate supplement schema and use it primarily for sensor/temporal reference. |

The candidates are complementary rather than interchangeable. Thermal-IM and IPHPDT address normal-posture false positives; TF-66 supplies the broadest fall/ADL/context lane; QUIDA and eHomeSeniors are closer to the low-resolution temperature-array lineage but are smaller and less diverse.

## 5. Top Serious Candidates

1. **Thermal Fall 66 — `HIGH_VALUE`, conditional.** Best overall semantic fit: substantial participant/environment coverage, non-fall activity, temporal fall windows, ceiling view, and native low spatial resolution. It should be the first D1 access/provenance request. It is not approved for training because the article's public-versus-request wording, exact payload representation, license, and subject-isolated split remain unresolved.

2. **IPHPDT/IPHD — `PROMISING_WITH_ADAPTATION`.** Best direct match for the false-positive boundary between standing/sitting/bending/lying. It is image-level posture evidence and therefore should be used to test or enrich posture hard negatives only after the labeled derivative, temperature encoding, and subject grouping are verified. Static lying is not a fall event.

3. **Thermal-IM — `PROMISING_WITH_ADAPTATION`.** Best currently discoverable normal-motion source with a stated dataset license, temporal thermal video, actor/room metadata, and walking/sitting/kneeling interactions. It lacks fall labels, so its role is hard-negative and temporal-context enrichment rather than positive generation.

4. **QUIDA — `PROMISING_WITH_ADAPTATION`.** Best native sensor-format/event reference among the new leads: 32×24 MLX90640 temperatures, timestamps, subject directories, and marked simulated fall windows. It is limited by ten young subjects, one laboratory geometry, narrow no-fall behavior, no supplied split, and unresolved asset terms.

5. **eHomeSeniors — `REFERENCE_ONLY` / conditional.** Valuable for numeric MLX90640/Omron handling and staged fall timing at small thermal-array resolution. It is not a strong solution to the normal-posture false-positive problem because the normal activity semantics and subject diversity are limited.

Recommended D1 order is TF-66 access and payload verification, IPHPDT label/provenance verification, Thermal-IM actor/scene split audit, QUIDA OSF/license/schema audit, and eHomeSeniors supplement/schema audit. D1/D2 must preserve source, subject, session, recording, timestamp/window, extraction profile, label mapping, split, and quality provenance for every derived sample if a later phase is authorized.

## 6. Rejected / Low-Value Sources

| Source | Decision | Reason |
|---|---|---|
| MUVIM | `UNRESOLVED`, not a current top candidate | Strong multimodal research relevance, but request-plus-privacy-waiver access, no verified public license/download, reported corruption/lost trials, and no verified subject-isolated split make it operationally blocked for the current discovery gate. |
| TSF / Thermal Simulated Fall | `REFERENCE_ONLY` / `LOW_VALUE` | Contact-gated, no stated dataset license, very small staged collection, and narrow actor/room coverage. It does not provide enough independent normal hard negatives. |
| LWIRPOSE | `REFERENCE_ONLY` | Official [paper](https://arxiv.org/abs/2404.10212) and [repository](https://github.com/avinres/LWIRPOSE) provide 2,461 640×480 LWIR images, seven subjects, 12 activities, and a documented subject split, but no verified fall/lying labels and no explicit dataset license. Useful as pose/occlusion reference, not a fall-proxy source. |
| TADAR | `LOW_VALUE` / `REFERENCE_ONLY` | Official [paper](https://arxiv.org/abs/2409.17742) and [repository](https://github.com/aiot-lab/TADAR) expose a thermal-array sensing/ranging dataset and case-study material, but a clearly exposed posture/fall label contract, subject split, and dataset license were not verified. The code license does not automatically license the data. |
| Local Family A and screenshot tree | `REJECT` | Identity, provenance, source license, sensor semantics, and redistribution rights are unresolved. |
| TsetFall, TST, RGB-only fall corpora, and ambient-IR/depth-only sources | `REJECT` for this lane | They do not provide the calibrated or image-form thermal evidence required for the present thermal false-positive investigation. Ambient IR/depth/RGB is not interchangeable with thermal radiance or temperature data. |

## 7. Limitations

- This was a metadata and official-source review. No raw archive, sample frame, CSV, video, or label file was downloaded or inspected. Resolution, bit depth, compression, temperature calibration, timestamps, and orientation claims marked “provisional” require D1 file inspection.
- “Public,” “open access,” and “download link” do not by themselves establish an asset-level license, redistribution permission, consent scope, or ability to publish derived samples. TF-66, IPHPDT/IPHD, QUIDA, MUVIM, TSF, and eHomeSeniors all retain an access/terms question of different severity.
- A paper's train/test folders or frame counts do not prove subject-disjoint evaluation. Correlated frames, clips, recordings, and repeated staged performances must be grouped by subject and, where applicable, session/recording before any later model-selection use.
- Staged falls and static lying are different semantics. None of these sources should be relabeled as natural falls, clinical falls, or safety outcomes.
- The current SafeNest 62×80 input contract, per-frame normalization, and three proxy classes are not automatically compatible with any candidate. Any later adaptation must be specified and validated without using `LOCKED_PUBLIC_TEST`.
- The search cannot establish that any one source will reduce the current `HUMAN_NORMAL -> HUMAN_FALL_PROXY` error until a separately authorized, subject-grouped D1/D2 evaluation is performed. No such evaluation was performed here.

## 8. TV2-D0 Gate Recommendation

**Gate: `PASS_WITH_LIMITATIONS`.** The search found credible candidates worth deeper D1/D2 work, led by TF-66, IPHPDT/IPHD, Thermal-IM, QUIDA, and eHomeSeniors. The candidates cover the needed complementary evidence: dynamic fall/ADL context, bending/sitting/lying hard negatives, normal thermal motion, and low-resolution calibrated-temperature sequences.

This gate means discovery is sufficient to continue to controlled source validation. It does **not** mean that any candidate is approved for training, import, derived-data generation, model selection, or public-test evaluation. The next authorized decision should resolve access/license, raw-versus-rendered thermal representation, label semantics, subject/session grouping, leakage controls, and quality accounting before any later phase uses data.

Explicitly out of scope and unchanged: model training, model or runtime files, existing datasets, manifests outside this report, `LOCKED_PUBLIC_TEST`, Team-repository integration, Raspberry Pi or sensor work, and the Thermal V2 master execution map.
