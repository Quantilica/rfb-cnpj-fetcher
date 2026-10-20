"""Tests for the CNPJ CSV reader (requires the `analysis` extra).

The fixtures are written in the real Receita format (Latin-1, ``;``, every
field quoted, no header) with fictitious companies.
"""

from __future__ import annotations

import datetime as dt
import zipfile
from decimal import Decimal
from pathlib import Path

import polars as pl
import pytest

from rfb_cnpj_fetcher.catalog import GROUPS
from rfb_cnpj_fetcher.reader import (
    CAPITAL_SOCIAL_DTYPE,
    LAYOUTS,
    read_file,
    write_parquet,
)


def _line(*fields: str) -> str:
    return ";".join('"' + f.replace('"', '""') + '"' for f in fields)


def _zip(tmp_path: Path, group: str, lines: list[str], name: str = "X") -> Path:
    path = tmp_path / "2026-10" / group / f"{name}@20261012.zip"
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(
            "K3241.K03200Y0.D61011.CSV", "\n".join(lines).encode("latin-1")
        )
    return path


def _estabelecimento(**overrides: str) -> str:
    fields = dict.fromkeys(LAYOUTS["estabelecimentos"], "")
    fields.update(
        cnpj_basico="00012345",
        cnpj_ordem="0001",
        cnpj_dv="09",
        identificador_matriz_filial="1",
        situacao_cadastral="02",
        data_situacao_cadastral="20050103",
        motivo_situacao_cadastral="00",
        data_inicio_atividade="19990315",
        cnae_fiscal_principal="0111301",
        cnae_fiscal_secundaria="0112101,0113000",
        uf="SP",
        municipio="7107",
    )
    fields.update(overrides)
    return _line(*fields.values())


def test_layouts_cover_every_catalog_group():
    assert set(LAYOUTS) == set(GROUPS)
    assert len(LAYOUTS["empresas"]) == 7
    assert len(LAYOUTS["estabelecimentos"]) == 30
    assert len(LAYOUTS["socios"]) == 11
    assert len(LAYOUTS["simples"]) == 7


def test_empresas_keep_leading_zeros_exact_capital_and_latin1(tmp_path):
    path = _zip(
        tmp_path,
        "empresas",
        [
            _line(
                "00012345",
                "CONSTRUÇÃO EXEMPLO LTDA",
                "2062",
                "49",
                "5173936,89",
                "01",
                "",
            ),
            _line(
                "00000001", 'COMÉRCIO "AÇO; FERRO" S.A.', "2054", "10", "0,00", "05", ""
            ),
        ],
    )
    df = read_file(path)

    assert df.schema["cnpj_basico"] == pl.Utf8
    assert df.schema["capital_social"] == CAPITAL_SOCIAL_DTYPE
    assert df["cnpj_basico"].to_list() == ["00012345", "00000001"]
    assert df["natureza_juridica"].to_list() == ["2062", "2054"]
    assert df["razao_social"].to_list() == [
        "CONSTRUÇÃO EXEMPLO LTDA",
        'COMÉRCIO "AÇO; FERRO" S.A.',
    ]
    assert df["capital_social"].to_list() == [Decimal("5173936.89"), Decimal("0.00")]
    assert df["ente_federativo_responsavel"].null_count() == 2


def test_estabelecimentos_dates_sentinels_and_embedded_separators(tmp_path):
    path = _zip(
        tmp_path,
        "estabelecimentos",
        [
            _estabelecimento(complemento="SALA 1; BLOCO B\nFUNDOS"),
            _estabelecimento(
                cnpj_basico="00000002",
                data_situacao_cadastral="0",
                situacao_especial="INTERVENCAO",
                data_situacao_especial="20200101",
            ),
        ],
    )
    df = read_file(path)

    assert df.height == 2
    assert df.columns == list(LAYOUTS["estabelecimentos"])
    first, second = df.rows(named=True)
    assert first["complemento"] == "SALA 1; BLOCO B\nFUNDOS"
    assert first["cnae_fiscal_secundaria"] == "0112101,0113000"
    assert first["data_situacao_cadastral"] == dt.date(2005, 1, 3)
    assert first["data_situacao_especial"] is None
    assert second["data_situacao_cadastral"] is None
    assert second["data_situacao_especial"] == dt.date(2020, 1, 1)
    assert df.schema["data_inicio_atividade"] == pl.Date


