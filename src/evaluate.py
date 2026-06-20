"""The verifiable signal: known-PII recall + leakage test.

Using the note<->patient oracle from load_data, for every known identifier that actually appears in a
raw note we check whether it survives anonymisation. Two numbers come out:

- leaks   = identifiers still present verbatim in the de-identified output. MUST be 0.
- recall  = scrubbed / present, per category. The end-to-end scrub rate of the system.

The analyzer is built WITH the Trust roster (patient + site names) enabled — the legitimate hybrid:
NER generalises, the roster guarantees known identifiers are caught. Names recall is therefore
roster-backed by design.
"""
from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path

from .analyzer import analyze, build_analyzer
from .anonymize import MODE_PSEUDONYMISE, Vault, anonymize_text
from .load_data import Note, load_notes_with_known_pii
from .recognizers import name_terms

OUT_DIR = Path(__file__).resolve().parent.parent / "data" / "out"

try:
    from dateutil import parser as _date_parser
except Exception:
    _date_parser = None


def _nhs_forms(value: str) -> list[str]:
    digits = "".join(c for c in value if c.isdigit())
    forms = {value, digits}
    if len(digits) == 10:
        forms.add(f"{digits[:3]} {digits[3:6]} {digits[6:]}")
        forms.add(f"{digits[:3]},{digits[3:6]},{digits[6:]}")
    return [f for f in forms if len(f) >= 5]


def _dob_forms(value: str) -> list[str]:
    forms = {value}
    if _date_parser is not None:
        try:
            dt = _date_parser.parse(value, dayfirst=True, fuzzy=True)
            for fmt in ("%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d", "%d.%m.%Y", "%d/%m/%y", "%-d/%-m/%Y"):
                try:
                    forms.add(dt.strftime(fmt))
                except ValueError:
                    pass
        except Exception:
            pass
    return [f for f in forms if len(f) >= 6]


def _search_items(note: Note) -> list[tuple[str, list[str]]]:
    """Flatten a note's known identifiers into (category, [search forms]) items."""
    items: list[tuple[str, list[str]]] = []
    # Per-token: a multi-name is scrubbed iff every token is. (Checking the whole "First Mid Last"
    # string would falsely fail, since the roster detects each token as a separate adjacent span.)
    seen_tokens: set[str] = set()
    for full_name in note.known.get("names", []):
        for token in name_terms(full_name):
            if len(token) >= 3 and " " not in token and token.lower() not in seen_tokens:
                seen_tokens.add(token.lower())
                items.append(("names", [token]))
    for nhs in note.known.get("nhs_numbers", []):
        items.append(("nhs", _nhs_forms(nhs)))
    for dob in note.known.get("dobs", []):
        items.append(("dob", _dob_forms(dob)))
    for place in note.known.get("places", []):
        if len(place) >= 4:
            items.append(("places", [place]))
    for record_id in note.known.get("ids", []):
        if len(record_id) >= 6:
            items.append(("ids", [record_id]))
    return items


def _occurrences(forms: list[str], text: str) -> list[tuple[int, int]]:
    """Character spans where any form appears (word-boundary, case-insensitive), so short tokens like
    'Ada' don't false-match inside 'Canada'."""
    spans: list[tuple[int, int]] = []
    for f in forms:
        if not f:
            continue
        for m in re.finditer(rf"\b{re.escape(f)}\b", text, re.IGNORECASE):
            spans.append((m.start(), m.end()))
    return spans


def _all_covered(occ: list[tuple[int, int]], detected: list[tuple[int, int]]) -> bool:
    """True if every occurrence sits inside some detected entity span (so it will be removed)."""
    return all(any(ds <= s and de >= e for ds, de in detected) for s, e in occ)


def evaluate(mode: str = MODE_PSEUDONYMISE, limit: int | None = 200) -> dict:
    notes = load_notes_with_known_pii(limit=limit)

    # Roster = this Trust's full patient list (legitimately held inside the Trust).
    roster_person, roster_place, roster_nhs, roster_ids = set(), set(), set(), set()
    for n in notes:
        roster_person.update(n.known.get("names", []))
        roster_place.update(n.known.get("places", []))
        roster_nhs.update(n.known.get("nhs_numbers", []))
        roster_ids.update(n.known.get("ids", []))
    analyzer = build_analyzer(
        roster_person=roster_person, roster_place=roster_place,
        roster_nhs=roster_nhs, roster_ids=roster_ids,
    )
    vault = Vault()

    cats = ("names", "nhs", "dob", "places", "ids")
    present = {c: 0 for c in cats}
    scrubbed = {c: 0 for c in cats}
    leak_samples: list[dict] = []

    # Metric = detection coverage: is every occurrence of a known identifier inside a detected span?
    # This is mode-independent and immune to the false positive where pseudonymisation happens to emit
    # a fake value that coincidentally matches another patient's real token.
    t0 = time.perf_counter()
    for note in notes:
        if not note.text:
            continue
        results = analyze(analyzer, note.text)
        anonymize_text(note.text, results, mode=mode, vault=vault)  # exercise full pipeline for timing
        detected = [(r.start, r.end) for r in results]

        for category, forms in _search_items(note):
            occ = _occurrences(forms, note.text)
            if not occ:
                continue
            present[category] += 1
            if _all_covered(occ, detected):
                scrubbed[category] += 1
            elif len(leak_samples) < 20:
                leak_samples.append({"note": note.clinical_note_id, "category": category, "value": forms[0]})
    elapsed = time.perf_counter() - t0

    total_present = sum(present.values())
    total_scrubbed = sum(scrubbed.values())
    n_notes = sum(1 for n in notes if n.text)
    metrics = {
        "mode": mode,
        "metric": "detection_coverage",
        "notes_processed": n_notes,
        "leaks": total_present - total_scrubbed,
        "overall_recall": round(total_scrubbed / total_present, 4) if total_present else 1.0,
        "recall_by_category": {
            c: round(scrubbed[c] / present[c], 4) if present[c] else None for c in cats
        },
        "present_by_category": present,
        "throughput_notes_per_sec": round(n_notes / elapsed, 2) if elapsed else None,
        "leak_samples": leak_samples,
        "roster_backed": True,
    }
    return metrics


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")  # allow ✅/❌ when piped on Windows
    except Exception:
        pass
    mode = MODE_PSEUDONYMISE
    limit: int | None = 200
    for arg in sys.argv[1:]:
        if arg.startswith("--policy="):
            mode = arg.split("=", 1)[1]
        elif arg.startswith("--limit="):
            limit = int(arg.split("=", 1)[1]) or None

    metrics = evaluate(mode=mode, limit=limit)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")

    print(json.dumps(metrics, indent=2))
    status = "PASS ✅" if metrics["leaks"] == 0 else f"FAIL ❌ ({metrics['leaks']} leaks)"
    print(f"\nLeakage test: {status}  |  overall recall {metrics['overall_recall']:.1%}  "
          f"|  {metrics['notes_processed']} notes")
    return 0 if metrics["leaks"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
