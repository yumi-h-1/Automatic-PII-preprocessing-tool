# Automatic PII Preprocessing Tool — NHS De-Identification Gate

De-identifies free-text NHS clinical notes (Microsoft Presidio + spaCy) so only de-identified data
leaves a Trust. Encode Club "Trusted Data & AI Infrastructure" hackathon.

## Commands
```bash
# Setup (Windows PowerShell)
python -m venv .venv; .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt; python -m spacy download en_core_web_sm

python -m src.load_data     # download + ftfy-clean the HF dataset into data/raw/
python -m src.pipeline      # de-identify a sample of notes -> data/out/
python -m src.evaluate      # VERIFIABLE SIGNAL: known-PII recall + leakage test (target 0 leaks)
python -m src.trust_demo    # simulate two NHS Trusts sharing only de-identified data
streamlit run app/streamlit_app.py
python -m pytest tests/ -v
```

## Code style
- Python 3.10+, type hints on function signatures. snake_case / PascalCase. Tests mirror `src/`.

## Data rules (treat the synthetic notes as if they were real NHS PHI)
- `data/raw/`, `data/out/`, and the pseudonymisation vault are gitignored — never commit them.
- Never paste note text into prompts; point at file paths and let tools read locally.
- The note↔patient join in `load_data.py` is the EVAL-ONLY ground-truth oracle. It must NEVER feed the
  detection/anonymisation path — doing so is data leakage and invalidates the metric.
- Never silently fall back to an older/cached dataset — fail loudly.
- `NRP` (nationality/religion/political) is UK-GDPR special-category data: always redact, never pseudonymise.

## Working with Claude
- Ask before non-trivial scope changes. After editing `src/recognizers/` or `src/anonymize.py`, run
  `python -m src.evaluate` and keep leaks at **0**.
- Log dead ends in `experiments/FAILED.md` so they aren't repeated.

## Gotchas
- `clean_note_text` has mojibake — `ftfy.fix_text` runs before detection.
- NHS numbers appear comma-separated (`272,733,208`) — strip non-digits before the Modulus-11 check.
- Names are "Surname, First Middle" — spaCy NER misses some; the roster recognizer backstops known names.
- Default spaCy model is `en_core_web_sm` (fast). Set `PII_SPACY_MODEL=en_core_web_lg` for better recall.
