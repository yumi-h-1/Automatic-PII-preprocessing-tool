# NoteGuard

**Automatic PII de-identification for NHS clinical notes — clean data in, no identifiers out.**

NoteGuard is a clinical-text de-identification pipeline in a Streamlit app. It combines **rule-based
detection**, **Presidio NER** and **patient-consistent pseudonymisation** so free-text clinical data can
be used for analysis without exposing the people in it. It runs **at the point of use** ("sanitise at
source"), so text is cleaned inside its own governance boundary before it is shared.

Bring your own text and get de-identified data back, or pick a clinical domain and download a
de-identified cohort. Uploaded data is processed **in memory only and never stored**.

## The app — two tabs

A short **"How it works"** walkthrough (Add data → Detect & remove → Review & download) greets you.

1. **De-identify your data** — paste text, or upload a `.txt` / `.csv` / `.pdf` (CSV picks the free-text
   column; multi-row files de-identify as a batch). You see the detected identifiers highlighted, a
   **donut chart** of how many of each type were found, a **table to review every change**, and a
   one-click download. Files are processed **in memory only** — nothing touches disk (asserted by
   [tests/test_privacy.py](tests/test_privacy.py)).
2. **Get data by domain** — choose a clinical domain (diabetes, cardiovascular, respiratory, mental
   health, cancer, renal) and download a **de-identified** cohort from the NHSE synthetic notes. Every
   record passes through the same de-identification gate first.

The UI follows the **NHS.UK** look (NHS Blue header, NHS palette, green action buttons). Detection is
fully deterministic and runs locally: no external model, no API key, no network call with your text in it.

**Data:** the only dataset the tool ships against is the Hugging Face
[`NHSEDataScience/synthetic_clinical_notes`](https://huggingface.co/datasets/NHSEDataScience/synthetic_clinical_notes)
set (synthetic — no real patients). Anything else comes in through the upload tab, which accepts any
free text you give it.

## What makes this more than "just Presidio"

Presidio is the detection **engine** — we don't reinvent it. NoteGuard is the clinical layer around it:

1. **Domain adaptation to messy clinical text.** NHS-aware recognisers: checksum-validated NHS numbers
   **plus** context-anchored detection for the dataset's 9-digit synthetic numbers Presidio's `UK_NHS`
   misses, plus GMC/NMC clinician IDs, ODS org codes and record UUIDs.
2. **Patient-consistent de-identification.** Same patient → same surrogate across their whole admission
   journey. Only date-of-birth is treated as PII (shifted by a consistent per-patient offset); visit /
   admission dates are clinically useful and left intact. Realistic en_GB fakes (or `[label]` redaction).
3. **Pluggable + degrades gracefully.** One `Detector` interface (Rule / Presidio); the pure-Python
   rule layer runs even if spaCy/Presidio are unavailable, and the model auto-resolves
   `lg → sm → rules` to whatever is installed.
4. **Human-in-the-loop by design.** Low-confidence spans are redacted anyway and flagged `needs_review`,
   so over-redaction — not leakage — is the failure mode.
5. **Governance wrapper.** A per-note audit of what was removed, mapped to the NHS **Five Safes**,
   **Caldicott Principles** and **DPA 2018 / UK GDPR**.

## Pipeline

```
your text / a domain cohort
        │
        ▼  ingest in memory (txt/csv/pdf → records, no disk)        src/ingest.py · src/cohorts.py
        ▼  fix mojibake                                             src/data.py
        ▼  detect  =  rules  ∪  Presidio NER                        src/recognisers.py · src/detect.py
        │            overlap-safe merge; precise rules win
        ▼  transform  =  redact  |  pseudonymise + DOB date-shift   src/transform.py  (patient-consistent Faker vault)
        ▼  review (donut chart + change table)  →  download         streamlit_app.py
```

## Measured performance

These numbers are recorded here, in the README, and nowhere else — the tool itself ships no evaluation
code, no metrics dashboard and no ground-truth join, so the engine can only ever see the note text.

The evaluation was run once, on **2026-08-31**, over all **1,602 notes** of the NHSE synthetic set
(1,027 known-PII occurrences), with `en_core_web_lg` and redaction. The dataset keeps its PII in
structured patient/admission tables, so those tables could be joined back to each note as ground truth
and every known identifier checked against the sanitised output.

| Detector | NHS number F1 | PERSON recall | **Residual leakage** |
|---|---|---|---|
| rules only | 0.98 | 0.00 | **74.9 %** |
| **presidio + rules** (shipping) | **0.98** | **0.69** | **4.7 %** |

**Residual leakage** — known identifiers still visible after sanitisation — is the number that matters
for a de-identification tool: it is the miss rate, the privacy risk. The rules→engine drop is the
headline; it shows exactly what the NER engine buys you.

Overall precision in that run was 0.12–0.19, and that figure is a conservative lower bound, not a real
error rate: the ground truth is the patient tables only, so correctly removing a clinician's name —
which is *not* in those tables — is scored as a false positive. Most of those "false positives" are real
identifiers the ground truth simply doesn't list.

> Over-redaction is the safe direction. Precision costs you utility. Recall costs you privacy. Those
> aren't symmetric.

*The harness that produced this table (`src/evaluate.py`, `tests/run_eval.py`, the published snapshot and
the ground-truth join) was removed in the "focus the tool on de-identification" change; it is recoverable
from git history at commit `09343db` if the measurement needs to be repeated.*

## Project layout

```
src/
  data.py          load the NHSE synthetic notes (free text only) + mojibake repair
  recognisers.py   pure-Python rules: NHS checksum/context, postcode, date, phone, email, GMC/NMC/ODS, UUID
  detect.py        RuleDetector / PresidioDetector behind one Detector interface
  transform.py     redaction | patient-consistent pseudonymisation + DOB date-shift (Faker vault)
  ingest.py        in-memory bytes → records for txt/csv/pdf (no disk writes)
  cohorts.py       derive clinical-domain cohorts from note text (keyword tagging)
  pipeline.py      single-note detect -> sanitise -> audit
tests/             unit tests incl. test_privacy.py (no-disk-writes)
docs/              DEPLOY_STREAMLIT_CLOUD.md
streamlit_app.py   the web app (Streamlit Cloud entry point)
requirements.txt   Streamlit Cloud deps    pyproject.toml   packaging + lint/test config
.streamlit/config.toml   NHS theme + viewer mode
```

## Trust & governance
- **Safe data** — PII removed to DAPB1523/ICO standard across patient + staff + org identifiers.
- **Safe settings** — processing is local/in-memory; raw CSVs and the re-id vault are gitignored, never leave.
- **Safe outputs** — only de-identified text plus a content-free audit ever leaves the tool.
- **Caldicott / DPA 2018 / UK GDPR** — pseudonymised data is still personal data (stated honestly, no
  over-claim); data minimisation + storage limitation (in-memory, never stored); special-category data
  always redacted, never pseudonymised.

## Run it locally

```bash
python -m venv .venv
source .venv/bin/activate            # Windows: .\.venv\Scripts\Activate.ps1
pip install -e ".[app,dev]"
python -m spacy download en_core_web_lg   # or en_core_web_sm for a lighter run

streamlit run streamlit_app.py            # the app (De-identify · Get data by domain)
pytest -q                                 # unit tests
```

The dataset is pulled from Hugging Face on first run. To run fully offline, drop the notes CSV in a
folder and set `NOTEGUARD_DATA_DIR=/path/to/csv`.

## Deploy the live demo — Streamlit Community Cloud (free, no card)

Point <https://share.streamlit.io> at this repo with main file `streamlit_app.py`. `requirements.txt`
ships the small spaCy model so it fits the free tier's RAM, and `build_detector` auto-uses whichever
model is installed. Full steps: [docs/DEPLOY_STREAMLIT_CLOUD.md](docs/DEPLOY_STREAMLIT_CLOUD.md).

## Data notes (found by inspecting the data, not assuming)
- NHS numbers in this synthetic set are **9 digits** (real ones are 10 + mod-11 check). We catch both:
  checksum-validated 10-digit anywhere, **and** context-anchored numbers after an "NHS …" label.
- Some fields are double-encoded (`Â·`); `_fix_mojibake` repairs them before detection.

Built with Claude Code (`CLAUDE.md`, `.claude/`).
