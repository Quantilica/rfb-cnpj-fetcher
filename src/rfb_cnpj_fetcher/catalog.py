"""Discovery of RFB CNPJ open data files via Nextcloud WebDAV directory inspection."""

from __future__ import annotations

import base64
import re
from typing import TypedDict
from xml.etree import ElementTree as ET

from quantilica.core.http import HttpClient
from quantilica.core.logging import get_logger

logger = get_logger(__name__)

BASE_URL = "https://arquivos.receitafederal.gov.br/"
WEBDAV_BASE_URL = "https://arquivos.receitafederal.gov.br/public.php/webdav/"
CNPJ_PATH = "Dados/Cadastros/CNPJ"

# Canonical group names, in display order
GROUPS: list[str] = [
    "empresas",
    "estabelecimentos",
    "socios",
    "simples",
    "cnaes",
    "naturezas",
    "qualificacoes",
    "municipios",
    "paises",
    "motivos",
]

# Filename patterns per group (case-insensitive match against directory index)
_GROUP_PATTERNS: dict[str, re.Pattern[str]] = {
    "empresas": re.compile(r"^Empresas\d+\.zip$", re.IGNORECASE),
    "estabelecimentos": re.compile(r"^Estabelecimentos\d+\.zip$", re.IGNORECASE),
    "socios": re.compile(r"^Socios\d+\.zip$", re.IGNORECASE),
    "simples": re.compile(r"^Simples\.zip$", re.IGNORECASE),
    "cnaes": re.compile(r"^Cnaes\.zip$", re.IGNORECASE),
    "naturezas": re.compile(r"^Naturezas\.zip$", re.IGNORECASE),
    "qualificacoes": re.compile(r"^Qualificacoes\.zip$", re.IGNORECASE),
    "municipios": re.compile(r"^Municipios\.zip$", re.IGNORECASE),
    "paises": re.compile(r"^Paises\.zip$", re.IGNORECASE),
    "motivos": re.compile(r"^Motivos\.zip$", re.IGNORECASE),
}


class FileEntry(TypedDict):
    """One downloadable ZIP file within a competência."""

    group: str  # canonical group name (ex: "empresas")
    filename: str  # basename (ex: "Empresas0.zip")
    url: str  # full download URL
    competencia: str  # YYYY-MM


_client = HttpClient(timeout=60.0)
_cached_token: str | None = None


def get_share_token(force_refresh: bool = False) -> str:
    """Extract Nextcloud public share token from arquivos.receitafederal.gov.br.

    Raises:
        RuntimeError: if the share token cannot be found in the redirect URL.
        httpx.HTTPError: if the portal is unreachable.
    """
    global _cached_token
    if _cached_token and not force_refresh:
        return _cached_token

    res = _client.get(BASE_URL)
    match = re.search(r"/s/([A-Za-z0-9]+)", str(res.url))
    if not match:
        raise RuntimeError(f"Could not extract Nextcloud share token from {res.url}")

    _cached_token = match.group(1)
    return _cached_token


def get_auth_headers(force_refresh: bool = False) -> dict[str, str]:
    """Return Basic Auth headers for WebDAV access using Nextcloud share token."""
    token = get_share_token(force_refresh=force_refresh)
    b64 = base64.b64encode(f"{token}:".encode()).decode()
    return {"Authorization": f"Basic {b64}"}


def _propfind(path: str) -> list[tuple[str, str]]:
    """Query Nextcloud WebDAV directory via PROPFIND.

    Returns a list of (filename, href) tuples for children of path.
    """
    headers = get_auth_headers()
    headers.update({"Depth": "1"})
    subpath = path.strip("/")
    url = f"{WEBDAV_BASE_URL}{subpath}/" if subpath else WEBDAV_BASE_URL

    res = _client.request("PROPFIND", url, headers=headers)
    if res.status_code == 401:
        headers = get_auth_headers(force_refresh=True)
        headers.update({"Depth": "1"})
        res = _client.request("PROPFIND", url, headers=headers)

    res.raise_for_status()

    root = ET.fromstring(res.content)
    items: list[tuple[str, str]] = []
    target_path = f"/public.php/webdav/{subpath}/".replace("//", "/")

    for resp in root.findall(".//{DAV:}response"):
        href_elem = resp.find(".//{DAV:}href")
        if href_elem is None or not href_elem.text:
            continue
        href = href_elem.text
        if href.rstrip("/") == target_path.rstrip("/"):
            continue
        name = href.rstrip("/").split("/")[-1]
        items.append((name, href))
    return items


def list_competencias() -> list[str]:
    """Return available competências (YYYY-MM), sorted newest first.

    Raises:
        httpx.HTTPError: if the RFB portal is unreachable.
    """
    items = _propfind(CNPJ_PATH)
    result = [name for name, _ in items if re.match(r"^\d{4}-\d{2}$", name)]
    logger.debug("Found %d competências at RFB portal.", len(result))
    return sorted(result, reverse=True)


def list_files(
    competencia: str,
    groups: list[str] | None = None,
) -> list[FileEntry]:
    """Return downloadable FileEntry objects for the given competência.

    Args:
        competencia: YYYY-MM string (e.g., "2025-07").
        groups: optional filter; if None, returns all known groups.

    Raises:
        httpx.HTTPError: if the competência directory is unreachable.
    """
    target_groups = groups if groups is not None else GROUPS
    patterns = {g: _GROUP_PATTERNS[g] for g in target_groups if g in _GROUP_PATTERNS}

    items = _propfind(f"{CNPJ_PATH}/{competencia}")
    entries: list[FileEntry] = []

    for filename, href in items:
        for group, pat in patterns.items():
            if pat.match(filename):
                entries.append(
                    FileEntry(
                        group=group,
                        filename=filename,
                        url=f"https://arquivos.receitafederal.gov.br{href}",
                        competencia=competencia,
                    )
                )
                break

    logger.debug(
        "Found %d file(s) for competência %s (groups: %s).",
        len(entries),
        competencia,
        ", ".join(target_groups),
    )
    return entries


def latest_competencia() -> str:
    """Return the most recent available competência.

    Raises:
        RuntimeError: if no competências are found.
        httpx.HTTPError: if the RFB portal is unreachable.
    """
    comps = list_competencias()
    if not comps:
        raise RuntimeError("No competências found at the RFB portal.")
    return comps[0]
