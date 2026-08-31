# NoteGuard — NHS Clinical-Note PII Sanitisation

Sanitise-at-source: detect + de-identify PII in free-text NHS clinical notes so only de-identified
data leaves a Trust. Ships a public three-tab demo — (1) upload a note/CSV/PDF and get de-identified
data back, processed in memory only; (2) pick a clinical domain and download de-identified data from
NHS + public sources; (3) "How safe is it?" — lay-reader false-negative (miss-rate) evidence + a live
re-check — plus measured residual leakage and Five Safes / Caldicott / DPA governance.

## Commands
```bash
# Setup (Windows PowerShell)
python -m venv .venv; .\.venv\Scripts\Activate.ps1
pip install -e ".[app,dev]"; python -m spacy download en_core_web_lg

python tests/run_eval.py --compare              # VERIFIABLE SIGNAL: rules vs presidio+rules (ALL notes) -> outputs/results.json
python tests/run_eval.py --compare --snapshot    # …plus refresh assets/metrics_snapshot.json (committed; read by the app)
# --limit N samples N notes for a quick run; the published snapshot + README table must quote a full run.
python -m src.trust_demo                          # two NHS Trusts share only de-identified data -> outputs/
streamlit run streamlit_app.py                    # demo (De-identify / Get-by-domain / How-safe-is-it)
python -m pytest tests/ -v

# Offline data: set NOTEGUARD_DATA_DIR to a folder holding the 3 CSVs (else auto-downloaded from HF).
# Optional LLM assurance pass: set LLM_ASSURE_API_KEY (free Groq/Gemini/HF key); off + inert otherwise.
#   LLM_ASSURE_BASE_URL / LLM_ASSURE_MODEL override the OpenAI-compatible endpoint (default: Groq Llama-3.x).
```

## Architecture
- `src/` — `data` (load + ground-truth join, EVAL-ONLY oracle) · `recognisers` (pure-Python
  rules) · `detect` (Rule / Presidio / optional LLM compose, graceful fallback) · `transform`
  (redact | patient-consistent pseudonymise + date-shift, Faker) · `evaluate` (P/R/F1 + residual
  leakage) · `quality` (data-quality report) · `ingest` (in-memory bytes→records, no disk) ·
  `cohorts` (clinical-domain keyword tagging) · `catalog` (public dataset registry) ·
  `llm_assure` (optional OpenAI-compatible LLM assurance) · `pipeline` · `trust_demo`.
- `tests/run_eval.py` CLI · `streamlit_app.py` demo (3 tabs: De-identify · Get-by-domain ·
  How-safe-is-it) · `tests/` mirror `src/`. Packaged via `pyproject.toml`.
- `assets/metrics_snapshot.json` — published eval aggregates (NO note text; safe to commit). The
  safety tab reads it; refresh with `run_eval.py --compare --snapshot` after detection changes.
- `integrations/` — illustrative platform code, NOT part of the package or tests: Fabric/Databricks
  notebook + Palantir Foundry (FDP) transform (`spark` is platform-injected; lint-relaxed via
  per-file-ignores in `pyproject.toml`). Platform story: `docs/NHS_PLATFORMS.md`.
- LLM assurance is OFF unless `LLM_ASSURE_API_KEY` is set; never trusted blindly (spans flagged
  `needs_review`). Tab 1 processes uploads in memory only — `tests/test_privacy.py` asserts no disk writes.

## Code style
- Python 3.10+, type hints on function signatures. The pure-Python rule layer must stay importable
  WITHOUT spaCy/Presidio (the fallback path). snake_case / PascalCase.

## Data rules (treat the synthetic notes as if real NHS PHI)
- `data/raw/`, `outputs/`, and any vault export are gitignored — never commit. Never paste note text
  into prompts; point at file paths.
- The note→patient join (`src/data.py` ground truth) is the EVAL-ONLY oracle. It must NEVER feed
  detection/transform — that is data leakage and invalidates the metric.
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
- **Places recall** — low recall (0–0.7) was mostly generic "ward"/"bay" in GT (now filtered by
  `_GENERIC`); NHS site names are caught by the `_SITE_RE` LOCATION rule in recognisers.
