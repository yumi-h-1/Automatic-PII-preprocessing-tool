# NoteGuard — NHS Clinical-Note PII Sanitisation

Sanitise-at-source: detect + de-identify PII in free-text NHS clinical notes so only de-identified
data leaves a Trust. A clinical-text de-identification pipeline in a Streamlit app — rule-based
detection, Presidio NER, and patient-consistent pseudonymisation. Two tabs: (1) upload/paste a
note/CSV/PDF and get de-identified data back, processed in memory only; (2) pick a clinical domain and
download a de-identified cohort from the NHSE synthetic notes.

The tool ships **no evaluation code and no metrics UI** — measured performance lives only in the
README (see "Measured performance"). Don't re-add an eval harness, a metrics snapshot, a ground-truth
join, or a "how safe is it?" tab without being asked.

## Commands
```bash
# Setup (Windows PowerShell)
python -m venv .venv; .\.venv\Scripts\Activate.ps1
pip install -e ".[app,dev]"; python -m spacy download en_core_web_lg

streamlit run streamlit_app.py                    # demo (De-identify · Get data by domain)
python -m pytest tests/ -v

# Offline data: set NOTEGUARD_DATA_DIR to a folder holding the notes CSV (else auto-downloaded from HF).
```

## Architecture
- `src/` — `data` (load the NHSE notes CSV, free text only) · `recognisers` (pure-Python rules +
  the entity vocabulary) · `detect` (Rule / Presidio, graceful fallback) · `transform` (redact |
  patient-consistent pseudonymise + date-shift, Faker) · `ingest` (in-memory bytes→records, no disk) ·
  `cohorts` (clinical-domain keyword tagging) · `pipeline`.
- `streamlit_app.py` demo (2 tabs: De-identify · Get-by-domain) · `tests/` mirror `src/`.
  Packaged via `pyproject.toml`.
- Detection is deterministic and local — no external model, no API key, no network call carrying note
  text. Tab 1 processes uploads in memory only — `tests/test_privacy.py` asserts no disk writes.

## Code style
- Python 3.10+, type hints on function signatures. The pure-Python rule layer must stay importable
  WITHOUT spaCy/Presidio/pandas (the fallback path). snake_case / PascalCase.

## Data rules (treat the synthetic notes as if real NHS PHI)
- Data source is the HF `NHSEDataScience/synthetic_clinical_notes` set **only**; anything else enters
  through the upload tab. Only the notes CSV is read — the patient/admission tables (which hold the
  identifiers) must never be loaded into the tool.
- `data/raw/`, `outputs/`, and any vault export are gitignored — never commit. Never paste note text
  into prompts; point at file paths.
- Never silently fall back to an older/cached dataset — fail loudly.

## Decisions locked in (version 1 branch)
- **Default model: `en_core_web_lg`** — 100% name recall vs 91% for sm; clinical transformer
  (`obi/deid_roberta_i2b2`) was tested and performed worse on UK names (US i2b2 training data).
- **ORGANIZATION excluded from PresidioDetector.KEEP** — spaCy lg over-tags labels/abbreviations
  ("NHS", "DOB …", "GMC") as ORG, causing false positives and swallowing precise rule spans. NHS
  site names are caught by the `_SITE_RE` LOCATION rule (incl. "… Trust") instead.
- **`_merge` is overlap-safe + priority-ranked** — output spans are disjoint (no transform
  corruption); on overlap, precise rule entities (date/NHS/GMC/…) beat broad NER spans.
- **Human-in-the-loop review queue** — spans with score in `[review_threshold, score_threshold)`
  are redacted but flagged `needs_review=True` for IG analyst review before SDE pool admission.
- **Over-redaction is the accepted failure mode** — precision costs utility, recall costs privacy,
  and those aren't symmetric.
- **Two-tab public demo** — Tab 1 (De-identify) ingests uploads (txt/csv/pdf) **in memory only**
  (`src/ingest.py`, no disk writes); Tab 2 (Get-by-domain) serves de-identified cohorts from the NHSE
  notes. Both reuse `Pipeline` + one shared `PseudonymVault` per batch.
- **Scope was deliberately narrowed (2026-09-05)** — the evaluation harness (`evaluate.py`,
  `quality.py`, `run_eval.py`, `assets/metrics_snapshot.json`, the "How safe is it?" tab, the
  ground-truth join in `data.py`), the federated / cross-Trust demo (`trust_demo.py`), the external
  dataset catalog (`catalog.py`), the platform integrations (`integrations/`, Fabric + Foundry/FDP)
  and the ATRS docs (`docs/report.md`, `docs/tool_card.md`, `docs/NHS_PLATFORMS.md`) were all removed
  so the repo is one thing: a de-identification pipeline in a Streamlit app. Recoverable from git
  history at `09343db` if ever needed. The LLM assurance pass went the same way (see below).
- **Demo hosting** — the public demo stays on free Streamlit Cloud. No paid hosting.
- **Domain cohorts are keyword tagging, NOT validated phenotypes** — `src/cohorts.py` derives domains
  (diabetes/cardiovascular/…) by clinical-concept substring matching because the NHSE set has no
  condition field. High-recall, stated honestly in the UI.
- **No LLM in the loop (removed 2026-09-05)** — the optional "AI double-check" assurance pass
  (`src/llm_assure.py`, `ComposedDetector`, the `LLM_ASSURE_*` env vars) is gone: the owner did not
  want the feature. Detection stays deterministic and offline. Don't re-add it without being asked.
- **Tab 2 has no sample-size controls** — the owner wants the full dataset by default: the whole NHSE
  set is scanned (`load_notes()` cached via `load_all_notes`) and the full matching cohort de-identified.

## Gotchas
- Note text has mojibake (`Â·`) — `_fix_mojibake` runs before detection.
- Synthetic NHS numbers are 9 digits (no valid mod-11) — caught via the "NHS …" context anchor.
- Default spaCy model is `en_core_web_lg`; override via the `spacy_model` arg or the
  `PII_SPACY_MODEL` env var. `build_detector` only loads a model that's actually **installed**
  (`spacy.util.is_package`) — it never lets Presidio trigger a 560MB runtime download of a missing
  model — and degrades `lg → sm → rules`. The free Streamlit Cloud deploy ships only `sm`.
- `[app]` extra pulls `pypdf` (PDF ingest). spaCy/Presidio/streamlit are heavy — the rule layer +
  pure-Python modules import without them.
- `requirements.txt` exists **only** for Streamlit Community Cloud (pins the `sm` model wheel); local/
  packaged installs use `pyproject.toml`. Keep the two dep lists roughly in sync.

## Working with Claude
- After touching `src/ingest.py` or the de-id path, run `tests/test_privacy.py` — it asserts
  de-identification writes **no files to disk** (the demo's "your data is never stored" guarantee).
- After editing `src/recognisers.py` / `detect.py` / `transform.py`, run `pytest -q` and spot-check the
  app on a sample note; there is no eval harness to fall back on.
