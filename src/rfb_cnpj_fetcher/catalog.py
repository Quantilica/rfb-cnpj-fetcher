"""Discovery of RFB CNPJ open data files via Nextcloud WebDAV directory inspection."""

from __future__ import annotations

import base64
import functools
import os
import re
import time
from typing import Any, TypedDict
from xml.etree import ElementTree as ET

from quantilica.core.http import HttpClient
from quantilica.core.logging import get_logger

logger = get_logger(__name__)

BASE_URL = "https://arquivos.receitafederal.gov.br/"
WEBDAV_BASE_URL = "https://arquivos.receitafederal.gov.br/public.php/webdav/"
# Endpoint de download sem autenticação: o token público do share vai no path.
# O GET/HEAD em WEBDAV_BASE_URL exige Basic auth (401 no client canônico do SDK);
# DAV_FILES_BASE_URL aceita o token na URL e responde ETag/Last-Modified/Content-Length.
DAV_FILES_BASE_URL = "https://arquivos.receitafederal.gov.br/public.php/dav/files/"
CNPJ_PATH = "Dados/Cadastros/CNPJ"

# Token do share público usado como último recurso quando a landing page deixa de
# redirecionar para /s/<token> (ex.: corpo vazio com 200). Validado manualmente via
# PROPFIND com Basic auth no WebDAV.
DEFAULT_SHARE_TOKEN = "gn672Ad4CF8N6TK"
SHARE_TOKEN_ENV_VAR = "RFB_CNPJ_SHARE_TOKEN"

# O portal responde de forma intermitente ao PROPFIND com HTTP 200 e corpo vazio.
PROPFIND_MAX_RETRIES = 2
PROPFIND_RETRY_DELAY = 5.0

# Canonical group names, in display order
GROUPS: dict[str, dict[str, str]] = {
    "empresas": {"name": "Empresas"},
    "estabelecimentos": {"name": "Estabelecimentos"},
    "socios": {"name": "Sócios"},
    "simples": {"name": "Simples"},
    "cnaes": {"name": "CNAEs"},
    "naturezas": {"name": "Naturezas Jurídicas"},
    "qualificacoes": {"name": "Qualificações de Sócios"},
    "municipios": {"name": "Municípios"},
    "paises": {"name": "Países"},
    "motivos": {"name": "Motivos de Situação Cadastral"},
}

GROUP_ALIASES: dict[str, list[str]] = {}

