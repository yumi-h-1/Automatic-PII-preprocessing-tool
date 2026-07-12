"""Run the NoteGuard evaluation over the NHSE synthetic dataset.

    python tests/run_eval.py --limit 300            # quick run
    python tests/run_eval.py --method pseudonym     # leakage under pseudonymisation
    python tests/run_eval.py --compare              # rules-only vs presidio+rules
    python tests/run_eval.py --compare --snapshot   # also refresh assets/metrics_snapshot.json
                                                    # (aggregates only — the app's safety tab reads it)

Writes outputs/results.json and prints a summary.
This is the pipeline's evaluation entry point; it lives under tests/ alongside the unit tests.
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import date
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))  # make the `src` package importable when run as a script

from src.data import load_notes  # noqa: E402
from src.detect import RuleDetector, build_detector  # noqa: E402
from src.evaluate import EvalResult, evaluate  # noqa: E402
from src.quality import data_quality_report, print_quality_report  # noqa: E402
from src.transform import REDACTION  # noqa: E402

OUTPUT_DIR = REPO / "outputs"
logger = logging.getLogger("noteguard.eval")


def _print_summary(res: EvalResult) -> None:
    d = res.to_dict()
    print(f"\n  detector : {d['detector']}")
    print(f"  transform: {d['transform']}   notes: {d['notes_evaluated']}")
    ov = d["detection"]["overall"]
    print(f"  detection  P={ov['precision']:.3f}  R={ov['recall']:.3f}  F1={ov['f1']:.3f}")
    print("  per-entity:")
    for et, m in d["detection"]["per_entity"].items():
        print(f"     {et:<14} P={m['precision']:.3f} R={m['recall']:.3f} "
              f"F1={m['f1']:.3f}  (support={m['support']})")
    lk = d["leakage"]
    print(f"  >> RESIDUAL LEAKAGE: {lk['residual_leaks_after_sanitisation']}"
          f"/{lk['total_known_pii_occurrences']} = {lk['leakage_rate_pct']:.2f}%")


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=300, help="max notes (None=all)")
    ap.add_argument("--method", default=REDACTION, choices=["redaction", "pseudonym"])
    ap.add_argument("--no-presidio", action="store_true", help="rules only")
    ap.add_argument("--compare", action="store_true", help="rules vs presidio+rules")
    ap.add_argument("--out", default=None, help="output JSON path (default: outputs/results.json)")
    ap.add_argument("--snapshot", action="store_true",
                    help="also write assets/metrics_snapshot.json (committed; read by the app)")
    args = ap.parse_args()

    logger.info("loading notes (limit=%s) ...", args.limit)
    records = load_notes(limit=args.limit)
    logger.info("%d notes; %d known PII values joined.",
                len(records), sum(len(r.ground_truth) for r in records))

    print_quality_report(data_quality_report(records))

    runs: dict[str, EvalResult] = {}
    spacy_model: str | None = None
    if args.compare:
        print("\n=== rules-only ===")
        runs["rules"] = evaluate(records, RuleDetector(), args.method)
        _print_summary(runs["rules"])
        print("\n=== presidio+rules (shipping headline detector) ===")
        engine = build_detector(True)
        spacy_model = getattr(engine, "spacy_model", None)
        runs["presidio+rules"] = evaluate(records, engine, args.method)
        _print_summary(runs["presidio+rules"])
    else:
        det = RuleDetector() if args.no_presidio else build_detector(True)
        spacy_model = getattr(det, "spacy_model", None)
        res = evaluate(records, det, args.method)
        _print_summary(res)
        runs[res.detector_name] = res

    # aggregate metrics only — safe to publish (no note text, no identifiers)
    payload = {
        "_meta": {
            "generated": date.today().isoformat(),
            "dataset": "NHSEDataScience/synthetic_clinical_notes",
            "notes_evaluated": max((r.notes for r in runs.values()), default=0),
            "spacy_model": spacy_model,
            "transform": args.method,
        },
        **{n: r.to_dict() for n, r in runs.items()},
    }
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = Path(args.out) if args.out else OUTPUT_DIR / "results.json"
    out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    logger.info("wrote %s", out_path)
    if args.snapshot:
        snap = REPO / "assets" / "metrics_snapshot.json"
        snap.parent.mkdir(parents=True, exist_ok=True)
        snap.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        logger.info("wrote %s (commit this to publish the numbers in the app)", snap)


if __name__ == "__main__":
    main()
