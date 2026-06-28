# NoteGuard

**Automatic PII de-identification for NHS clinical notes — clean data in, no identifiers out.**

NoteGuard discovers, inspects, removes and de-identifies PII in free-text NHS clinical notes **before**
the data is shared or used to train a model. It runs **at the point of use** ("sanitise at source"), so
data is cleaned inside its own governance boundary first — the privacy-preserving on-ramp in front of an
NHS Secure Data Environment (SDE) / the Federated Data Platform.

It ships as a small, friendly web app anyone can try: **upload your own text and get de-identified data
back**, or **pick a clinical domain and download a de-identified dataset**. Uploaded data is processed
**in memory only and never stored**.

> Built to evidence the NHS England **Data Scientist (Data Wrangler), Band 7** competencies —
> LLM exploitation/assurance, RAP, data linkage, IG (Caldicott/DPA), data quality, and the National SDE.
> JD-to-feature map: [docs/role_alignment.md](docs/role_alignment.md).

## The app — two tabs anyone can use

A short **"How it works"** walkthrough (Add data → Detect & remove → Review & download) greets you, with
a plain-English note on the optional LLM assurance pass.

1. **De-identify your data** — paste text, or upload a `.txt` / `.csv` / `.pdf` (CSV picks the free-text
   column; multi-row files de-identify as a batch). You see the detected identifiers highlighted, a
   **donut chart** of how many of each type were found, a **table to review every change**, and a
   one-click download. Files are processed **in memory only** — nothing touches disk (asserted by
   [tests/test_privacy.py](tests/test_privacy.py)).
2. **Get data by domain** — choose a clinical domain (diabetes, cardiovascular, respiratory, mental
   health, cancer, renal) and download **de-identified** data from the NHS synthetic notes (primary) or
   a curated catalog of public free-text datasets. Every record passes through the same gate first.

The UI follows the **NHS.UK** look (NHS Blue header, NHS palette, green action buttons). Optional
**LLM assurance** (sidebar) adds a free, OpenAI-compatible model as a recall-oriented safety net whose
hits are always flagged for human review — off unless a key is configured.

## What makes this more than "just Presidio"

Presidio is the detection **engine** — we don't reinvent it. NoteGuard is the **clinical assurance
layer** Presidio leaves to you:

1. **Measured residual leakage.** The dataset keeps PII in structured tables, so we join them back to
   each note for free ground truth and report a real **re-identification risk** number — not a vibe.
2. **Domain adaptation to messy clinical text.** NHS-aware recognisers: checksum-validated NHS numbers
   **plus** context-anchored detection for the dataset's 9-digit synthetic numbers Presidio's `UK_NHS`
   misses, plus GMC/NMC clinician IDs, ODS org codes and record UUIDs.
3. **Patient-consistent de-identification.** Same patient → same surrogate across their whole admission
   journey. Only date-of-birth is treated as PII (shifted by a consistent per-patient offset); visit /
   admission dates are clinically useful and left intact. Realistic en_GB fakes (or `[label]` redaction).
4. **Pluggable + degrades gracefully.** One `Detector` interface (Rule / Presidio / optional LLM); the
   pure-Python rule layer + eval run even if spaCy/Presidio are unavailable, and the model auto-resolves
   `lg → sm → rules` to whatever is installed.
5. **Data-quality report.** Completeness, encoding (mojibake) remediation, NHS-checksum validity and
   ground-truth coverage — the routine checks a data wrangler runs before modelling (`src/quality.py`).
6. **Governance wrapper.** Per-note audit of what was removed + the dataset-level leakage report, mapped
   to the NHS **Five Safes**, **Caldicott Principles**, and **DPA 2018 / UK GDPR**.

## Pipeline

```
your text / a domain cohort
        │
        ▼  ingest in memory (txt/csv/pdf → records, no disk)        src/ingest.py · src/cohorts.py · src/catalog.py
        ▼  fix mojibake                                             src/data.py
        ▼  detect  =  rules  ∪  Presidio NER  (∪ optional LLM)      src/recognisers.py · src/detect.py · src/llm_assure.py
        │            overlap-safe merge; precise rules win
        ▼  transform  =  redact  |  pseudonymise + DOB date-shift   src/transform.py  (patient-consistent Faker vault)
        ▼  review (donut chart + change table)  →  download         streamlit_app.py
```