- **Three-tab public demo** — Tab 1 (De-identify) ingests uploads (txt/csv/pdf) **in memory only**
  (`src/ingest.py`, no disk writes); Tab 2 (Get-by-domain) serves de-identified cohorts from NHS notes
  (primary) + a public catalog. Both reuse `Pipeline` + one shared `PseudonymVault` per batch.
- **Tab 3 leads with false negatives, for lay readers** — the headline metric is the miss rate
  (known identifiers still visible after sanitisation = residual leakage), NOT accuracy/F1. It shows
  the committed snapshot, per-type caught/missed, honest caveats, and a live re-check
  (`src/evaluate.py` on `load_notes`, deterministic engine, no LLM) so a constrained deploy
  (sm model) measures itself instead of quoting the lg snapshot. The owner explicitly does NOT
  want a rules-only vs full-engine comparison chart in this tab (removed 2026-07-13).
- **Demo hosting ≠ product runtime** — the public demo stays on free Streamlit Cloud; NHS-platform
  familiarity is shown via `integrations/` (Fabric/Databricks notebook, Foundry/FDP transform) and
  the "Built to run where NHS teams already work" strip in the app. No paid Azure hosting.
- **Domain cohorts are keyword tagging, NOT validated phenotypes** — `src/cohorts.py` derives domains
  (diabetes/cardiovascular/…) by clinical-concept substring matching because the NHSE set has no
  condition field. High-recall, stated honestly in the UI. Same matcher filters external catalog rows.
- **External datasets labelled by provenance** — `src/catalog.py` entries carry honest origin/licence
  labels (NHS-synthetic vs US case-report); credential-gated/tabular sets (Kaggle) are link-only.
- **LLM assurance is additive, off-by-default, human-reviewed** — `src/llm_assure.py` runs only when a
  free key is set, composed via `ComposedDetector` in `detect.py`; its hits are `needs_review=True` and
  its failures are swallowed so the deterministic path can never break. In the UI this is labelled
  **"AI double-check"** (owner finds "LLM assurance pass" opaque) and the sidebar shows the actual
  model + endpoint host (`LLMAssurance().model` / `.base_url`).
- **Tab 2 has no sample-size controls** — the owner wants the full dataset by default: the whole NHSE
  set is scanned (`load_notes()` cached via `load_all_notes`) and the full matching cohort de-identified.
  External catalog sets stream a fixed `EXTERNAL_FETCH_ROWS` cap (UI states it) since they can't be
  fetched whole.

## Gotchas
- Note text has mojibake (`Â·`) — `_fix_mojibake` runs before detection.
- Synthetic NHS numbers are 9 digits (no valid mod-11) — caught via the "NHS …" context anchor.
- Default spaCy model is `en_core_web_lg`; override via the `spacy_model` arg or the
  `PII_SPACY_MODEL` env var. `build_detector` only loads a model that's actually **installed**
  (`spacy.util.is_package`) — it never lets Presidio trigger a 560MB runtime download of a missing
  model — and degrades `lg → sm → rules`. The free Streamlit Cloud deploy ships only `sm`.
- `[app]` extra now also pulls `pypdf` (PDF ingest), `requests` (LLM), `datasets` (external catalog).
  spaCy/Presidio/streamlit/datasets are heavy — the rule layer + new pure-Python modules import without them.
- `requirements.txt` exists **only** for Streamlit Community Cloud (pins the `sm` model wheel); local/
  packaged installs use `pyproject.toml`. Keep the two dep lists roughly in sync.

## Working with Claude
- After editing `src/recognisers.py` / `detect.py` / `transform.py`, run
  `python tests/run_eval.py --compare` and check residual leakage didn't regress.
- After touching `src/ingest.py` or the de-id path, run `tests/test_privacy.py` — it asserts
  de-identification writes **no files to disk** (the demo's "your data is never stored" guarantee).
