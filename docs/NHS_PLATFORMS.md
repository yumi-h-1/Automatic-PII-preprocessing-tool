# Running NoteGuard where the NHS already works

NoteGuard's engine is a plain, pip-installable Python package (`pip install noteguard` from this
repo) with **no service dependencies and no external calls** — detection and transformation run
entirely inside whatever compute you point it at. That is deliberate: "sanitise at source" only
works if the tool can run *inside* a Trust's existing governance boundary, on the platforms NHS
teams already use.

| Where NHS teams work | How NoteGuard runs there | In this repo |
|---|---|---|
| **Microsoft Fabric** (being piloted across NHS analytics) | Notebook over a Lakehouse table: read → de-identify the text column → write the de-identified table back | [`integrations/fabric_deidentify.ipynb`](../integrations/fabric_deidentify.ipynb) |
| **Azure Databricks** (widely used for NHS data engineering) | The same notebook runs unchanged against a Unity Catalog / hive table | [`integrations/fabric_deidentify.ipynb`](../integrations/fabric_deidentify.ipynb) |
| **Palantir Foundry — the Federated Data Platform (FDP)** | A `transforms-python` transform in a Code Repository: raw notes dataset in, de-identified dataset out; downstream consumers never touch the original | [`integrations/foundry_transform.py`](../integrations/foundry_transform.py) |
| **NHS Secure Data Environments / Trust RAP pipelines** | Ordinary Python: `Pipeline(build_detector(), PseudonymVault())` in a scheduled job, plus the evaluation harness for a recurring miss-rate report | `src/pipeline.py` · `src/evaluate.py` · `tests/run_eval.py` |
| **Anyone's browser** (this public demo) | Streamlit app, hosted free — uploads processed in memory only, never stored | `streamlit_app.py` |

## Why the demo is on Streamlit, not Azure

The public demo needs to be free to host and safe to share (no card, no bill, no real data). The
point of the integrations above is that **the demo's hosting is not the product's runtime**: the
same package that powers the Streamlit app drops into Fabric, Databricks, or Foundry with no code
changes to the engine.

## The three properties that make it portable

1. **Pure-Python core, graceful degradation** — the rule layer runs with no spaCy/Presidio at
   all; the detector auto-resolves `en_core_web_lg → sm → rules` to whatever the environment has
   installed, and never triggers a runtime model download.
2. **No I/O inside the engine** — text in, text out. Storage decisions (lakehouse table, Foundry
   dataset, download button) stay with the platform, so information governance reviews the flow,
   not the library.
3. **Measurable in place** — `src/evaluate.py` ships with the package, so any deployment can
   re-measure the miss rate (false negatives) on labelled data *inside* the same environment.
   The demo app's **How safe is it?** tab does exactly this, live.

## Governance notes (all platforms)

- Pseudonymised data is **still personal data** under UK GDPR / DPA 2018 — treat de-identified
  outputs per your IG lead's sign-off; `redaction` mode removes rather than replaces.
- The in-memory pseudonym vault is never persisted by the engine. If a re-identification key is
  required, exporting and safeguarding it is an explicit, governed decision (`PseudonymVault.export`).
- Low-confidence detections are redacted anyway and flagged `needs_review` — a human-in-the-loop
  queue, not silent trust.
