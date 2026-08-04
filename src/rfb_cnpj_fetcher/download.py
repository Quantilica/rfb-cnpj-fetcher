"""Download functions for RFB CNPJ open data."""

from __future__ import annotations

import contextlib
import datetime as dt
from collections.abc import Mapping
from pathlib import Path

from quantilica.core.http import HttpClient, ProgressCallback
from quantilica.core.logging import get_logger

from .catalog import FileEntry, get_auth_headers
from .storage import DataRepository

logger = get_logger(__name__)

# Generous timeout: RFB ZIP files can be hundreds of MB each
client = HttpClient(timeout=300.0, verify=True)


def _safe_head_date(url: str) -> dt.date | None:
    """Try HEAD request for Last-Modified; silently return None on any error."""
    with contextlib.suppress(Exception):
        headers = get_auth_headers()
        return client.head_last_modified_date(url, headers=headers)
    return None


def download_file(
    url: str,
    output: Path,
    *,
    progress: ProgressCallback | None = None,
    headers: Mapping[str, str] | None = None,
) -> Path:
    """Download a single ZIP, writing atomically with a SHA-256 manifest.

    Args:
        url: source URL on the RFB portal.
        output: destination path (parent directories created automatically).
        progress: optional callback(downloaded_bytes, total_bytes).
        headers: optional HTTP headers (defaults to WebDAV auth headers).

    Returns:
        The path to the written file.
    """
    if headers is None:
        headers = get_auth_headers()
    return client.download_with_manifest(
        url,
        output,
        source_id="rfb-cnpj",
        dataset_id=output.parent.name,
        producer="rfb-cnpj-fetcher",
        progress=progress,
        headers=headers,
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