def test_socios_column_order(tmp_path):
    path = _zip(
        tmp_path,
        "socios",
        [
            _line(
                "00012345",
                "2",
                "FULANO DE TAL",
                "***123456**",
                "49",
                "20100201",
                "",
                "***000000**",
                "",
                "00",
                "5",
            )
        ],
    )
    row = read_file(path).row(0, named=True)

    assert row["cnpj_basico"] == "00012345"
    assert row["identificador_socio"] == "2"
    assert row["nome_socio"] == "FULANO DE TAL"
    assert row["cnpj_cpf_socio"] == "***123456**"
    assert row["qualificacao_socio"] == "49"
    assert row["data_entrada_sociedade"] == dt.date(2010, 2, 1)
    assert row["pais"] is None
    assert row["representante_legal"] == "***000000**"
    assert row["nome_representante_legal"] is None
    assert row["qualificacao_representante_legal"] == "00"
    assert row["faixa_etaria"] == "5"


def test_simples_zero_dates_become_null(tmp_path):
    path = _zip(
        tmp_path,
        "simples",
        [_line("00012345", "S", "20070701", "00000000", "N", "00000000", "00000000")],
    )
    row = read_file(path).row(0, named=True)

    assert row["data_opcao_simples"] == dt.date(2007, 7, 1)
    assert row["data_exclusao_simples"] is None
    assert row["data_opcao_mei"] is None


def test_domain_table_group_inferred_from_path(tmp_path):
    path = _zip(tmp_path, "cnaes", [_line("0111301", "Cultivo de arroz")], "Cnaes")
    df = read_file(path)

    assert df.columns == ["codigo", "descricao"]
    assert df.row(0) == ("0111301", "Cultivo de arroz")


def test_unknown_group_raises(tmp_path):
    path = _zip(tmp_path, "outros", [_line("1", "x")])
    with pytest.raises(ValueError, match="Grupo desconhecido"):
        read_file(path)


def test_short_row_raises_instead_of_shifting(tmp_path):
    path = _zip(
        tmp_path,
        "simples",
        [
            _line("00012345", "S", "20070701", "00000000", "N", "00000000", "00000000"),
            _line("00012346", "S", "20070701", "00000000", "N", "00000000"),
        ],
    )
    with pytest.raises(ValueError, match="menos de 7 campos"):
        read_file(path)


@pytest.mark.parametrize("position", [0, 1])
def test_long_row_raises(tmp_path, position):
    lines = [_line("0111301", "Cultivo de arroz")]
    lines.insert(position, _line("0112101", "Cultivo de milho", "extra"))
    path = _zip(tmp_path, "cnaes", lines)
    with pytest.raises(ValueError, match="mais de 2 campos"):
        read_file(path)


def test_invalid_date_raises(tmp_path):
    path = _zip(
        tmp_path,
        "simples",
        [_line("00012345", "S", "20070231", "00000000", "N", "00000000", "00000000")],
    )
    with pytest.raises(ValueError, match="fora do layout"):
        read_file(path)


def test_invalid_capital_raises(tmp_path):
    path = _zip(
        tmp_path,
        "empresas",
        [_line("00012345", "EXEMPLO LTDA", "2062", "49", "1.000,00", "01", "")],
    )
    with pytest.raises(ValueError, match="fora do layout"):
        read_file(path)


def test_zip_with_two_files_raises(tmp_path):
    path = tmp_path / "2026-10" / "cnaes" / "Cnaes@20261012.zip"
    path.parent.mkdir(parents=True)
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("a.csv", _line("1", "a"))
        archive.writestr("b.csv", _line("2", "b"))
    with pytest.raises(ValueError, match="único arquivo"):
        read_file(path)


def test_write_parquet_round_trip(tmp_path):
    path = _zip(
        tmp_path,
        "empresas",
        [_line("00012345", "EXEMPLO LTDA", "2062", "49", "1000,50", "01", "")],
    )
    df = read_file(path)
    target = write_parquet(df, tmp_path / "out" / "empresas.parquet")
    back = pl.read_parquet(target)

    assert back["cnpj_basico"].to_list() == ["00012345"]
    assert back["capital_social"].to_list() == [Decimal("1000.50")]
