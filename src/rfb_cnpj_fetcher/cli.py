"""Standalone command-line interface for rfb-cnpj-fetcher."""

import sys

from .plugin import app


def main(argv: list[str] | None = None) -> None:
    """Execute the command-line interface logic.

    Args:
        argv (list[str] | None, optional): Optional list of arguments to override
            sys.argv. Defaults to None.
    """
    if argv is not None:
        sys.argv = [sys.argv[0]] + argv
    try:
        app()
    except KeyboardInterrupt:
        sys.exit(130)
