"""Prova de equivalência: o lake tem o mesmo conteúdo antes e depois do agrupamento.

``golden/lake_antes_do_agrupamento.json`` foi gerado pelo conversor de um Parquet
por ZIP (commit anterior à mudança). Aqui o conversor atual lê os mesmos brutos
e o retrato do lake, por dataset e período (linhas, colunas e tipos, conteúdo
ordenado), tem de ser idêntico.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

pytest.importorskip("quantilica.analytics.lake")
pytest.importorskip("duckdb")

from rfb_cnpj_fetcher.lake import converter  # noqa: E402

from .lake_fixtures import GOLDEN, build_raw, snapshot  # noqa: E402


def _golden() -> dict:
    return json.loads(GOLDEN.read_text(encoding="utf-8"))


def _viaje_json(obj: dict) -> dict:
    return json.loads(json.dumps(obj, ensure_ascii=False))


def test_conteudo_do_lake_igual_ao_do_conversor_anterior(tmp_path: Path) -> None:
    build_raw(tmp_path / "raw")
    res = converter.convert(tmp_path / "raw", tmp_path / "lake")
    assert not res.errors

    atual = _viaje_json(snapshot(tmp_path / "lake"))
    golden = _golden()["lake"]

    assert sorted(atual) == sorted(golden)
    for dataset, esperado in golden.items():
        obtido = atual[dataset]
        assert obtido["colunas"] == esperado["colunas"], dataset
        assert sorted(obtido["periodos"]) == sorted(esperado["periodos"]), dataset
        for periodo, dados in esperado["periodos"].items():
            lido = obtido["periodos"][periodo]
            assert lido["linhas"] == dados["linhas"], (dataset, periodo)
            assert lido["colunas"] == dados["colunas"], (dataset, periodo)
            assert lido["conteudo"] == dados["conteudo"], (dataset, periodo)
