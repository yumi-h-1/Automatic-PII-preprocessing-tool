---
name: run-evaluation
description: How to run the NoteGuard evaluation (detection P/R/F1 + residual leakage) and read it
---
# Running the evaluation

The eval is the project's pass/fail signal — it proves sanitisation actually removes PII, with numbers.

1. Data: either `NOTEGUARD_DATA_DIR=<folder with the 3 CSVs>` (offline) or let it auto-download from HF.
2. Run `python run_eval.py --compare --limit 300` (use a larger `--limit` for the headline; `--method
   pseudonym` to measure leakage under pseudonymisation). Writes `results.json`.
3. It joins each note to its patient/admission record (the EVAL-ONLY oracle) to get ground truth, then
   reports, per detector:
   - **detection P / R / F1** per entity type (precision is a conservative lower bound — removing PII
     that isn't in the tables, e.g. clinician names, counts as a false positive).
   - **residual leakage** = known identifiers still present after sanitisation. This is the headline.

## How to read it
- `--compare` prints two rows: **rules** → **presidio+rules** (the shipping detector). The leakage
  should drop sharply between them.
- Watch residual leakage as the headline. If it regresses after a change to `noteguard/recognizers.py`,
  `detect.py`, or `transform.py`, fix it before continuing.

Log anything that didn't work in `experiments/FAILED.md`.
