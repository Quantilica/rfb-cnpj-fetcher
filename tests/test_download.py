"""Tests for rfb_cnpj_fetcher.download."""

from __future__ import annotations

import datetime as dt
from pathlib import Path
from unittest.mock import patch

from rfb_cnpj_fetcher.catalog import FileEntry
from rfb_cnpj_fetcher.download import download_entry
from rfb_cnpj_fetcher.storage import DataRepository


def _make_entry(
    filename: str = "Simples.zip",
    group: str = "simples",
    competencia: str = "2025-07",
) -> FileEntry:
    return FileEntry(
        group=group,
        filename=filename,
        url=f"https://dadosabertos.rfb.gov.br/CNPJ/dados_abertos_cnpj/{competencia}/{filename}",
        competencia=competencia,
    )


def test_download_entry_calls_download_file(tmp_path: Path) -> None:
    """download_entry calls download_file with correct arguments."""
    entry = _make_entry()
    repo = DataRepository(tmp_path)

    with (
        patch("rfb_cnpj_fetcher.download._safe_head_date", return_value=None),
        patch("rfb_cnpj_fetcher.download.download_file") as mock_dl,
    ):
        mock_dl.return_value = tmp_path / "Simples@unknown.zip"
        download_entry(entry, repo)

    mock_dl.assert_called_once()
    call_args = mock_dl.call_args
    assert call_args.args[0] == entry["url"]


def test_download_entry_uses_head_date(tmp_path: Path) -> None:
    """download_entry passes Last-Modified date to repo.path_for_entry."""
    entry = _make_entry()
    repo = DataRepository(tmp_path)
    today = dt.date(2025, 7, 10)

    with (
        patch("rfb_cnpj_fetcher.download._safe_head_date", return_value=today),
        patch("rfb_cnpj_fetcher.download.download_file") as mock_dl,
    ):
        mock_dl.return_value = tmp_path / "Simples@20250710.zip"
        download_entry(entry, repo)

    # The output path passed to download_file should contain the date stamp
    output_path: Path = mock_dl.call_args.args[1]
    assert "20250710" in output_path.name


def test_safe_head_date_returns_none_on_error() -> None:
    """_safe_head_date returns None when the HEAD request fails."""
    from rfb_cnpj_fetcher.download import _safe_head_date

    with patch(
        "rfb_cnpj_fetcher.download.client.head_last_modified_date",
        side_effect=Exception("timeout"),
    ):
        result = _safe_head_date("https://example.com/file.zip")

    assert result is None
