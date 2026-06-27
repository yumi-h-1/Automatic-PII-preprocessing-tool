"""In-memory ingestion of user uploads — bytes in, records out, nothing touches disk.

This backs Tab 1 ("de-identify your data") and is the technical basis for the
"your data is never stored" guarantee: every reader works on the uploaded *bytes*
via in-memory buffers (``io.BytesIO`` / ``io.StringIO``). No temp files are written,
so there is nothing on disk to leak or forget to delete. ``tests/test_privacy.py``
asserts this.
"""
from __future__ import annotations

import io
from dataclasses import dataclass

import pandas as pd

from .data import _fix_mojibake

TXT = (".txt", ".text", ".md")
CSV = (".csv",)
PDF = (".pdf",)
SUPPORTED = TXT + CSV + PDF


@dataclass
class IngestRecord:
    record_id: str
    text: str


def _ext(filename: str) -> str:
    name = (filename or "").lower()
    dot = name.rfind(".")
    return name[dot:] if dot != -1 else ""


def read_txt(data: bytes) -> str:
    for enc in ("utf-8", "latin-1"):
        try:
            return _fix_mojibake(data.decode(enc))
        except UnicodeDecodeError:
            continue
    return _fix_mojibake(data.decode("utf-8", errors="replace"))


def csv_columns(data: bytes) -> list[str]:
    """Column names of an uploaded CSV (for the free-text column picker)."""
    df = pd.read_csv(io.BytesIO(data), dtype=str, nrows=0)
    return list(df.columns)


def read_pdf(data: bytes) -> str:
    """Extract text from a PDF in memory. Requires pypdf (optional dependency)."""
    try:
        from pypdf import PdfReader
    except ImportError as e:  # pragma: no cover - environment dependent
        raise RuntimeError("PDF support needs `pypdf` (pip install pypdf).") from e
    reader = PdfReader(io.BytesIO(data))
    pages = [page.extract_text() or "" for page in reader.pages]
    return _fix_mojibake("\n".join(pages))


def records_from_upload(
    filename: str, data: bytes, text_column: str | None = None
) -> list[IngestRecord]:
    """Turn an uploaded file's bytes into de-identifiable records, fully in memory.

    .txt/.pdf  -> a single record holding the document text.
    .csv       -> one record per row, taking text_column (defaults to the first
                  column whose name looks like free text, else the first column).
    """
    ext = _ext(filename)
    if ext in TXT:
        return [IngestRecord(record_id=filename or "upload.txt", text=read_txt(data))]
    if ext in PDF:
        return [IngestRecord(record_id=filename or "upload.pdf", text=read_pdf(data))]
    if ext in CSV:
        df = pd.read_csv(io.BytesIO(data), dtype=str, keep_default_na=False)
        col = text_column or _guess_text_column(df)
        if col not in df.columns:
            raise ValueError(f"Column {col!r} not in CSV columns {list(df.columns)}.")
        out: list[IngestRecord] = []
        for i, val in enumerate(df[col].tolist()):
            text = _fix_mojibake(str(val))
            if text.strip():
                out.append(IngestRecord(record_id=f"row_{i + 1}", text=text))
        return out
    raise ValueError(f"Unsupported file type {ext!r}. Supported: {', '.join(SUPPORTED)}.")


_TEXT_COL_HINTS = ("note", "text", "clinical", "narrative", "comment", "summary", "body")


def _guess_text_column(df: pd.DataFrame) -> str:
    for c in df.columns:
        if any(h in c.lower() for h in _TEXT_COL_HINTS):
            return c
    return df.columns[0] if len(df.columns) else ""
