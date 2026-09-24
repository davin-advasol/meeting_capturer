import subprocess
import sys

import pytest

from meeting_digest import __version__
from meeting_digest.cli import build_parser, main


def test_version_is_a_string():
    assert isinstance(__version__, str)
    assert __version__.count(".") == 2


def test_parser_builds():
    assert build_parser().prog == "meeting-digest"


def test_no_command_prints_help_and_returns_1(capsys):
    assert main([]) == 1
    assert "usage: meeting-digest" in capsys.readouterr().out


def test_version_flag_exits_zero(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["--version"])
    assert exc.value.code == 0
    assert __version__ in capsys.readouterr().out


def test_installed_console_script_runs():
    result = subprocess.run(
        [sys.executable, "-m", "meeting_digest.cli", "--version"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert __version__ in result.stdout