# Filename patterns per group (case-insensitive match against directory index).
# Suporta nomes canônicos e correções com sufixo de chamado/reparo
# (ex.: Estabelecimentos6-RF0819000032530.zip).
_GROUP_PATTERNS: dict[str, re.Pattern[str]] = {
    "empresas": re.compile(
        r"^(?P<canonical>Empresas\d+)(?:-[A-Za-z0-9]+)?\.zip$", re.IGNORECASE
    ),
    "estabelecimentos": re.compile(
        r"^(?P<canonical>Estabelecimentos\d+)(?:-[A-Za-z0-9]+)?\.zip$",
        re.IGNORECASE,
    ),
    "socios": re.compile(
        r"^(?P<canonical>Socios\d+)(?:-[A-Za-z0-9]+)?\.zip$", re.IGNORECASE
    ),
    "simples": re.compile(
        r"^(?P<canonical>Simples)(?:-[A-Za-z0-9]+)?\.zip$", re.IGNORECASE
    ),
    "cnaes": re.compile(
        r"^(?P<canonical>Cnaes)(?:-[A-Za-z0-9]+)?\.zip$", re.IGNORECASE
    ),
    "naturezas": re.compile(
        r"^(?P<canonical>Naturezas)(?:-[A-Za-z0-9]+)?\.zip$", re.IGNORECASE
    ),
    "qualificacoes": re.compile(
        r"^(?P<canonical>Qualificacoes)(?:-[A-Za-z0-9]+)?\.zip$", re.IGNORECASE
    ),
    "municipios": re.compile(
        r"^(?P<canonical>Municipios)(?:-[A-Za-z0-9]+)?\.zip$", re.IGNORECASE
    ),
    "paises": re.compile(
        r"^(?P<canonical>Paises)(?:-[A-Za-z0-9]+)?\.zip$", re.IGNORECASE
    ),
    "motivos": re.compile(
        r"^(?P<canonical>Motivos)(?:-[A-Za-z0-9]+)?\.zip$", re.IGNORECASE
    ),
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
    """Resolve o token de share público do Nextcloud.

    A ordem de resolução é:

    1. variável de ambiente ``RFB_CNPJ_SHARE_TOKEN`` (se definida e não vazia);
    2. descoberta via redirect da landing page para ``/s/<token>``;
    3. fallback para ``DEFAULT_SHARE_TOKEN`` (com WARNING) quando a descoberta
       falha (sem match ou erro HTTP/rede na landing page).

    Args:
        force_refresh (bool): Se True, refaz a resolução em vez de usar o cache
            em memória. A variável de ambiente continua tendo precedência.
            Defaults to False.

    Returns:
        str: O token de share resolvido.

    Raises:
        RuntimeError: se nenhuma estratégia de resolução conseguir extrair um
            token e o fallback também estiver indisponível.
    """
    global _cached_token

    env_token = os.environ.get(SHARE_TOKEN_ENV_VAR, "").strip()
    if env_token:
        _cached_token = env_token
        return _cached_token

    if _cached_token and not force_refresh:
        return _cached_token

    try:
        res = _client.get(BASE_URL)
        match = re.search(r"/s/([A-Za-z0-9]+)", str(res.url))
    except Exception:
        match = None
    if not match:
        logger.warning(
            "Não foi possível descobrir o token de share do Nextcloud via "
            "landing page %s (sem redirect para /s/<token> ou erro de rede). "
            "Usando token de fallback %s.",
            BASE_URL,
            DEFAULT_SHARE_TOKEN,
        )
        _cached_token = DEFAULT_SHARE_TOKEN
        return _cached_token

    _cached_token = match.group(1)
    return _cached_token


def get_auth_headers(force_refresh: bool = False) -> dict[str, str]:
    """Return Basic Auth headers for WebDAV access using Nextcloud share token.

    Args:
        force_refresh (bool): Whether to force a refresh of the share token. Defaults
            to False.

    Returns:
        dict[str, str]: The dictionary containing the Authorization header.
    """
    token = get_share_token(force_refresh=force_refresh)
    b64 = base64.b64encode(f"{token}:".encode()).decode()
    return {"Authorization": f"Basic {b64}"}


def _download_url(href: str) -> str:
    """Build a download URL that requires no Authorization header.

    PROPFIND returns hrefs rooted at ``/public.php/webdav/``. Downloading (and
    HEAD) against that endpoint requires Basic auth, which the canonical SDK
    client does not carry (it would 401). The public-share ``dav/files/{token}``
    endpoint instead accepts the token in the path, so embed it and drop the
    webdav prefix.

    Args:
        href: Full href from a PROPFIND response (e.g.
            ``/public.php/webdav/Dados/Cadastros/CNPJ/2025-07/Simples.zip``).

    Returns:
        str: Auth-free download URL (``.../public.php/dav/files/{token}/...``).
    """
    rel = href.replace("/public.php/webdav/", "", 1).lstrip("/")
    token = get_share_token()
    return f"{DAV_FILES_BASE_URL}{token}/{rel}"


def _parse_multistatus(res: Any) -> ET.Element | None:
    """Parse a PROPFIND response, returning None if it is not a 207 multistatus."""
    if res.status_code != 207 or not res.content:
        return None
    try:
        return ET.fromstring(res.content)
    except ET.ParseError:
        return None


def _propfind(path: str) -> list[tuple[str, str]]:
    """Query Nextcloud WebDAV directory via PROPFIND.

    Returns a list of (filename, href) tuples for children of path.
    """
    headers = get_auth_headers()
    headers.update({"Depth": "1"})
    subpath = path.strip("/")
    url = f"{WEBDAV_BASE_URL}{subpath}/" if subpath else WEBDAV_BASE_URL

    root: ET.Element | None = None
    res = None
    for attempt in range(PROPFIND_MAX_RETRIES + 1):
        if attempt:
            time.sleep(PROPFIND_RETRY_DELAY)
        res = _client.request("PROPFIND", url, headers=headers)
        if res.status_code == 401:
            headers = get_auth_headers(force_refresh=True)
            headers.update({"Depth": "1"})
            res = _client.request("PROPFIND", url, headers=headers)
            if res.status_code == 401:
                # Tentativa única de refresh: se o token de fallback também for
                # inválido, falha com erro claro em vez de entrar em loop.
                raise RuntimeError(
                    f"WebDAV do RFB rejeitou o token de share (401) mesmo após "
                    f"refresh em {url}. Defina a variável de ambiente "
                    f"{SHARE_TOKEN_ENV_VAR} com um token válido."
                )

        res.raise_for_status()
        root = _parse_multistatus(res)
        if root is not None:
            break
        logger.warning(
            "PROPFIND com HTTP %s e corpo vazio/não-XML em %s (tentativa %d/%d)",
            res.status_code,
            url,
            attempt + 1,
            PROPFIND_MAX_RETRIES + 1,
        )

    if root is None:
        assert res is not None
        raise RuntimeError(
            f"Servidor da Receita Federal respondeu ao PROPFIND com HTTP "
            f"{res.status_code} e corpo vazio/não-XML (instabilidade do portal "
            f"arquivos.receitafederal.gov.br) em {url}"
        )

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

    Returns:
        list[str]: A list of available competências in YYYY-MM format.

    Raises:
        httpx2.HTTPError: if the RFB portal is unreachable.
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
        competencia (str): YYYY-MM string (e.g., "2025-07").
        groups (list[str] | None, optional): filter by specific groups; if None,
            returns all known groups.

    Returns:
        list[FileEntry]: A list of files available for the specified competência and
            groups.

    Raises:
        httpx2.HTTPError: if the competência directory is unreachable.
    """
    target_groups = groups if groups is not None else GROUPS
    patterns = {g: _GROUP_PATTERNS[g] for g in target_groups if g in _GROUP_PATTERNS}

    items = _propfind(f"{CNPJ_PATH}/{competencia}")
    selected: dict[tuple[str, str], tuple[bool, FileEntry]] = {}

    for filename, href in items:
        for group, pat in patterns.items():
            m = pat.match(filename)
            if m:
                canonical_base = m.group("canonical")
                canonical_filename = f"{canonical_base}.zip"
                is_repaired = bool("-" in filename)
                key = (group, canonical_filename.lower())
                if key not in selected or (is_repaired and not selected[key][0]):
                    selected[key] = (
                        is_repaired,
                        FileEntry(
                            group=group,
                            filename=canonical_filename,
                            url=_download_url(href),
                            competencia=competencia,
                        ),
                    )
                break

    entries = [entry for _, entry in selected.values()]

    logger.debug(
        "Found %d file(s) for competência %s (groups: %s).",
        len(entries),
        competencia,
        ", ".join(target_groups),
    )
    return entries


def latest_competencia() -> str:
    """Return the most recent available competência.

    Returns:
        str: The most recent competência in YYYY-MM format.

    Raises:
        RuntimeError: if no competências are found.
        httpx2.HTTPError: if the RFB portal is unreachable.
    """
    comps = list_competencias()
    if not comps:
        raise RuntimeError("No competências found at the RFB portal.")
    return comps[0]


@functools.lru_cache
def _get_latest_entries() -> list[FileEntry]:
    comp = latest_competencia()
    return list_files(comp, groups=list(GROUPS.keys()))


def list_datasets(group: str | None = None) -> list[dict[str, Any]]:
    """Return all datasets for the latest competência, optionally filtered by group.

    Args:
        group (str | None, optional): If provided, filters the datasets to only return
            those matching the group.

    Returns:
        list[dict[str, Any]]: A list of dictionary objects representing datasets.
    """
    entries = _get_latest_entries()
    res: list[dict[str, Any]] = []
    for e in entries:
        if group is None or e["group"] == group:
            res.append(
                {
                    "id": e["filename"],
                    "url": e["url"],
                    "ext": "zip",
                    "group": e["group"],
                    "year": int(e["competencia"][:4]),
                    "month": int(e["competencia"][5:7]),
                    "filename": e["filename"],
                    "competencia": e["competencia"],
                }
            )
    return res
