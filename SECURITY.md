# Security

Jeevia handles health information about patients and the identities of the staff who treat them. This page lists
what we protect, against whom, how, and how each control is checked. Everything here runs in the code in this
repository and is covered by tests (`backend/tests/test_security.py` and others named below).

> Prototype scope: the deployment holds synthetic or public sample data only (`JEEVIA_DATA_ORIGIN`). The controls
> are built as they would be for real records.

## What we protect

| Asset | Where it lives |
|---|---|
| Patient identifiers: name, phone, village, proxy's name | `patients`, `consents` tables (encrypted) |
| Clinical record: intake, triage note, urgency, referrals | `encounters`, `referrals` tables (identifiers removed from free text) |
| Uploaded reports, photos, voice recordings | disk / S3 / Cloudinary (encrypted, deleted on schedule) |
| Staff identities and credentials | `users` (PIN hashed), sign-in codes (hashed, expire in 5 minutes) |
| Audit trail | `audit_events` (hash-chained, append-only) |
| Secrets: signing key, data key, provider keys | `backend/.env` on the server only, never committed |

## Threats and how each is handled

| # | Threat | Controls | Checked by |
|---|---|---|---|
| T1 | **Stolen database or backup** | Patient names, phones, villages and proxy names are encrypted with Fernet (AES-128-CBC + HMAC-SHA256) under `JEEVIA_DATA_KEY`. Phones are found through a keyed hash (HMAC-SHA256, separate derived key), so the number is never stored readable. Free text has names, phone, Aadhaar, ABHA and email removed before storage. Staff PINs and sign-in codes are stored as PBKDF2-SHA256 hashes. | `test_patient_identifiers_are_ciphertext_in_the_database`, `test_rows_stored_before_encryption_are_encrypted_at_start_up`, `test_privacy.py` |
| T2 | **Stolen file storage** (disk, bucket, Cloudinary account) | Every file is encrypted before it leaves the API; the store only holds ciphertext. Photos are redacted before storage (faces blurred, ID numbers blacked out, location data removed). Files are deleted after 24 h (voice), 3 days (photos) or 30 days (reports). | `test_uploaded_files_are_encrypted_on_disk`, `test_images.py`, retention tests |
| T3 | **Someone signs in as staff** | SMS or email code **and** a personal PIN; weak PINs refused; 5 wrong PINs lock the account for 15 minutes; code requests limited per phone (3 in 10 minutes, 10 a day) and per address; every sign-in check is also rate-limited. Sessions last 60 minutes; refresh tokens rotate and can be revoked. Staff kiosks must be registered devices. | `test_api.py` (PIN, lockout, refresh, bound device), `test_security.py` |
| T4 | **Staff see more than their job needs** | Role checks on every route: front desk sees names and tokens only; supervisors and admins never open clinical notes or documents; employers see fitness status only; documents open only for the treating doctors and nurses at that facility. Group counts under 5 show as "<5". | `test_admin_cannot_read_clinical_notes`, `test_employer_sees_cohorts_only`, `test_orgs.py` |
| T5 | **A QR referral slip is photographed or forwarded** | The QR holds a random token only; opening it also needs the 6-digit code printed beside it. 8 wrong codes lock the link. Links expire (a week at most), can be revoked, and each opening is logged with the opener's address. The summary leaves out the phone number, village, proxy's name and anything occupational. Document links inside it last 10 minutes. | `test_shares.py`, `test_shared_summary_leaves_out_contact_details` |
| T6 | **Guessing and flooding** (codes, links, kiosk lookups, AI calls that cost money) | Per-device and per-address limits per minute: 30 for public links and kiosk lookups, 20 for speech, voice and translation, 20 for uploads, 10 for sign-in checks; a kiosk lookup is also limited to 5 per phone number in 10 minutes. A refusal returns 429 with Retry-After. | `test_public_links_are_rate_limited`, `test_kiosk_lookup_is_limited_per_phone` |
| T7 | **Malicious upload** (a program renamed `.png`, a scripted SVG, an XML bomb) | The type is read from the file's bytes, never its name or the browser's label, and must match both the upload kind and the claimed type. SVG is accepted only for the app's own sample reports and only without scripts, event handlers or external links, and it is parsed with `defusedxml`. Files are served with `nosniff` and a sandboxing policy, so nothing in them can run. 8 MB limit. | `test_the_contents_decide_the_file_type`, `test_sniffing`, `test_a_recording_must_be_audio` |
| T8 | **Attacks through the browser** (cross-site scripting, clickjacking, leaky caches) | The web app sends a Content Security Policy (scripts only from itself, data only from itself and the API, no framing), HSTS, `nosniff`, `Referrer-Policy` and a camera/microphone policy. The API sends `default-src 'none'`, `frame-ancestors 'none'`, `no-store` caching on all data, and HSTS on HTTPS. CORS allows only the listed web origins, with no cookies. | `test_api_sends_browser_protections` |
| T9 | **Patient data leaks to AI services** | Offline models (speech, translation, OCR, summary, voice) run on the facility's own machine. Online engines (Sarvam, Bhashini) are used only with the patient's AI consent, and only after identifiers are removed. "Continue without AI" turns all of it off. A guard blocks the summary model from writing diagnoses or drug advice. | `test_language_extras.py`, `test_consent_required`, output-guard tests |
| T10 | **Misconfigured production server** | With `JEEVIA_ENV=production` the server refuses to start on a default or short signing secret, a missing data key, mock sign-in codes, a `*` or plain-http CORS origin, or rate limits switched off. The API's interactive docs are off in production. | `test_production_refuses_development_settings` |
| T11 | **Insider tampering or denial** | Every view, edit, override, export, share opening, redaction, guard block and purge is logged. Each event's SHA-256 hash includes the previous one, and a database trigger refuses updates and deletes. Supervisors can verify the chain and export it. | `test_views_are_audited_and_chain_verifies`, `test_audit_is_append_only` |
| T12 | **Vulnerable dependencies or leaked secrets in code** | CI fails on any known vulnerability in the Python dependencies (pip-audit) or in the browser-side JavaScript (npm audit, high and above), any medium or high finding of the code scanner (bandit), and any secret found in the git history (gitleaks). | `.github/workflows/ci.yml`, job `security` |

