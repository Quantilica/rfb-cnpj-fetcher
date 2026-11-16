"""Agrupamento das partes do mês: segunda execução, migração, auditoria e limpeza."""

from __future__ import annotations

import json
import shutil
import zipfile
from pathlib import Path

import pyarrow.parquet as pq
import pytest

pytest.importorskip("quantilica.analytics.lake")
pytest.importorskip("duckdb")

from quantilica.analytics import lake_audit  # noqa: E402
from quantilica.analytics.lake import (  # noqa: E402
    META_MEMBERS,
    LakeWriter,
    check_dataset,
    scan_dataset,
)
from quantilica.core.lake import DatasetDescriptor, partition_types_for  # noqa: E402

import rfb_cnpj_fetcher.lake as lake_mod  # noqa: E402
from rfb_cnpj_fetcher.lake import (  # noqa: E402
    SOURCE_ID,
    converter,
    infer_partitions,
)
from rfb_cnpj_fetcher.reader import LAYOUTS  # noqa: E402

from .lake_fixtures import (  # noqa: E402
    build_raw,
    contagem_de_arquivos,
)


def _legacy_convert(raw: Path, lake: Path) -> None:
    """O conversor anterior: um Parquet por ZIP, como ``write_duckdb`` o escrevia."""
    for path in sorted(raw.rglob("*.zip")):
        group = lake_mod.infer_group(path)
        writer = LakeWriter(
            lake / SOURCE_ID / group,
            DatasetDescriptor(
                source_id=SOURCE_ID,
                dataset_id=group,
                alias=group,
                partition_keys=["ano", "mes"],
                partition_types=partition_types_for(["ano", "mes"]),
            ),
        )
        writer.write_duckdb(
            path,
            partitions=infer_partitions(path),
            separator=";",
            encoding="latin-1",
            header=False,
            names=LAYOUTS[group],
            quote='"',
            escape='"',
            parallel=False,
        )


def _parquets(lake: Path) -> list[Path]:
    return sorted((lake / SOURCE_ID).rglob("*.parquet"))


def _members(path: Path) -> dict:
    raw = pq.ParquetFile(path).metadata.metadata
    return json.loads(raw[META_MEMBERS.encode()])


def _rewrite_zip(path: Path, linhas: list[str]) -> None:
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as arquivo:
        arquivo.writestr("K3241.K03200Y0.D60911.EMPRECSV", "\n".join(linhas).encode())


@pytest.fixture
def raw(tmp_path: Path) -> Path:
    build_raw(tmp_path / "raw")
    return tmp_path / "raw"


def test_membros_do_grupo_no_rodape_e_origem_nas_linhas(
    raw: Path, tmp_path: Path
) -> None:
    lake = tmp_path / "lake"
    res = converter.convert(raw, lake)
    assert not res.errors and res.converted == 12 and res.skipped == 0

    arquivo = lake / SOURCE_ID / "estabelecimentos/ano=2026/mes=10"
    arquivo = arquivo / "estabelecimentos_202610.parquet"
    membros = _members(arquivo)
    assert sorted(membros) == ["Estabelecimentos0", "Estabelecimentos1"]
    assert {m["rows"] for m in membros.values()} == {4, 7}
    assert all(
        m["origin_sha256"] and m["contract_version"] == 1 for m in membros.values()
    )
    assert all(m["converter_version"] == "1" for m in membros.values())
    # Sem coluna de parte: só as colunas do layout e _origem.
    colunas = pq.ParquetFile(arquivo).schema_arrow.names
    assert colunas == [*LAYOUTS["estabelecimentos"], "_origem"]
    df = scan_dataset(lake / SOURCE_ID / "estabelecimentos").collect()
    assert df.group_by("_origem").len().sort("_origem").rows() == [
        ("Estabelecimentos0", 4),
        ("Estabelecimentos1", 7),
    ]
    assert check_dataset(lake / SOURCE_ID / "estabelecimentos") == []


