"""PostToolUse hook: re-run the de-identification tests after edits to the scrubbing logic.

Wired in `.claude/settings.json`. The team guide's lesson is "verify everything" — recognizers and
anonymisation operators are exactly where a silent regression would let PII leak, so we re-check them
on every edit.

Safe by design:
- Only acts on edits to `src/recognizers/` or `src/anonymize.py`; otherwise exits 0 silently.
- Gated behind the `PII_ENABLE_HOOK=1` env var so it never disrupts an unrelated session or a
  half-installed environment. Turn it on once the venv + tests exist.
- Exits 0 (never blocks) if the venv or pytest is missing.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
WATCHED = ("src/recognizers", "src/anonymize.py")


def main() -> int:
    if os.environ.get("PII_ENABLE_HOOK") != "1":
        return 0
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0

    file_path = (payload.get("tool_input") or {}).get("file_path", "")
    rel = file_path.replace("\\", "/")
    if not any(w in rel for w in WATCHED):
        return 0

    venv_python = REPO / ".venv" / "Scripts" / "python.exe"
    python = str(venv_python) if venv_python.exists() else sys.executable
    test_file = REPO / "tests" / "test_leakage.py"
    if not test_file.exists():
        return 0

    result = subprocess.run(
        [python, "-m", "pytest", str(test_file), "-q"],
        cwd=str(REPO),
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        # Surface failures to Claude via stderr; exit 2 asks the model to address them.
        sys.stderr.write("Leakage tests FAILED after edit — PII may be leaking:\n")
        sys.stderr.write(result.stdout[-2000:] + "\n" + result.stderr[-1000:])
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
