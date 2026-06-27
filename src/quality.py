"""Data-quality checks & remediation report.

Band-7 data wrangling means knowing your data *before* you model it. This module
runs the routine quality checks the JD calls for ("carry out routine data quality
checks and remediation") over the loaded notes and reports them as a plain dict —
consumed by the Streamlit Metrics tab and printed by ``tests/run_eval.py``.

It is pure-Python and importable without spaCy/Presidio (same guarantee as the
rule layer): it only reuses ``nhs_number_is_valid`` from ``recognisers``.
"""
from __future__ import annotations

import re
import statistics
from dataclasses import dataclass

from .data import NoteRecord
from .recognisers import nhs_number_is_valid

# residual mojibake markers (post-_fix_mojibake these should be ~0)
_MOJIBAKE_RE = re.compile(r"[ÂÃ�]")
# any 9-10 digit run that looks like an NHS number candidate (grouped or not)
_NHS_CANDIDATE_RE = re.compile(r"\b\d{3}[ ,\-]?\d{3}[ ,\-]?\d{2,4}\b")


@dataclass
class QualityReport:
    notes_total: int = 0
    empty_notes: int = 0
    mojibake_notes: int = 0
    notes_with_ground_truth: int = 0
    mean_chars: float = 0.0
    median_chars: float = 0.0
    nhs_candidates: int = 0
    nhs_checksum_valid: int = 0

    @property
    def empty_rate_pct(self) -> float:
        return 100 * self.empty_notes / self.notes_total if self.notes_total else 0.0

    @property
    def mojibake_rate_pct(self) -> float:
        return 100 * self.mojibake_notes / self.notes_total if self.notes_total else 0.0

    @property
    def gt_coverage_pct(self) -> float:
        return 100 * self.notes_with_ground_truth / self.notes_total if self.notes_total else 0.0

    @property
    def nhs_checksum_pass_pct(self) -> float:
        """% of NHS-number candidates that pass mod-11 — low here is EXPECTED and
        documented: the synthetic set uses 9-digit numbers with no valid checksum,
        which is exactly why detection is context-anchored, not checksum-only."""
        return 100 * self.nhs_checksum_valid / self.nhs_candidates if self.nhs_candidates else 0.0

    def to_dict(self) -> dict:
        return {
            "notes_total": self.notes_total,
            "empty_notes": self.empty_notes,
            "empty_rate_pct": round(self.empty_rate_pct, 2),
            "mojibake_notes": self.mojibake_notes,
            "mojibake_rate_pct": round(self.mojibake_rate_pct, 2),
            "notes_with_ground_truth": self.notes_with_ground_truth,
            "ground_truth_coverage_pct": round(self.gt_coverage_pct, 2),
            "mean_chars": round(self.mean_chars, 1),
            "median_chars": round(self.median_chars, 1),
            "nhs_candidates": self.nhs_candidates,
            "nhs_checksum_valid": self.nhs_checksum_valid,
            "nhs_checksum_pass_pct": round(self.nhs_checksum_pass_pct, 2),
        }


def data_quality_report(records: list[NoteRecord]) -> QualityReport:
    """Routine quality checks over loaded notes (completeness, encoding, key integrity)."""
    rep = QualityReport(notes_total=len(records))
    lengths: list[int] = []
    for r in records:
        text = r.text or ""
        if not text.strip():
            rep.empty_notes += 1
        else:
            lengths.append(len(text))
        if _MOJIBAKE_RE.search(text):
            rep.mojibake_notes += 1
        if r.ground_truth:
            rep.notes_with_ground_truth += 1
        for m in _NHS_CANDIDATE_RE.finditer(text):
            rep.nhs_candidates += 1
            if nhs_number_is_valid(m.group(0)):
                rep.nhs_checksum_valid += 1
    if lengths:
        rep.mean_chars = statistics.mean(lengths)
        rep.median_chars = float(statistics.median(lengths))
    return rep


def print_quality_report(rep: QualityReport) -> None:
    d = rep.to_dict()
    print("\n  data-quality report:")
    print(f"     notes: {d['notes_total']}  empty: {d['empty_notes']} ({d['empty_rate_pct']}%)")
    print(f"     mojibake-affected: {d['mojibake_notes']} ({d['mojibake_rate_pct']}%)")
    print(f"     ground-truth coverage: {d['notes_with_ground_truth']} ({d['ground_truth_coverage_pct']}%)")
    print(f"     note length chars: mean={d['mean_chars']} median={d['median_chars']}")
    print(f"     NHS-number candidates: {d['nhs_candidates']}  "
          f"mod-11 valid: {d['nhs_checksum_valid']} ({d['nhs_checksum_pass_pct']}%)")