## Scan results (8 Oct 2026)

| Scan | Scope | Result |
|---|---|---|
| pip-audit | `backend/requirements.txt` | No known vulnerabilities |
| bandit (medium and high) | `backend/app` | 0 findings. Fixed: uploaded SVGs now parsed with `defusedxml`; the summary-model URL must be http(s). Reviewed and marked: model loads from local folders (B615), fixed table names in the encryption backfill (B608), TwiML text escaping (B406), the OAuth word "bearer" (B105). 1 low remains: a `try/except/pass` around an optional voice. |
| npm audit (shipped code) | `frontend`, production dependencies | 0 vulnerabilities, after updating `sharp` and `source-map-js` |
| npm audit (development tools) | `frontend`, all dependencies | 5 high in `braces` used by the lint tools (`eslint-config-next`); no fixed version exists yet. They never reach a browser or the server. |
| gitleaks | the full git history (25 commits) and all uncommitted files | No secrets. One false positive allowlisted: image-crop names (`cropKey: 'crop_…'`) in the old prototype. |

## DPDP Act 2023 checklist

| Duty under the Act | How Jeevia meets it |
|---|---|
| Consent that is free, specific, informed and unambiguous (s. 6) | A consent record is needed before any intake. It is self or proxy (with relationship), read aloud in the patient's language, and covers named scopes; "Continue without AI" is a real choice. |
| Notice of what is collected and why (s. 5) | The consent screen and the spoken text say what is collected, for triage only, who sees it and for how long, in the patient's language. |
| Purpose limitation and data minimisation (s. 4, 6) | Only triage fields are asked for. Identifiers are removed from free text. Employers see fitness only. Shared summaries leave out contact details. Group counts under 5 are hidden. |
| Storage limitation (s. 8(7)) | Voice deleted after 24 h, photos after 3 days, reports after 30 days, by an hourly job that logs each deletion. |
| Reasonable security safeguards (s. 8(5)) | Encryption at rest, role-based access, two-factor staff sign-in, rate limits, upload checks, browser protections, an audit trail and scanning in CI (above). |
| Accuracy and completeness (s. 8(3)) | Read-back and confirmation of what the patient said, report-value checks, missing-information prompts, and staff review before anything is final. |
| Breach notification (s. 8(6)) | The audit trail shows who saw what and when, so the scope of a breach can be found. The procedure for notifying the Board and patients is to be written by the deploying facility; not built here. |
| Children's data, verifiable guardian consent (s. 9) | Under 18, the server refuses any consent that is not given by a mother, father or guardian, and the kiosk sends the helper back to the consent step. The guardian's name and relationship are recorded and audited. Identity documents are not checked; staff confirm the guardian at the desk. (`test_under_18_needs_a_parent_or_guardian`) |
| Rights to access, correction and erasure (s. 11–13) | Staff can correct records (every correction is logged). A patient portal and self-service erasure are not built; requests go through the facility. |
| Grievance redressal (s. 13) | Every patient slip shows the grievance contact, set per deployment (`JEEVIA_GRIEVANCE_CONTACT`), in the patient's language. The process behind it belongs to the deploying facility. |
| Cross-border transfer (s. 16) | Offline models keep data on the facility's machine. The online engines (Sarvam, Bhashini) are hosted in India. |

## Known limits

- **Encryption scope.** Free text, notes and lab values are stored with identifiers removed but are not themselves
  encrypted. Real records would also need whole-database encryption (PostgreSQL on an encrypted volume) and a key
  manager (KMS) instead of a key in an environment variable.
- **Name search** decrypts patient records on the server to match part of a name. This is fine for a facility's
  patients, but a large registry would need a searchable index.
- **Rate limits** are kept in memory for one server process. Several servers would share a Redis counter.
- **Key loss.** If `JEEVIA_DATA_KEY` is lost or changed, encrypted records cannot be read. There is no key rotation yet.
- **No external penetration test** has been done.

## Reporting a problem

Open a private security advisory on this repository, or email the maintainers. Never put patient data in an issue.
