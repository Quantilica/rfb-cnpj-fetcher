"""Tests for the Hive lake conversion of RFB CNPJ open data."""

from __future__ import annotations

import zipfile
from importlib.metadata import entry_points
from pathlib import Path

import pytest

pytest.importorskip("quantilica.analytics.lake")
pytest.importorskip("duckdb")

from quantilica.analytics.lake import check_dataset, scan_dataset  # noqa: E402
from typer.testing import CliRunner  # noqa: E402

from rfb_cnpj_fetcher.lake import (  # noqa: E402
    SOURCE_ID,
    converter,
    infer_group,
    infer_partitions,
)
from rfb_cnpj_fetcher.plugin import app  # noqa: E402
from rfb_cnpj_fetcher.reader import LAYOUTS  # noqa: E402


def _line(*fields: str) -> str:
    return ";".join('"' + f.replace('"', '""') + '"' for f in fields)


def _zip(path: Path, lines: list[str]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(
            "K3241.K03200Y0.D61011.CSV", "\n".join(lines).encode("latin-1")
        )
    return path


@pytest.fixture
def raw_data(tmp_path: Path) -> Path:
    root = tmp_path / "raw"
    # cnaes fixture
    cnae_lines = [
        _line("6201500", "Desenvolvimento de programas de computador sob encomenda"),
        _line("6202300", "Desenvolvimento e customização de programas de computador"),
    ]
    _zip(root / "2026-10" / "cnaes" / "Cnaes@20261012.zip", cnae_lines)

    # empresas fixture (parts 0 and 1)
    emp0_lines = [
        _line(
            "00000000",
            "BANCO DO BRASIL SA",
            "2038",
            "10",
            "12000000000,00",
            "05",
            "",
        )
    ]
    emp1_lines = [
        _line(
            "00000001",
            "EMPRESA TESTE",
            "2062",
            "49",
            "50000,00",
            "01",
            "",
        )
    ]
    _zip(root / "2026-10" / "empresas" / "Empresas0@20261012.zip", emp0_lines)
    _zip(root / "2026-10" / "empresas" / "Empresas1@20261012.zip", emp1_lines)

    return root


def test_entry_point_registered() -> None:
    eps = entry_points(group="quantilica.lake")
    matches = [ep for ep in eps if ep.name == "rfb-cnpj"]
    assert len(matches) == 1
    loaded = matches[0].load()
    assert loaded is converter
    assert loaded.source_id == SOURCE_ID


def test_infer_group() -> None:
    assert infer_group(Path("2026-10/cnaes/Cnaes@20261012.zip")) == "cnaes"
    assert infer_group(Path("downloads/Empresas0.zip")) == "empresas"
    assert infer_group(Path("downloads/Estabelecimentos2.zip")) == "estabelecimentos"
    assert infer_group(Path("downloads/random.zip")) is None


def test_infer_partitions() -> None:
    parts = infer_partitions(Path("raw/2026-10/cnaes/Cnaes@20261012.zip"))
    assert parts == {"ano": "2026", "mes": "10"}

    parts_stamp = infer_partitions(Path("flat/Empresas0@20250710.zip"))
    assert parts_stamp == {"ano": "2025", "mes": "07"}

    assert infer_partitions(Path("unknown/file.zip")) is None


def test_converter_datasets() -> None:
    assert set(converter.datasets()) == set(LAYOUTS)


def test_convert_end_to_end(raw_data: Path, tmp_path: Path) -> None:
    lake_dir = tmp_path / "lake"
    res = converter.convert(raw_data, lake_dir)
    assert not res.errors
    assert res.converted == 3
    assert res.skipped == 0

    # Check cnaes dataset
    cnaes_dir = lake_dir / SOURCE_ID / "cnaes"
    assert check_dataset(cnaes_dir) == []

    df_cnaes = scan_dataset(cnaes_dir).collect()
    assert df_cnaes.shape == (2, 4)  # 2 data cols + ano + mes
    assert set(df_cnaes["codigo"].to_list()) == {"6201500", "6202300"}
    assert df_cnaes["ano"][0] == "2026"
    assert df_cnaes["mes"][0] == "10"

    # Check empresas dataset (has 2 parts)
    emp_dir = lake_dir / SOURCE_ID / "empresas"
    assert check_dataset(emp_dir) == []

    df_emp = scan_dataset(emp_dir).collect()
    assert df_emp.shape == (2, 9)  # 7 data cols + ano + mes
    assert set(df_emp["cnpj_basico"].to_list()) == {"00000000", "00000001"}

    # Second conversion skips already converted
    res2 = converter.convert(raw_data, lake_dir)
    assert not res2.errors
    assert res2.converted == 0
    assert res2.skipped == 3


def test_convert_filter_dataset(raw_data: Path, tmp_path: Path) -> None:
    lake_dir = tmp_path / "lake"
    res = converter.convert(raw_data, lake_dir, datasets=["cnaes"])
    assert not res.errors
    assert res.converted == 1
    assert (lake_dir / SOURCE_ID / "cnaes").exists()
    assert not (lake_dir / SOURCE_ID / "empresas").exists()


def test_cli_convert(raw_data: Path, tmp_path: Path) -> None:
    lake_dir = tmp_path / "lake"
    runner = CliRunner()
    result = runner.invoke(
        app,
        ["convert", "-i", str(raw_data), "-o", str(lake_dir), "--dataset", "cnaes"],
    )
    assert result.exit_code == 0
    assert (lake_dir / SOURCE_ID / "cnaes").exists()
