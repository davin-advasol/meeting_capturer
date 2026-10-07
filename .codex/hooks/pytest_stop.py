#!/usr/bin/env python
"""Stop hook: at the end of each turn, run the pytest suite from the repo root.

If it fails, exit code 2 blocks the turn and feeds the pytest output back to
the agent so work continues until the suite passes.
"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def main() -> int:
    try:
        sys.stdin.read()  # drain the Stop payload; not needed
    except Exception:
        pass

    if not (ROOT / "tests").exists():
        return 0

    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "-q"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    if proc.returncode == 0:
        return 0

    sys.stderr.write(
        "pytest is RED — the turn is blocked until it passes.\n"
        "If tracebacks are large or confusing, dispatch the test-triage subagent "
        "to diagnose instead of reading full tracebacks inline.\n"
        "Durable, hard-won test facts are in LESSONS.md.\n\n"
        + proc.stdout
        + proc.stderr
    )
    return 2


if __name__ == "__main__":
    sys.exit(main())
