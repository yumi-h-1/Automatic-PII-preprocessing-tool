"""End-to-end de-identification of a single note: detect -> anonymise -> audit record.

The audit record is the governance artifact (Five Safes "safe outputs"): it reports *what kind* of PII
was found and removed, with counts only — never the raw values.
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from .analyzer import analyze, get_default_analyzer
from .anonymize import MODE_PSEUDONYMISE, Vault, anonymize_text

OUT_DIR = Path(__file__).resolve().parent.parent / "data" / "out"


@dataclass
class ProcessedNote:
    anonymized_text: str
    entities: list[dict] = field(default_factory=list)
    audit: dict = field(default_factory=dict)


def process_note(text: str, mode: str = MODE_PSEUDONYMISE, analyzer=None, vault: Vault | None = None) -> ProcessedNote:
    analyzer = analyzer or get_default_analyzer()
    results = analyze(analyzer, text)
    entities = [
        {"entity_type": r.entity_type, "start": r.start, "end": r.end, "score": round(r.score, 3)}
        for r in sorted(results, key=lambda r: r.start)
    ]
    anonymized = anonymize_text(text, results, mode=mode, vault=vault)
    audit = {
        "policy": mode,
        "total_entities": len(results),
        "entity_counts": dict(Counter(r.entity_type for r in results)),
        "chars_in": len(text),
        "chars_out": len(anonymized),
    }
    return ProcessedNote(anonymized_text=anonymized, entities=entities, audit=audit)


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")  # note text may contain non-ASCII
    except Exception:
        pass
    from .load_data import load_tables

    mode = sys.argv[1] if len(sys.argv) > 1 else MODE_PSEUDONYMISE
    limit = int(sys.argv[2]) if len(sys.argv) > 2 else 5

    notes = load_tables()["notes"]
    texts = notes["clean_note_text"].head(limit).tolist()

    analyzer = get_default_analyzer()
    vault = Vault()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUT_DIR / "deidentified_sample.jsonl"
    with out_path.open("w", encoding="utf-8") as fh:
        for i, text in enumerate(texts):
            processed = process_note(text, mode=mode, analyzer=analyzer, vault=vault)
            fh.write(json.dumps({"anonymized_text": processed.anonymized_text, "audit": processed.audit}) + "\n")
            if i == 0:
                print("=== RAW (first note) ===\n" + text[:600])
                print("\n=== DE-IDENTIFIED ===\n" + processed.anonymized_text[:600])
                print("\n=== AUDIT ===\n" + json.dumps(processed.audit, indent=2))
    print(f"\nWrote {len(texts)} de-identified notes -> {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