Offline / RAP tooling over the same package: **leakage + P/R/F1 evaluation** (`src/evaluate.py`, run via
`tests/run_eval.py`), the **data-quality report** (`src/quality.py`), and a **two-Trust sanitise-at-source
demo** (`src/trust_demo.py`: each Trust cleans locally; only de-identified text joins a shared pool).

## Results — residual leakage drops as we layer detection

*Known identifiers (joined from the structured tables) still present after sanitisation. Measured on all
**1,602 notes** (1,027 known-PII occurrences). Reproduce with `python tests/run_eval.py --compare`.*

| Detector | NHS number F1 | PERSON recall | **Residual leakage** |
|---|---|---|---|
| rules only | 0.98 | 0.00 | **74.8 %** |
| **presidio + rules** (shipping) | **0.99** | **0.68** | **8.5 %** |

The rules→engine drop is the headline: it shows, with numbers, exactly what the NER engine buys you.

> Precision is reported against *structured* PII only, so it is a conservative lower bound — correctly
> removing a clinician's name (not in the tables) counts here as a false positive. **Recall and leakage
> are the sound, headline metrics.**

## Project layout (Gold-RAP "analysis as a product")

```
src/
  data.py          load CSVs + ground-truth join (EVAL-ONLY oracle)
  recognisers.py   pure-Python rules: NHS checksum/context, postcode, date, phone, email, GMC/NMC/ODS, UUID
  detect.py        RuleDetector / PresidioDetector / optional LLM compose, behind one Detector interface
  transform.py     redaction | patient-consistent pseudonymisation + DOB date-shift (Faker vault)
  ingest.py        in-memory bytes → records for txt/csv/pdf (no disk writes)
  cohorts.py       derive clinical-domain cohorts from note text (keyword tagging)
  catalog.py       registry of public free-text datasets (de-identified before download)
  llm_assure.py    optional OpenAI-compatible LLM assurance pass (off unless a key is set)
  quality.py       data-quality report (completeness, mojibake, NHS-checksum validity)
  pipeline.py      single-note detect -> sanitise -> audit
  evaluate.py      detection P/R/F1 + residual-leakage metric
  trust_demo.py    two-Trust sanitise-at-source demo
tests/             unit tests incl. test_privacy.py (no-disk-writes) + run_eval.py (eval CLI)
docs/              tool_card.md · report.md (ATRS) · role_alignment.md · DEPLOY_STREAMLIT_CLOUD.md
streamlit_app.py   the web app (Streamlit Cloud entry point)
requirements.txt   Streamlit Cloud deps    pyproject.toml   packaging + lint/test config
.streamlit/config.toml   NHS theme + viewer mode
```

## Trust & governance
- **Safe data** — PII removed to DAPB1523/ICO standard across patient + staff + org identifiers.
- **Safe settings** — processing is local/in-memory; raw CSVs and the re-id vault are gitignored, never leave.
- **Safe outputs** — only de-identified text + content-free audit; the measured leakage gates release.
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
python tests/run_eval.py --compare --limit 300   # reproduce the leakage table + data-quality report
python -m src.trust_demo                          # two-Trust sanitise-at-source demo
pytest -q                                         # unit tests
```

The dataset is pulled from Hugging Face on first run. To run fully offline, drop the three CSVs in a
folder and set `NOTEGUARD_DATA_DIR=/path/to/csvs`.

## Deploy the live demo — Streamlit Community Cloud (free, no card)

Point <https://share.streamlit.io> at this repo with main file `streamlit_app.py`. `requirements.txt`
ships the small spaCy model so it fits the free tier's RAM, and `build_detector` auto-uses whichever
model is installed. To enable the optional LLM assurance pass, add a free key as a secret
(`LLM_ASSURE_API_KEY`). Full steps: [docs/DEPLOY_STREAMLIT_CLOUD.md](docs/DEPLOY_STREAMLIT_CLOUD.md).

## Data notes (found by inspecting the data, not assuming)
- NHS numbers in this synthetic set are **9 digits** (real ones are 10 + mod-11 check). We catch both:
  checksum-validated 10-digit anywhere, **and** context-anchored numbers after an "NHS …" label.
- Some fields are double-encoded (`Â·`); `_fix_mojibake` repairs them so they don't pollute ground truth.

Built with Claude Code (`CLAUDE.md`, `.claude/`).
