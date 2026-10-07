"""The one exception type the CLI turns into a clean message."""

from __future__ import annotations


class DigestError(Exception):
    """A failure the user can act on.

    Raised for bad input, missing dependencies, and unusable media. The CLI
    prints these as `error: <message>` and exits 2, never as a traceback.
    """