def test_segunda_execucao_pula_tudo_sem_reescrever_nem_extrair(
    raw: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    lake = tmp_path / "lake"
    assert converter.convert(raw, lake).converted == 12
    antes = {p: (p.stat().st_mtime_ns, p.stat().st_ino) for p in _parquets(lake)}

    def nao_extrair(self, path, names):
        raise AssertionError(f"extraiu {path.name} sem precisar")

    monkeypatch.setattr(lake_mod._Extractions, "source", nao_extrair)
    res = converter.convert(raw, lake)

    assert not res.errors
    assert (res.converted, res.skipped) == (0, 12)
    depois = {p: (p.stat().st_mtime_ns, p.stat().st_ino) for p in _parquets(lake)}
    assert depois == antes  # nenhum arquivo reescrito
    assert not list((lake / SOURCE_ID).rglob(".tmp/*"))


def test_zip_novo_ou_alterado_reescreve_so_o_mes_e_converte_so_o_membro(
    raw: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    lake = tmp_path / "lake"
    converter.convert(raw, lake)
    outro_mes = lake / SOURCE_ID / "empresas/ano=2026/mes=09/empresas_202609.parquet"
    mtime = outro_mes.stat().st_mtime_ns

    # A parte 1 de empresas de outubro muda; as partes 0 e 2 não.
    zip1 = raw / "2026-10/empresas/Empresas1@20261012.zip"
    _rewrite_zip(zip1, ['"00009999";"NOVA";"1";"2";"3";"4";"5"'])
    extraidos: list[str] = []
    original = lake_mod._Extractions.source

    def espiar(self, path, names):
        extraidos.append(path.name)
        return original(self, path, names)

    monkeypatch.setattr(lake_mod._Extractions, "source", espiar)
    res = converter.convert(raw, lake)

    assert not res.errors
    assert (res.converted, res.skipped) == (1, 11)
    assert extraidos == ["Empresas1@20261012.zip"]
    assert outro_mes.stat().st_mtime_ns == mtime
    df = (
        scan_dataset(lake / SOURCE_ID / "empresas")
        .filter(__import__("polars").col("mes") == "10")
        .collect()
    )
    assert df.height == 4 + 1 + 10  # partes 0 e 2 intactas, a 1 trocada (1 linha)
    assert "00009999" in df["cnpj_basico"].to_list()


def test_zip_que_sai_do_bruto_sai_do_arquivo_do_mes(raw: Path, tmp_path: Path) -> None:
    lake = tmp_path / "lake"
    converter.convert(raw, lake)
    (raw / "2026-10/socios/Socios1@20261012.zip").unlink()

    res = converter.convert(raw, lake)

    assert not res.errors and res.converted == 0
    arquivo = lake / SOURCE_ID / "socios/ano=2026/mes=10/socios_202610.parquet"
    assert sorted(_members(arquivo)) == ["Socios0"]
    assert scan_dataset(lake / SOURCE_ID / "socios").collect().height == 4


def test_migracao_do_layout_antigo_sem_duplicar_linhas(
    raw: Path, tmp_path: Path
) -> None:
    lake = tmp_path / "lake"
    _legacy_convert(raw, lake)
    antigos = _parquets(lake)
    assert len(antigos) == 12
    linhas_antes = {
        d: scan_dataset(lake / SOURCE_ID / d).collect().height
        for d in ("empresas", "estabelecimentos", "socios", "simples", "cnaes")
    }
    assert {p.name for p in antigos} >= {"Cnaes.parquet", "Empresas0.parquet"}

    res = converter.convert(raw, lake)

    assert not res.errors
    assert (res.converted, res.skipped) == (12, 0)
    novos = _parquets(lake)
    assert [p.name for p in novos] == [
        "cnaes_202609.parquet",
        "cnaes_202610.parquet",
        "empresas_202609.parquet",
        "empresas_202610.parquet",
        "estabelecimentos_202610.parquet",
        "simples_202610.parquet",
        "socios_202610.parquet",
    ]
    for dataset, linhas in linhas_antes.items():
        df = scan_dataset(lake / SOURCE_ID / dataset).collect()
        assert df.height == linhas, dataset  # nenhuma linha duplicada
    # Idempotente: a segunda passada não mexe em nada.
    assert converter.convert(raw, lake).skipped == 12
    assert contagem_de_arquivos(lake) == {
        d: {m: 1 for m in meses} for d, meses in contagem_de_arquivos(lake).items()
    }


def test_migracao_nao_apaga_parquet_que_o_grupo_nao_cobre(
    raw: Path, tmp_path: Path
) -> None:
    """Um Parquet antigo cujo ZIP não está mais no bruto não é apagado às cegas."""
    lake = tmp_path / "lake"
    _legacy_convert(raw, lake)
    orfao = lake / SOURCE_ID / "socios/ano=2026/mes=10/Socios1.parquet"
    assert orfao.exists()
    (raw / "2026-10/socios/Socios1@20261012.zip").unlink()

    res = converter.convert(raw, lake)

    assert not res.errors
    # O grupo só tem Socios0; o Parquet de Socios1 (linhas que o grupo não tem)
    # fica, e a auditoria é quem acusa o resíduo.
    assert orfao.exists()
    assert not (lake / SOURCE_ID / "socios/ano=2026/mes=10/Socios0.parquet").exists()


def test_auditoria_do_lake_agrupado(raw: Path, tmp_path: Path) -> None:
    # O lake_audit espera <fonte>/<pasta>/<arquivo> sob o diretório de entrada.
    entrada = tmp_path / "entrada"
    shutil.copytree(raw, entrada / SOURCE_ID)
    lake = tmp_path / "lake"
    res = converter.convert(entrada / SOURCE_ID, lake)
    assert not res.errors

    report = lake_audit(lake, input_dir=entrada, converters={}, rehash=True)

    assert report.ok, report.to_text()
    assert [f for f in report.findings if f.category == "membros_divergentes"] == []


def test_auditoria_do_lake_migrado(raw: Path, tmp_path: Path) -> None:
    entrada = tmp_path / "entrada"
    shutil.copytree(raw, entrada / SOURCE_ID)
    lake = tmp_path / "lake"
    _legacy_convert(entrada / SOURCE_ID, lake)
    converter.convert(entrada / SOURCE_ID, lake)

    report = lake_audit(lake, input_dir=entrada, converters={}, rehash=True)

    assert report.ok, report.to_text()


def test_extracao_nao_deixa_arquivos_e_so_uma_vive_por_vez(
    raw: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    vivas: list[int] = []
    original = lake_mod._Extractions.source

    def contar(self, path, names):
        saida = original(self, path, names)
        vivas.append(len(list(self.base.glob("rfb-cnpj-*"))))
        return saida

    monkeypatch.setattr(lake_mod._Extractions, "source", contar)
    scratch = tmp_path / "scratch"
    monkeypatch.setenv("QUANTILICA_LAKE_SCRATCH", str(scratch))
    lake = tmp_path / "lake"

    res = converter.convert(raw, lake)

    assert not res.errors
    assert vivas and set(vivas) == {1}  # nunca duas extrações ao mesmo tempo
    assert not any(scratch.rglob("rfb-cnpj-*"))
    assert not list(lake.rglob(".tmp"))


def test_extracao_limpa_mesmo_quando_o_mes_falha(raw: Path, tmp_path: Path) -> None:
    lake = tmp_path / "lake"
    # CSV com uma coluna a menos: o DuckDB preenche (null_padding), não falha;
    # um ZIP sem dado, sim.
    ruim = raw / "2026-10/socios/Socios1@20261012.zip"
    with zipfile.ZipFile(ruim, "w") as arquivo:
        arquivo.writestr("LEIA-ME.pdf", b"nada")

    res = converter.convert(raw, lake)

    assert len(res.errors) == 1 and res.errors[0].startswith("socios_202610:")
    assert "Socios1" in res.errors[0]
    assert not list(lake.rglob(".tmp"))
    # Os outros meses e datasets foram escritos.
    assert (
        lake / SOURCE_ID / "empresas/ano=2026/mes=10/empresas_202610.parquet"
    ).exists()
    assert not list((lake / SOURCE_ID / "socios").rglob("*.parquet"))


def test_so_a_safra_mais_recente_do_mesmo_zip_entra_no_grupo(
    raw: Path, tmp_path: Path
) -> None:
    antiga = raw / "2026-10/empresas/Empresas0@20261001.zip"
    _rewrite_zip(antiga, ['"00000042";"VELHA";"1";"2";"3";"4";"5"'])
    lake = tmp_path / "lake"

    res = converter.convert(raw, lake)

    assert not res.errors
    arquivo = lake / SOURCE_ID / "empresas/ano=2026/mes=10/empresas_202610.parquet"
    assert sorted(_members(arquivo)) == ["Empresas0", "Empresas1", "Empresas2"]
    nomes = scan_dataset(lake / SOURCE_ID / "empresas").collect()["razao_social"]
    assert "VELHA" not in nomes.to_list()


def test_csv_solto_continua_aceito(tmp_path: Path) -> None:
    raw = tmp_path / "raw" / "2026-10" / "cnaes"
    raw.mkdir(parents=True)
    (raw / "Cnaes@20261012.csv").write_bytes(b'"6201500";"Desenvolvimento"\n')

    res = converter.convert(tmp_path / "raw", tmp_path / "lake")

    assert not res.errors and res.converted == 1
    df = scan_dataset(tmp_path / "lake" / SOURCE_ID / "cnaes").collect()
    assert df["codigo"].to_list() == ["6201500"]
