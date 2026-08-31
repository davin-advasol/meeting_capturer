#!/usr/bin/env python
"""Stop hook: at the end of each turn, run pytest only for the tests whose
implementation file has already been created.

The plan (docs/superpowers/plans/2026-06-15-meeting-capturer-v1.md) builds the
app one module at a time, and a test file exists for each module up front. So
the full suite is red until every task is done. This hook runs a test only once
its subject module exists — tests for not-yet-built modules are skipped, not
failed.

If a run test fails, exit code 2 blocks the turn and feeds the pytest output
back to Claude so work continues until those tests pass. A blocked turn is the
expected state while the created modules' tests are red.
"""
import subprocess
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[2] / "backend"

# test file -> implementation module it requires (paths relative to backend/)
TEST_REQUIRES = {
    "test_config.py": "app/config.py",
    "test_models.py": "app/models.py",
    "test_formatting.py": "app/formatting.py",
    "test_storage.py": "app/storage.py",
    "test_audio.py": "app/audio.py",
    "test_transcription_openai.py": "app/transcription/openai_adapter.py",
    "test_transcription_factory.py": "app/transcription/factory.py",
    "test_llm_factory.py": "app/llm/factory.py",
    "test_notes_generator.py": "app/notes/generator.py",
    "test_notes_renderer.py": "app/notes/renderer.py",
    "test_qa.py": "app/qa/answerer.py",
    "test_pipeline.py": "app/pipeline.py",
    "test_api.py": "app/main.py",
    "test_smoke.py": "app/pipeline.py",
}


def main() -> int:
    try:
        sys.stdin.read()  # drain the Stop payload; not needed
    except Exception:
        pass

    if not BACKEND.exists():
        return 0

    targets = sorted(
        f"tests/{test_file}"
        for test_file, module in TEST_REQUIRES.items()
        if (BACKEND / module).exists() and (BACKEND / "tests" / test_file).exists()
    )
    if not targets:
        return 0

    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", *targets],
        cwd=BACKEND,
        capture_output=True,
        text=True,
    )
    if proc.returncode == 0:
        return 0

    sys.stderr.write(
        "Backend pytest is RED for created modules — the turn is blocked until it passes.\n"
        "If tracebacks are large or confusing, dispatch the test-triage subagent "
        "to diagnose instead of reading full tracebacks inline.\n"
        "Durable, hard-won test facts are in LESSONS.md.\n\n"
        + proc.stdout
        + proc.stderr
    )
    return 2


if __name__ == "__main__":
    sys.exit(main())
