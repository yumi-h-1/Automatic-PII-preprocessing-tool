# NoteGuard ↔ NHS England — Data Scientist (Data Wrangler), Band 7

How this project evidences the JD's essential skills and the team's actual project areas
(Data Science & Applied AI Team / National Secure Data Environment). Use this as a portfolio map.

## Project areas in the JD → what NoteGuard demonstrates

| JD project / theme | NoteGuard evidence |
|---|---|
| **National Secure Data Environment (SDE)** | The whole tool is an **SDE on-ramp**: a leakage-gated de-identification layer that lets free-text notes safely enter a shared pool. Governance tab maps it to the Five Safes. |
| **Federated Data Platform — Discharge Summaries (LLMs)** | Free-text clinical-note processing + optional **LLM assurance pass** (`src/llm_assure.py`). Two-Trust demo (`src/trust_demo.py`) models federation: code to data, data never leaves. |
| **Synthetic data (GenAI)** | Patient-consistent **surrogate generation** (Faker vault, `src/transform.py`) produces realistic de-identified text — synthetic stand-ins that keep data useful for training. |
| **Free-text / large-scale survey responses (LLMs)** | The upload tab de-identifies arbitrary free text (txt/csv/pdf) — the same pattern needed to safely analyse free-text survey responses at scale. |

## Essential skills → evidence

| Essential (JD) | Evidence |
|---|---|
| Data security, IG & legislation (**DPA 2018, Caldicott**) | Governance tab: Five Safes + 8 Caldicott Principles + DPA/UK GDPR mapping; pseudonymised-data-is-still-personal-data stated honestly (no over-claim). |
| Professional analytical standards (**AqUA book, Code of Practice for Statistics**) | Honest, conservative metrics (precision as a lower bound), measured residual leakage, openly stated caveats in `src/evaluate.py` and the README. |
| Modern programming languages (**Python**) | Typed Python 3.10+ package; pure-Python rule layer that degrades gracefully without spaCy/Presidio. |

## Wider skills → evidence

| Skill area | Evidence |
|---|---|
| **Reproducible Analytical Pipelines (RAP)** | Packaged `src/` ("analysis as a product"), one `Detector` interface, `tests/run_eval.py` as a reproducible eval CLI, unit tests, CI (`.github/workflows/ci.yml`), Dockerised deploy. |
| **Data engineering / data linkage** | `src/data.py` joins notes↔patients↔admissions for ground truth; `src/cohorts.py` derives clinical-domain cohorts; `src/catalog.py` integrates external public sources — "create new datasets through manipulation of multiple data sources". |
| **Data quality checks & remediation** | `src/quality.py`: completeness, encoding (mojibake) remediation, NHS-number checksum validity, ground-truth coverage — surfaced in the Metrics tab and the eval CLI. |
| **MLOps / model governance / AQA** | Pluggable detectors, leakage as a release gate, human-in-the-loop review queue, per-note audit log, content-free manifests. |
| **LLM exploitation & assurance** | `src/llm_assure.py`: a free OpenAI-compatible LLM as a recall-oriented assurance net whose hits are flagged for human review — never auto-trusted. |
| **Communicating analysis / data visualisation** | Streamlit app communicates detection, sanitisation, metrics and governance to technical and non-technical audiences. |
| **Innovation / open-source** | Built on Microsoft Presidio + spaCy; adds NHS-aware recognisers and a measurable leakage metric Presidio doesn't provide. |

## Honest limitations (the "consider legal and ethical issues" bullet)
- Pseudonymised output is **still personal data** under UK GDPR — the re-identification vault stays Trust-local.
- Domain cohorts (`src/cohorts.py`) are **keyword tagging, not validated phenotypes**.
- The LLM assurance pass is **optional and human-reviewed**, not a source of truth.
- Precision is a **conservative lower bound** (clinician names not in the structured tables count as false positives).
