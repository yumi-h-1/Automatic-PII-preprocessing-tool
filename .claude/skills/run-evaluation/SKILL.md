---
name: run-evaluation
description: How to run the de-identification evaluation (known-PII recall + leakage test) and read it
---
# Running the evaluation

The eval is the project's pass/fail signal — it proves the de-identification gate actually scrubs PII.

1. Ensure the dataset is present: `python -m src.load_data` (writes `data/raw/`).
2. Run `python -m src.evaluate` (optionally `--policy redact|pseudonymise`, `--limit N`).
3. It builds ground truth by joining each note to its patient/admission record (the EVAL-ONLY oracle),
   then for every known identifier present in the raw note checks whether it survives anonymisation.

## How to read the result (`data/out/metrics.json` + console)
- **`leaks` must be 0.** A leak = a patient's real name / NHS number / DOB still present verbatim in the
  de-identified output. Any leak is a hard fail — fix the recognizer or policy before continuing.
- **`recall` per entity type** = fraction of present identifiers that were scrubbed. Higher is better;
  compare against the previous run. Names are the hardest (NER misses "Surname, First" forms) — the
  roster recognizer in `src/recognizers/roster.py` is the backstop.
- **`throughput`** = notes/sec, for the "runs inside a Trust at scale" story.

If `leaks > 0` or recall drops: inspect `src/recognizers/` and the policy map in `src/config.py`,
adjust, re-run. Log anything that didn't work in `experiments/FAILED.md`.
