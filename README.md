# 🛡️ NHS De-Identification Gate

**Trusted Data & AI Infrastructure — Encode Club hackathon.**
*How can organisations collaborate on AI without sharing sensitive data?*

Free-text clinical notes are the hardest NHS data to share, because identifiers are buried in prose.
This tool is a **de-identification gate**: it detects and removes patient/clinician PII *inside* each
NHS Trust, so only de-identified text ever leaves. That's the missing on-ramp to an **NHS Secure Data
Environment (SDE) / Trusted Research Environment** — the "code comes to the data, data never leaves"
model behind OpenSAFELY and the NHS Federated Data Platform — and the privacy layer that makes
cross-Trust / federated AI (e.g. FLock.io) safe.

Built on **Microsoft Presidio** + **spaCy**, evaluated on
[NHSEDataScience/synthetic_clinical_notes](https://huggingface.co/datasets/NHSEDataScience/synthetic_clinical_notes).

## Headline result (verifiable)

```
python -m src.evaluate        # all 1,602 notes
→ Leakage test: PASS ✅  |  overall recall 100.0%  |  0 identifier leaks
   recall by type: names 100% · NHS number 100% · DOB 100% · place 100% · record-id 100%
```

We don't hand-annotate. Each note links (`person_id`/`admission_id`) to a patient + admission record
holding the real (synthetic) identifiers — a **free ground-truth oracle**. The metric is *detection
coverage*: every known identifier occurring in a raw note must sit inside a detected span (and so be
removed). It's mode-independent, so it can't be gamed by pseudonymisation.

## Architecture

```
                 ┌──────────────────── inside Trust A ────────────────────┐
 raw notes ──►   │  ftfy clean ─► Presidio Analyzer ─► Anonymiser ─► audit │  ──► de-identified
 (PHI)           │     spaCy NER + UK/NHS recognizers   redact|pseudonymise│       text + audit log
                 │     + Trust roster (deny-list)        (Faker, vault)     │       (no PHI leaves)
                 └────────────────────────────────────────────────────────┘
        same gate runs inside Trust B ──►  ┌─────────────────────────┐
                                           │  shared de-identified pool │ ──► federated AI / FLock.io
                                           └─────────────────────────┘
```

**Detection (two layers):**
- *Presidio built-ins:* `PERSON`, `DATE_TIME`, `LOCATION`, `ORGANIZATION`, `NRP`, `PHONE_NUMBER`,
  `EMAIL_ADDRESS`, `UK_NHS`, …
- *Custom NHS layer (`src/recognizers/`):* NHS number with **Modulus-11** checksum (+ the dataset's
  9-digit/comma forms), `UK_POSTCODE`/`UK_NINO`/`UK_PASSPORT`/`UK_VEHICLE_REGISTRATION` (not shipped in
  this Presidio version), GMC/NMC clinician IDs, ODS org codes, record UUIDs, and a **Trust roster**
  deny-list (the legitimate hybrid: NER generalises, the roster guarantees known identifiers are caught).

**Anonymisation (`src/anonymize.py`), per-entity policy:**
- **Pseudonymise** (default) — consistent Faker(en_GB) fakes via a Trust-local vault; valid fake NHS
  numbers; postcode → outward code; dates shifted by one consistent offset (intervals preserved).
- **Redact** — `<ENTITY_TYPE>` tags. `NRP` (special-category) is always redacted, never synthesised.

## Trust & governance — mapped to the NHS Five Safes
- **Safe data** — de-identified to DAPB1523/ICO standard across the full entity set.
- **Safe settings** — runs inside the Trust; raw CSVs + vault are gitignored, never leave.
- **Safe outputs** — only de-identified text + content-free audit logs; leakage test gates at **0**.
- **Safe people/projects** — vault (re-id key) stays Trust-local; pseudonymised data is still personal
  data under UK GDPR — stated honestly, no over-claim.

## Run it

```bash
python -m venv .venv; .\.venv\Scripts\Activate.ps1      # Windows PowerShell
pip install -r requirements.txt
python -m spacy download en_core_web_sm                 # PII_SPACY_MODEL=en_core_web_lg for more recall

python -m src.load_data        # download + ftfy-clean the dataset
python -m src.evaluate         # the leakage test (0 leaks, 100% recall)
python -m src.trust_demo       # two NHS Trusts share only de-identified data
streamlit run app/streamlit_app.py   # demo UI: Try-it · Metrics · Governance · Two-Trust
python -m pytest tests/ -v
```

## Layout
`src/` — `load_data` (oracle) · `analyzer` · `recognizers/` · `anonymize` · `pipeline` · `evaluate` ·
`trust_demo`. `app/streamlit_app.py` — demo. `tests/` — checksum, recognizers, pseudonym consistency,
end-to-end leakage. Built with Claude Code (`CLAUDE.md`, `.claude/`).
