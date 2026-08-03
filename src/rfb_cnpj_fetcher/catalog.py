"""Discovery of RFB CNPJ open data files via HTTP directory index scraping."""

from __future__ import annotations

import re
from typing import TypedDict

from bs4 import BeautifulSoup
from quantilica.core.http import HttpClient
from quantilica.core.logging import get_logger

logger = get_logger(__name__)

BASE_URL = "https://dadosabertos.rfb.gov.br/CNPJ/dados_abertos_cnpj/"

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


def list_competencias() -> list[str]:
    """Return available competências (YYYY-MM), sorted newest first.

    Raises:
        httpx.HTTPError: if the RFB portal is unreachable.
    """
    html = _client.get(BASE_URL).text
    soup = BeautifulSoup(html, "html.parser")
    result: list[str] = []
    for link in soup.find_all("a", href=True):
        href = link["href"].strip("/")
        if re.match(r"^\d{4}-\d{2}$", href):
            result.append(href)
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
    url = f"{BASE_URL}{competencia}/"
    html = _client.get(url).text
    soup = BeautifulSoup(html, "html.parser")

    target_groups = groups if groups is not None else GROUPS
    patterns = {g: _GROUP_PATTERNS[g] for g in target_groups if g in _GROUP_PATTERNS}

    entries: list[FileEntry] = []
    for link in soup.find_all("a", href=True):
        filename = link["href"].strip()
        for group, pat in patterns.items():
            if pat.match(filename):
                entries.append(
                    FileEntry(
                        group=group,
                        filename=filename,
                        url=f"{url}{filename}",
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
