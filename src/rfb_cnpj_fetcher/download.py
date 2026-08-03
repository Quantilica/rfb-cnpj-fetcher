"""Download functions for RFB CNPJ open data."""

from __future__ import annotations

import contextlib
import datetime as dt
from pathlib import Path

from quantilica.core.http import HttpClient, ProgressCallback
from quantilica.core.logging import get_logger

from .catalog import FileEntry
from .storage import DataRepository

logger = get_logger(__name__)

# Generous timeout: RFB ZIP files can be hundreds of MB each
client = HttpClient(timeout=300.0, verify=True)


def _safe_head_date(url: str) -> dt.date | None:
    """Try HEAD request for Last-Modified; silently return None on any error."""
    with contextlib.suppress(Exception):
        return client.head_last_modified_date(url)
    return None


def download_file(
    url: str,
    output: Path,
    *,
    progress: ProgressCallback | None = None,
) -> Path:
    """Download a single ZIP, writing atomically with a SHA-256 manifest.

    Args:
        url: source URL on the RFB portal.
        output: destination path (parent directories created automatically).
        progress: optional callback(downloaded_bytes, total_bytes).

    Returns:
        The path to the written file.
    """
    return client.download_with_manifest(
        url,
        output,
        source_id="rfb-cnpj",
        dataset_id=output.parent.name,
        producer="rfb-cnpj-fetcher",
        progress=progress,
    )


def download_entry(
    entry: FileEntry,
    repo: DataRepository,
    *,
    progress: ProgressCallback | None = None,
) -> Path:
    """Download one FileEntry and return its local path.

    Performs a HEAD request first to determine the Last-Modified date used
    for the stamped filename convention.
    """
    last_modified = _safe_head_date(entry["url"])
    output = repo.path_for_entry(entry, last_modified=last_modified)
    logger.debug("Downloading %s → %s", entry["url"], output)
    return download_file(entry["url"], output, progress=progress)
