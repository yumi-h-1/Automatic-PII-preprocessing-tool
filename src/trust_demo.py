"""Simulate two NHS Trusts collaborating without sharing sensitive data.

Each Trust holds its own patients, its own roster, and its own re-identification vault. It de-identifies
its notes LOCALLY and contributes only the de-identified text + a content-free audit manifest to a
shared pool. Raw notes and vaults never leave the Trust. This is the de-identification gate that sits
in front of a federated SDE / FLock.io training round.
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

from .analyzer import analyze, build_analyzer
from .anonymize import MODE_PSEUDONYMISE, Vault, anonymize_text
from .evaluate import _all_covered, _occurrences, _search_items
from .load_data import Note, load_notes_with_known_pii

OUT_DIR = Path(__file__).resolve().parent.parent / "data" / "out"
TRUST_NAMES = {0: "Trust A (Northgate NHS Foundation Trust)", 1: "Trust B (Riverside NHS Trust)"}


def _assign_trust(person_id: str) -> int:
    return (hash(person_id) & 1) if person_id else 0


def _run_trust(trust_id: int, notes: list[Note], mode: str) -> dict:
    """De-identify one Trust's notes locally; return a shareable manifest + de-identified records."""
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
    vault = Vault()  # this Trust's local re-identification key — never shared

    entity_counts: Counter = Counter()
    deidentified: list[dict] = []
    present = scrubbed = 0
    for note in notes:
        if not note.text:
            continue
        results = analyze(analyzer, note.text)
        clean = anonymize_text(note.text, results, mode=mode, vault=vault)
        entity_counts.update(r.entity_type for r in results)
        deidentified.append({"clinical_note_id": note.clinical_note_id, "anonymized_text": clean})

        detected = [(r.start, r.end) for r in results]
        for _, forms in _search_items(note):
            occ = _occurrences(forms, note.text)
            if occ:
                present += 1
                if _all_covered(occ, detected):
                    scrubbed += 1

    manifest = {
        "trust": TRUST_NAMES[trust_id],
        "patients": len({n.person_id for n in notes}),
        "notes_deidentified": len(deidentified),
        "raw_records_shared": 0,
        "entity_counts": dict(entity_counts),
        "leaks": present - scrubbed,
        "policy": mode,
    }
    return {"manifest": manifest, "deidentified": deidentified}


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")  # allow ✅/❌ when piped on Windows
    except Exception:
        pass
    mode = sys.argv[1] if len(sys.argv) > 1 else MODE_PSEUDONYMISE
    limit = int(sys.argv[2]) if len(sys.argv) > 2 else 300

    all_notes = load_notes_with_known_pii(limit=limit)
    split: dict[int, list[Note]] = {0: [], 1: []}
    for note in all_notes:
        split[_assign_trust(note.person_id)].append(note)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    shared_pool: list[dict] = []
    manifests = []
    for trust_id, notes in split.items():
        result = _run_trust(trust_id, notes, mode)
        manifests.append(result["manifest"])
        trust_dir = OUT_DIR / f"trust_{trust_id}"
        trust_dir.mkdir(exist_ok=True)
        (trust_dir / "manifest.json").write_text(json.dumps(result["manifest"], indent=2), encoding="utf-8")
        with (trust_dir / "deidentified.jsonl").open("w", encoding="utf-8") as fh:
            for rec in result["deidentified"]:
                fh.write(json.dumps(rec) + "\n")
        shared_pool.extend(result["deidentified"])

    with (OUT_DIR / "shared_pool.jsonl").open("w", encoding="utf-8") as fh:
        for rec in shared_pool:
            fh.write(json.dumps(rec) + "\n")

    total_leaks = sum(m["leaks"] for m in manifests)
    summary = {
        "trusts": manifests,
        "shared_pool_size": len(shared_pool),
        "raw_records_shared": 0,
        "total_leaks": total_leaks,
    }
    (OUT_DIR / "trust_demo_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print(json.dumps(summary, indent=2))
    for m in manifests:
        print(f"  {m['trust']}: {m['notes_deidentified']} notes de-identified, "
              f"{m['raw_records_shared']} raw shared, {m['leaks']} leaks")
    print(f"\nShared pool: {len(shared_pool)} de-identified notes | raw records shared: 0 | "
          f"total leaks: {total_leaks} {'✅' if total_leaks == 0 else '❌'}")
    return 0 if total_leaks == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
