# SafeNest D2 — Locked public cross-device test acquisition and cryptographic seal

- Date: 2026-08-22
- Phase: **D2 acquisition/checksum lane only**. No D0 split work, D1 adapter, R1 features, training, or D2 evaluation.
- Manifest: `datasets/mmwave/manifests/M-PV0_D2_locked_acquisition/`
- Parent freeze: M-PV0 commit `18e4a4e86d6bf95795d6749a91ce303ad3f1c417`
- Gate: **`BLOCKED`** (`D2_PAYLOAD_ACQUISITION = BLOCKED_AUTH_REQUIRED`)

This lane exists to identify canonical D2, acquire the untouched IEEE DataPort object if a legitimate session exists, hash it as an opaque blob, and keep the lock. It does not inspect physiological contents.

---

## 1. Canonical D2 identity

| Field | Value |
|---|---|
| Role | `LOCKED_PUBLIC_CROSS_DEVICE_TEST` |
| Publication DOI | `10.1038/s41597-026-07016-6` |
| Dataset DOI | `10.21227/wq68-sv85` |
| Publisher | IEEE DataPort |
| Landing page | `https://ieee-dataport.org/open-access/new-dataset-millimeter-wave-radar-vital-sensing-reference-signals` |
| Announced object | `VITALSENSE_120_DATASET.zip` |
| Sensor | 120 GHz mmWave radar |
| Subjects | 24 |
| Protocol (public metadata) | resting; normal → instructed breath-hold → normal |

The Scientific Data article’s data-availability statement points only at the IEEE DataPort DOI. D2 was not replaced with another public radar dataset.

---

## 2. Why D2 stays unseen

D2 is the only reserved public radar for a later cross-device test. Using it for representation, family, seed, threshold, calibration, augmentation, or candidate inference would leave no unseen public radar after M-PV3. Downloading the zip, if it later succeeds, still does not unlock those uses.

---

## 3. Acquisition result

**Did not succeed.** IEEE DataPort shows `LOGIN TO ACCESS DATASET FILES` for the open-access zip. Dataset DOI `10.21227/wq68-sv85` redirects to that landing page (HTTP 302 then 200). This environment had no IEEE account session, cookies, or tokens. Authentication was not bypassed. No Kaggle, Drive, or GitHub zip was substituted (`DO_NOT_SUBSTITUTE`).

Other V2 development lanes may continue. D2 is **not** acquisition-ready.

---

## 4. Local cryptographic identity

Not established. No local SHA-256, SHA-512, MD5, or exact byte count exists because the canonical object was not downloaded.

Intended gitignored storage role, if a later authenticated download occurs:

```text
datasets/raw_archives/external_datasets/VITALSENSE_120_DATASET.zip
```

No absolute local path is stored in the manifests.

---

## 5. Publisher checksum

IEEE DataPort landing-page HTML contained **zero** SHA-256 or MD5 mentions. M-PV0 already recorded `NOT_PUBLISHED_ON_AUDITED_LANDING_PAGES`. This lane did not invent a published checksum.

---

## 6. Byte-size evidence

Public claims remain approximate metadata:

- IEEE DataPort Dataset Files: **28.69 MB**
- M-PV0 GitHub README inheritance: **about 31 MB**

No authoritative exact-byte publisher value was found. Exact local bytes are `null` until authenticated acquisition. This is not classified as corruption.

---

## 7. Authentication / access

| Item | State |
|---|---|
| Access mode | `IEEE_DATAPORT_OPEN_ACCESS_LOGIN_REQUIRED` |
| Login required | YES |
| IEEE session in this environment | NO |
| Payload acquisition | `BLOCKED_AUTH_REQUIRED` |

A later run with a legitimate logged-in session may hash the same announced filename as an opaque blob. That future download still leaves D2 locked.

---

## 8. No archive member or signal inspection

This lane did not unzip the payload, run `unzip -l` / `unzip -t`, open `.mat` files, list archive members from a downloaded object, load arrays, plot, compute RR/amplitude/spectrum, create windows, or run V1/V2. D2 scripts do not call `zipfile`, `loadmat`, `numpy.load`, or `h5py`.

Landing-page Instructions that describe expected `.mat` names remain public metadata from M-PV0. They are not an archive listing of a local blob.

Derived D2 artifacts produced here: **0** arrays, samples, windows, features, plots, payload-derived labels, and model outputs.

---

## 9. Current lock state

```text
PUBLIC_METADATA_ACCESS = YES
PAYLOAD_ACQUISITION = BLOCKED_AUTH_REQUIRED
PAYLOAD_SEMANTIC_INSPECTION = NO
ARCHIVE_MEMBER_LISTING = NO
FEATURE_EXTRACTION = NO
MODEL_INFERENCE = NO
MODEL_INFERENCE_COUNT = 0
LOCK_STATE = LOCKED_BEFORE_SEMANTIC_USE
ROLE = LOCKED_PUBLIC_CROSS_DEVICE_TEST
```

Repository scan found no D2 identity in training, scaler, threshold, augmentation, or candidate-ranking configs. Hits remain in the V2 roadmap, M-PV0 lock, and this custody lane.

---

## 10. What remains prohibited

Until M-PV3 freezes a FLOAT identity and an explicit D2 evaluation authorization exists:

- representation / feature / model-family / seed / threshold / calibration / augmentation selection from D2
- candidate inference (`count` must stay 0)
- semantic inspection of the zip or `.mat` contents
- using D2 results to reopen model selection

This PR does not start that evaluation.
