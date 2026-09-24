"""Command-line front door. Parses arguments and dispatches to the modules."""

from __future__ import annotations

import argparse
import sys

from meeting_digest import __version__


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="meeting-digest",
        description="Turn recorded meetings into transcripts, screenshots, and notes.",
    )
    parser.add_argument("--version", action="version", version=f"meeting-digest {__version__}")
    parser.add_subparsers(dest="command", metavar="COMMAND")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not args.command:
        parser.print_help()
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
