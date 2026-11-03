# Copyright (c) 2026 Komesu, D.K.
# Licensed under the MIT License.

"""Testes para DataRepository do rfb-cnpj-fetcher."""

import datetime as dt
from pathlib import Path

from rfb_cnpj_fetcher.storage import DataRepository


def test_path_for_entry_empresas(tmp_path: Path) -> None:
    repo = DataRepository(tmp_path)
    entry = {
        "group": "empresas",
        "filename": "Empresas0.zip",
        "url": "https://example.com/Empresas0.zip",
        "competencia": "2025-07",
    }
    path = repo.path_for_entry(entry, last_modified=dt.date(2025, 7, 10))
    expected = tmp_path / "empresas" / "empresas_0_2025-07@20250710.zip"
    assert path == expected


def test_path_for_entry_simples(tmp_path: Path) -> None:
    repo = DataRepository(tmp_path)
    entry = {
        "group": "simples",
        "filename": "Simples.zip",
        "url": "https://example.com/Simples.zip",
        "competencia": "2025-07",
    }
    path = repo.path_for_entry(entry, last_modified=dt.date(2025, 7, 10))
    expected = tmp_path / "simples" / "simples_2025-07@20250710.zip"
    assert path == expected


def test_path_for_entry_cnaes(tmp_path: Path) -> None:
    repo = DataRepository(tmp_path)
    entry = {
        "group": "cnaes",
        "filename": "Cnaes.zip",
        "url": "https://example.com/Cnaes.zip",
        "competencia": "2025-07",
    }
    path = repo.path_for_entry(entry, last_modified=dt.date(2025, 7, 10))
    expected = tmp_path / "cnaes" / "cnaes_2025-07@20250710.zip"
    assert path == expected


def test_path_for_entry_fallback_timestamp(tmp_path: Path) -> None:
    repo = DataRepository(tmp_path)
    entry = {
        "group": "empresas",
        "filename": "Empresas0.zip",
        "url": "https://example.com/Empresas0.zip",
        "competencia": "2025-07",
    }
    path = repo.path_for_entry(entry, last_modified=None)
    today_str = dt.date.today().strftime("%Y%m%d")
    expected = tmp_path / "empresas" / f"empresas_0_2025-07@{today_str}.zip"
    assert path == expected
