"""Tests for rfb_cnpj_fetcher.catalog — HTTP mocked with `unittest.mock`."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from rfb_cnpj_fetcher.catalog import (
    WEBDAV_BASE_URL,
    get_auth_headers,
    get_share_token,
    list_competencias,
    list_files,
)

_INDEX_XML = """\
<?xml version="1.0"?>
<d:multistatus xmlns:d="DAV:">
<d:response><d:href>/public.php/webdav/Dados/Cadastros/CNPJ/</d:href></d:response>
<d:response><d:href>/public.php/webdav/Dados/Cadastros/CNPJ/2025-07/</d:href></d:response>
<d:response><d:href>/public.php/webdav/Dados/Cadastros/CNPJ/2025-06/</d:href></d:response>
<d:response><d:href>/public.php/webdav/Dados/Cadastros/CNPJ/2024-12/</d:href></d:response>
</d:multistatus>
"""

_COMP_XML = """\
<?xml version="1.0"?>
<d:multistatus xmlns:d="DAV:">
<d:response><d:href>/public.php/webdav/Dados/Cadastros/CNPJ/2025-07/</d:href></d:response>
<d:response><d:href>/public.php/webdav/Dados/Cadastros/CNPJ/2025-07/Empresas0.zip</d:href></d:response>
<d:response><d:href>/public.php/webdav/Dados/Cadastros/CNPJ/2025-07/Empresas1.zip</d:href></d:response>
<d:response><d:href>/public.php/webdav/Dados/Cadastros/CNPJ/2025-07/Socios0.zip</d:href></d:response>
<d:response><d:href>/public.php/webdav/Dados/Cadastros/CNPJ/2025-07/Simples.zip</d:href></d:response>
<d:response><d:href>/public.php/webdav/Dados/Cadastros/CNPJ/2025-07/Cnaes.zip</d:href></d:response>
<d:response><d:href>/public.php/webdav/Dados/Cadastros/CNPJ/2025-07/Municipios.zip</d:href></d:response>
</d:multistatus>
"""


def _mock_response(content: bytes | str, status_code: int = 207) -> MagicMock:
    resp = MagicMock()
    resp.content = content.encode("utf-8") if isinstance(content, str) else content
    resp.status_code = status_code
    return resp


def test_get_share_token():
    """Share token is extracted from redirect URL."""
    mock_res = MagicMock()
    mock_res.url = "https://arquivos.receitafederal.gov.br/index.php/s/TESTTOKEN123"
    with patch("rfb_cnpj_fetcher.catalog._client.get", return_value=mock_res):
        token = get_share_token(force_refresh=True)
        headers = get_auth_headers()
    assert token == "TESTTOKEN123"
    assert "Authorization" in headers
    assert headers["Authorization"].startswith("Basic ")


def test_list_competencias_sorted_desc():
    """Competências are returned newest-first."""
    with (
        patch(
            "rfb_cnpj_fetcher.catalog.get_auth_headers",
            return_value={"Authorization": "Basic TEST"},
        ),
        patch(
            "rfb_cnpj_fetcher.catalog._client.request",
            return_value=_mock_response(_INDEX_XML),
        ),
    ):
        comps = list_competencias()
    assert comps == ["2025-07", "2025-06", "2024-12"]


def test_list_competencias_ignores_non_date_links():
    """Parent directory links are not returned."""
    with (
        patch(
            "rfb_cnpj_fetcher.catalog.get_auth_headers",
            return_value={"Authorization": "Basic TEST"},
        ),
        patch(
            "rfb_cnpj_fetcher.catalog._client.request",
            return_value=_mock_response(_INDEX_XML),
        ),
    ):
        comps = list_competencias()
    assert all(len(c) == 7 for c in comps)  # YYYY-MM


def test_list_files_multi_part_group():
    """Multi-part groups (Empresas0, Empresas1) are both discovered."""
    with (
        patch(
            "rfb_cnpj_fetcher.catalog.get_auth_headers",
            return_value={"Authorization": "Basic TEST"},
        ),
        patch(
            "rfb_cnpj_fetcher.catalog._client.request",
            return_value=_mock_response(_COMP_XML),
        ),
    ):
        entries = list_files("2025-07")
    groups = [e["group"] for e in entries]
    assert groups.count("empresas") == 2


def test_list_files_all_known_groups_present():
    """Every group with a matching filename is returned."""
    with (
        patch(
            "rfb_cnpj_fetcher.catalog.get_auth_headers",
            return_value={"Authorization": "Basic TEST"},
        ),
        patch(
            "rfb_cnpj_fetcher.catalog._client.request",
            return_value=_mock_response(_COMP_XML),
        ),
    ):
        entries = list_files("2025-07")
    groups = {e["group"] for e in entries}
    assert {"empresas", "socios", "simples", "cnaes", "municipios"} <= groups


def test_list_files_filtered_by_single_group():
    """Filtering by group returns only matching entries."""
    with (
        patch(
            "rfb_cnpj_fetcher.catalog.get_auth_headers",
            return_value={"Authorization": "Basic TEST"},
        ),
        patch(
            "rfb_cnpj_fetcher.catalog._client.request",
            return_value=_mock_response(_COMP_XML),
        ),
    ):
        entries = list_files("2025-07", groups=["simples"])
    assert len(entries) == 1
    assert entries[0]["group"] == "simples"
    assert entries[0]["filename"] == "Simples.zip"
    assert entries[0]["competencia"] == "2025-07"
    expected_url = f"{WEBDAV_BASE_URL}Dados/Cadastros/CNPJ/2025-07/Simples.zip"
    assert entries[0]["url"] == expected_url


def test_list_files_filtered_by_multiple_groups():
    """Filtering by multiple groups returns all matching entries."""
    with (
        patch(
            "rfb_cnpj_fetcher.catalog.get_auth_headers",
            return_value={"Authorization": "Basic TEST"},
        ),
        patch(
            "rfb_cnpj_fetcher.catalog._client.request",
            return_value=_mock_response(_COMP_XML),
        ),
    ):
        entries = list_files("2025-07", groups=["socios", "cnaes"])
    groups = {e["group"] for e in entries}
    assert groups == {"socios", "cnaes"}


def test_list_files_url_construction():
    """Entry URLs are fully qualified."""
    with (
        patch(
            "rfb_cnpj_fetcher.catalog.get_auth_headers",
            return_value={"Authorization": "Basic TEST"},
        ),
        patch(
            "rfb_cnpj_fetcher.catalog._client.request",
            return_value=_mock_response(_COMP_XML),
        ),
    ):
        entries = list_files("2025-07", groups=["cnaes"])
    assert entries[0]["url"].startswith("https://")
    assert entries[0]["url"].endswith("Cnaes.zip")
