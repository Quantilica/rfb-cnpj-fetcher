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

from rfb_cnpj_fetcher.lake import (
    SOURCE_ID,  # noqa: E402
    converter,  # noqa: E402
)

from .lake_fixtures import (  # noqa: E402
    GOLDEN,
    build_raw,
    contagem_de_arquivos,
    snapshot,
)


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


def test_um_parquet_por_dataset_e_mes(tmp_path: Path) -> None:
    build_raw(tmp_path / "raw")
    res = converter.convert(tmp_path / "raw", tmp_path / "lake")
    assert not res.errors

    depois = contagem_de_arquivos(tmp_path / "lake")
    antes = _golden()["contagem_de_arquivos"]

    assert sorted(depois) == sorted(antes)
    for dataset, meses in depois.items():
        assert set(meses) == set(antes[dataset])
        assert set(meses.values()) == {1}, dataset
    # Antes: um Parquet por ZIP (13 nas fixtures). Depois: um por dataset e mês (8).
    assert sum(sum(m.values()) for m in antes.values()) == 13
    assert sum(sum(m.values()) for m in depois.values()) == 8
    nomes = sorted(p.name for p in (tmp_path / "lake" / SOURCE_ID).rglob("*.parquet"))
    assert nomes == [
        "cnaes_202609.parquet",
        "cnaes_202610.parquet",
        "empresas_202608.parquet",
        "empresas_202609.parquet",
        "empresas_202610.parquet",
        "estabelecimentos_202610.parquet",
        "simples_202610.parquet",
        "socios_202610.parquet",
    ]
