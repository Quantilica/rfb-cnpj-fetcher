"""Tests for rfb_cnpj_fetcher.catalog — HTTP mocked with `unittest.mock`."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from rfb_cnpj_fetcher.catalog import BASE_URL, list_competencias, list_files

_INDEX_HTML = """\
<html><body>
<a href="2025-07/">2025-07/</a>
<a href="2025-06/">2025-06/</a>
<a href="2024-12/">2024-12/</a>
<a href="../">../</a>
</body></html>
"""

_COMP_HTML = """\
<html><body>
<a href="Empresas0.zip">Empresas0.zip</a>
<a href="Empresas1.zip">Empresas1.zip</a>
<a href="Socios0.zip">Socios0.zip</a>
<a href="Simples.zip">Simples.zip</a>
<a href="Cnaes.zip">Cnaes.zip</a>
<a href="Municipios.zip">Municipios.zip</a>
<a href="../">../</a>
</body></html>
"""


def _mock_response(text: str) -> MagicMock:
    resp = MagicMock()
    resp.text = text
    return resp


def test_list_competencias_sorted_desc():
    """Competências are returned newest-first."""
    with patch(
        "rfb_cnpj_fetcher.catalog._client.get",
        return_value=_mock_response(_INDEX_HTML),
    ):
        comps = list_competencias()
    assert comps == ["2025-07", "2025-06", "2024-12"]


def test_list_competencias_ignores_non_date_links():
    """Parent directory links (../) are not returned."""
    with patch(
        "rfb_cnpj_fetcher.catalog._client.get",
        return_value=_mock_response(_INDEX_HTML),
    ):
        comps = list_competencias()
    assert "../" not in comps
    assert all(len(c) == 7 for c in comps)  # YYYY-MM


def test_list_files_multi_part_group():
    """Multi-part groups (Empresas0, Empresas1) are both discovered."""
    with patch(
        "rfb_cnpj_fetcher.catalog._client.get",
        return_value=_mock_response(_COMP_HTML),
    ):
        entries = list_files("2025-07")
    groups = [e["group"] for e in entries]
    assert groups.count("empresas") == 2


def test_list_files_all_known_groups_present():
    """Every group with a matching filename is returned."""
    with patch(
        "rfb_cnpj_fetcher.catalog._client.get",
        return_value=_mock_response(_COMP_HTML),
    ):
        entries = list_files("2025-07")
    groups = {e["group"] for e in entries}
    assert {"empresas", "socios", "simples", "cnaes", "municipios"} <= groups


def test_list_files_filtered_by_single_group():
    """Filtering by group returns only matching entries."""
    with patch(
        "rfb_cnpj_fetcher.catalog._client.get",
        return_value=_mock_response(_COMP_HTML),
    ):
        entries = list_files("2025-07", groups=["simples"])
    assert len(entries) == 1
    assert entries[0]["group"] == "simples"
    assert entries[0]["filename"] == "Simples.zip"
    assert entries[0]["competencia"] == "2025-07"
    assert entries[0]["url"] == f"{BASE_URL}2025-07/Simples.zip"


def test_list_files_filtered_by_multiple_groups():
    """Filtering by multiple groups returns all matching entries."""
    with patch(
        "rfb_cnpj_fetcher.catalog._client.get",
        return_value=_mock_response(_COMP_HTML),
    ):
        entries = list_files("2025-07", groups=["socios", "cnaes"])
    groups = {e["group"] for e in entries}
    assert groups == {"socios", "cnaes"}


def test_list_files_url_construction():
    """Entry URLs are fully qualified."""
    with patch(
        "rfb_cnpj_fetcher.catalog._client.get",
        return_value=_mock_response(_COMP_HTML),
    ):
        entries = list_files("2025-07", groups=["cnaes"])
    assert entries[0]["url"].startswith("https://")
    assert entries[0]["url"].endswith("Cnaes.zip")
