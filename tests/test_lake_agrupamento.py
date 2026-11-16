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
    check_dataset,
    scan_dataset,
)

import rfb_cnpj_fetcher.lake as lake_mod  # noqa: E402
from rfb_cnpj_fetcher.lake import SOURCE_ID, converter  # noqa: E402
from rfb_cnpj_fetcher.reader import LAYOUTS  # noqa: E402

from .lake_fixtures import (  # noqa: E402
    build_raw,
    contagem_de_arquivos,
    conversor_antigo,
    converter_com_o_antigo,
)


@pytest.fixture(scope="session")
def src_antigo(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """O conversor REAL de antes do agrupamento, extraído do commit pelo git."""
    src = conversor_antigo(tmp_path_factory.mktemp("conversor-antigo"))
    if src is None:
        pytest.skip("o commit do conversor antigo não existe neste clone")
    return src


@pytest.fixture
def legacy_convert(src_antigo: Path):
    """``legacy_convert(raw, lake)``: roda o conversor antigo de verdade."""

    def run(raw: Path, lake: Path) -> None:
        erros = converter_com_o_antigo(src_antigo, raw, lake)
        assert not erros, erros

    return run


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
    assert not res.errors and res.converted == 13 and res.skipped == 0

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
    assert converter.convert(raw, lake).converted == 13
    antes = {p: (p.stat().st_mtime_ns, p.stat().st_ino) for p in _parquets(lake)}

    def nao_extrair(self, path, names):
        raise AssertionError(f"extraiu {path.name} sem precisar")

    monkeypatch.setattr(lake_mod._Extractions, "source", nao_extrair)
    res = converter.convert(raw, lake)

    assert not res.errors
    assert (res.converted, res.skipped) == (0, 13)
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
    assert (res.converted, res.skipped) == (1, 12)
    assert extraidos == ["Empresas1@20261012.zip"]
    assert outro_mes.stat().st_mtime_ns == mtime
    df = (
        scan_dataset(lake / SOURCE_ID / "empresas")
        .filter(__import__("polars").col("mes") == "10")
        .collect()
    )
    assert df.height == 4 + 1 + 10  # partes 0 e 2 intactas, a 1 trocada (1 linha)
    assert "00009999" in df["cnpj_basico"].to_list()


def test_zip_que_some_da_visao_nao_apaga_dados_do_mes(
    raw: Path, tmp_path: Path
) -> None:
    lake = tmp_path / "lake"
    converter.convert(raw, lake)
    arquivo = lake / SOURCE_ID / "socios/ano=2026/mes=10/socios_202610.parquet"
    antes = (arquivo.stat().st_mtime_ns, arquivo.read_bytes())
    zip1 = raw / "2026-10/socios/Socios1@20261012.zip"
    guardado = tmp_path / "guardado.zip"
    shutil.move(zip1, guardado)

    res = converter.convert(raw, lake)

    # O mês fica intacto e o resultado acusa; os outros meses seguem normalmente.
    assert len(res.errors) == 1
    assert res.errors[0].startswith("socios_202610: mês incompleto: faltam Socios1")
    assert (arquivo.stat().st_mtime_ns, arquivo.read_bytes()) == antes
    assert sorted(_members(arquivo)) == ["Socios0", "Socios1"]
    assert scan_dataset(lake / SOURCE_ID / "socios").collect().height == 4 + 7
    assert res.converted == 0

    # Com o ZIP de volta a execução seguinte converge, sem erro nem reescrita.
    shutil.move(guardado, zip1)
    res = converter.convert(raw, lake)
    assert not res.errors and res.converted == 0
    assert (arquivo.stat().st_mtime_ns, arquivo.read_bytes()) == antes


def test_zip_que_some_da_visao_nao_impede_os_outros_meses(
    raw: Path, tmp_path: Path
) -> None:
    lake = tmp_path / "lake"
    converter.convert(raw, lake)
    (raw / "2026-10/socios/Socios1@20261012.zip").unlink()
    _rewrite_zip(
        raw / "2026-10/empresas/Empresas1@20261012.zip",
        ['"00009999";"NOVA";"1";"2";"3";"4";"5"'],
    )

    res = converter.convert(raw, lake)

    assert len(res.errors) == 1 and res.converted == 1


def test_migracao_do_layout_antigo_sem_duplicar_linhas(
    raw: Path, tmp_path: Path, legacy_convert
) -> None:
    lake = tmp_path / "lake"
    legacy_convert(raw, lake)
    antigos = _parquets(lake)
    assert len(antigos) == 13
    linhas_antes = {
        d: scan_dataset(lake / SOURCE_ID / d).collect().height
        for d in ("empresas", "estabelecimentos", "socios", "simples", "cnaes")
    }
    assert {p.name for p in antigos} >= {"Cnaes.parquet", "Empresas0.parquet"}

    res = converter.convert(raw, lake)

    assert not res.errors
    assert (res.converted, res.skipped) == (13, 0)
    novos = _parquets(lake)
    assert [p.name for p in novos] == [
        "cnaes_202609.parquet",
        "cnaes_202610.parquet",
        "empresas_202608.parquet",
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
    assert converter.convert(raw, lake).skipped == 13
    assert contagem_de_arquivos(lake) == {
        d: {m: 1 for m in meses} for d, meses in contagem_de_arquivos(lake).items()
    }


def test_migracao_nao_apaga_parquet_que_o_grupo_nao_cobre_e_acusa(
    raw: Path, tmp_path: Path, legacy_convert
) -> None:
    """Parquet antigo de um ZIP que não está na visão fica, e o resultado acusa."""
    lake = tmp_path / "lake"
    legacy_convert(raw, lake)
    orfao = lake / SOURCE_ID / "socios/ano=2026/mes=10/Socios1.parquet"
    assert orfao.exists()
    (raw / "2026-10/socios/Socios1@20261012.zip").unlink()

    res = converter.convert(raw, lake)

    assert len(res.errors) == 1
    assert "Socios1.parquet" in res.errors[0] and "duplicadas" in res.errors[0]
    assert orfao.exists()
    assert not (lake / SOURCE_ID / "socios/ano=2026/mes=10/Socios0.parquet").exists()


def test_safra_nova_do_zip_acusa_o_parquet_antigo_que_ficou(
    raw: Path, tmp_path: Path, legacy_convert
) -> None:
    """Lake antigo com ``Empresas0`` de uma safra; a visão traz outra."""
    lake = tmp_path / "lake"
    legacy_convert(raw, lake)
    antigo = raw / "2026-10/empresas/Empresas0@20261012.zip"
    antigo.rename(antigo.with_name("Empresas0@20261101.zip"))
    _rewrite_zip(
        antigo.with_name("Empresas0@20261101.zip"),
        ['"00000777";"SAFRA NOVA";"1";"2";"3";"4";"5"'],
    )

    res = converter.convert(raw, lake)

    assert len(res.errors) == 1
    assert "empresas_202610" in res.errors[0] and "Empresas0.parquet" in res.errors[0]
    antigos = lake / SOURCE_ID / "empresas/ano=2026/mes=10/Empresas0.parquet"
    assert antigos.exists()  # a decisão de apagar é de quem lê o aviso


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


def test_auditoria_do_lake_migrado(raw: Path, tmp_path: Path, legacy_convert) -> None:
    entrada = tmp_path / "entrada"
    shutil.copytree(raw, entrada / SOURCE_ID)
    lake = tmp_path / "lake"
    legacy_convert(entrada / SOURCE_ID, lake)
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
        vivas.append(len(list(self.base.glob("lake-work-*"))))
        return saida

    monkeypatch.setattr(lake_mod._Extractions, "source", contar)
    scratch = tmp_path / "scratch"
    monkeypatch.setenv("QUANTILICA_LAKE_SCRATCH", str(scratch))
    lake = tmp_path / "lake"

    res = converter.convert(raw, lake)

    assert not res.errors
    assert vivas and set(vivas) == {1}  # nunca duas extrações ao mesmo tempo
    assert not any(scratch.rglob("lake-work-*"))
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


def test_linha_irregular_nao_cria_colunas_alem_do_layout(
    raw: Path, tmp_path: Path
) -> None:
    """Linha com campos a mais (ou a menos) não vira ``column7`` no Parquet."""
    lake = tmp_path / "lake"
    res = converter.convert(raw, lake)
    assert not res.errors
    arquivo = lake / SOURCE_ID / "empresas/ano=2026/mes=08/empresas_202608.parquet"
    assert pq.ParquetFile(arquivo).schema_arrow.names == [
        *LAYOUTS["empresas"],
        "_origem",
    ]
    df = (
        scan_dataset(lake / SOURCE_ID / "empresas")
        .filter(__import__("polars").col("mes") == "08")
        .collect()
    )
    por_cnpj = {r["cnpj_basico"]: r for r in df.iter_rows(named=True)}
    assert por_cnpj["00000013"]["ente_federativo_responsavel"] in (
        None,
        "",
    )  # extras cortados
    assert por_cnpj["00000012"]["porte_empresa"] in (None, "")  # curta, preenchida
    assert por_cnpj["00000010"]["razao_social"] == "SEM ASPAS LTDA"


def _corromper(path: Path) -> None:
    dados = path.read_bytes()
    path.write_bytes(dados[: len(dados) // 2])


@pytest.mark.parametrize("como", ["truncado", "lixo"])
def test_zip_corrompido_e_erro_do_mes_e_o_resto_segue(
    raw: Path, tmp_path: Path, como: str
) -> None:
    lake = tmp_path / "lake"
    ruim = raw / "2026-10/socios/Socios1@20261012.zip"
    if como == "truncado":
        _corromper(ruim)
    else:
        ruim.write_bytes(b"isto nao e um zip")

    res = converter.convert(raw, lake)

    assert len(res.errors) == 1 and res.errors[0].startswith("socios_202610:")
    assert not list((lake / SOURCE_ID / "socios").rglob("*.parquet"))
    assert not list(lake.rglob(".tmp"))
    # Os demais meses e datasets foram escritos.
    assert res.converted == 13 - 2  # socios (2 ZIPs) ficou de fora
    assert (
        lake / SOURCE_ID / "empresas/ano=2026/mes=10/empresas_202610.parquet"
    ).exists()


def test_zip_corrompido_nao_toca_o_mes_ja_publicado(raw: Path, tmp_path: Path) -> None:
    lake = tmp_path / "lake"
    converter.convert(raw, lake)
    arquivo = lake / SOURCE_ID / "socios/ano=2026/mes=10/socios_202610.parquet"
    antes = arquivo.read_bytes()
    ruim = raw / "2026-10/socios/Socios1@20261012.zip"
    _corromper(ruim)

    res = converter.convert(raw, lake)

    assert len(res.errors) == 1
    assert arquivo.read_bytes() == antes


def test_erro_de_hash_e_erro_do_mes(
    raw: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from quantilica.core.exceptions import StorageError

    original = lake_mod.sha256_file

    def falha(path, *args, **kwargs):
        if path.name.startswith("Simples"):
            raise StorageError("disco com defeito")
        return original(path, *args, **kwargs)

    monkeypatch.setattr(lake_mod, "sha256_file", falha)
    res = converter.convert(raw, tmp_path / "lake")

    assert [e.split(":")[0] for e in res.errors] == ["simples_202610"]
    assert res.converted == 12


def test_mesmo_zip_nos_dois_layouts_do_bruto_entra_uma_vez(
    raw: Path, tmp_path: Path
) -> None:
    atual = raw / "2026-10/empresas/Empresas0@20261012.zip"
    outro = raw / "empresas" / "empresas_0_2026-10@20261012.zip"
    outro.parent.mkdir(parents=True)
    shutil.copy(atual, outro)
    lake = tmp_path / "lake"

    res = converter.convert(raw, lake)

    assert not res.errors and res.converted == 13  # a cópia não conta
    arquivo = lake / SOURCE_ID / "empresas/ano=2026/mes=10/empresas_202610.parquet"
    assert sorted(_members(arquivo)) == ["Empresas0", "Empresas1", "Empresas2"]
    assert (
        scan_dataset(lake / SOURCE_ID / "empresas")
        .filter(__import__("polars").col("mes") == "10")
        .collect()
        .height
        == 4 + 7 + 10
    )
    # E segue estável quando a visão troca de layout entre execuções.
    outro.parent.joinpath(outro.name).rename(
        outro.with_name("empresas_0_2026-10@20261012.zip")
    )
    assert not converter.convert(raw, lake).errors


def test_carimbo_mais_recente_vence_e_empate_fica_com_o_layout_atual(
    raw: Path, tmp_path: Path
) -> None:
    outro = raw / "empresas" / "empresas_0_2026-10@20261020.zip"
    outro.parent.mkdir(parents=True)
    _rewrite_zip(outro, ['"00000555";"CARIMBO NOVO";"1";"2";"3";"4";"5"'])
    lake = tmp_path / "lake"
    converter.convert(raw, lake)
    df = scan_dataset(lake / SOURCE_ID / "empresas").collect()
    assert "CARIMBO NOVO" in df["razao_social"].to_list()

    empate = raw / "empresas" / "empresas_0_2026-09@20260912.zip"
    _rewrite_zip(empate, ['"00000556";"OUTRO LAYOUT";"1";"2";"3";"4";"5"'])
    converter.convert(raw, tmp_path / "lake2")
    df = scan_dataset(tmp_path / "lake2" / SOURCE_ID / "empresas").collect()
    nomes = df.filter(df["mes"] == "09")["razao_social"].to_list()
    assert "OUTRO LAYOUT" not in nomes  # o layout atual (Empresas0@20261012) fica


def test_correcao_de_parte_e_outro_membro_nao_substitui_o_original(
    tmp_path: Path,
) -> None:
    raw = tmp_path / "raw" / "2026-10" / "estabelecimentos"
    raw.mkdir(parents=True)
    linha = ['"00000001";"1";"2";' + ";".join(['"x"'] * 29)]
    _rewrite_zip(raw / "Estabelecimentos6@20261012.zip", linha)
    _rewrite_zip(raw / "Estabelecimentos6-RF0819000032530@20261012.zip", linha)

    res = converter.convert(tmp_path / "raw", tmp_path / "lake")

    assert not res.errors and res.converted == 2


def test_safras_misturadas_vao_para_o_log(
    raw: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    avisos: list[str] = []
    monkeypatch.setattr(
        lake_mod.logger, "warning", lambda msg, *args: avisos.append(msg % args)
    )
    antigo = raw / "2026-10/empresas/Empresas1@20261012.zip"
    antigo.rename(antigo.with_name("Empresas1@20261001.zip"))

    converter.convert(raw, tmp_path / "lake")

    assert any("empresas" in a and "different harvests" in a for a in avisos)


def _manifesto(path: Path, *, sha: str, size: int) -> None:
    path.with_name(path.name + ".manifest.json").write_text(
        json.dumps({"sha256": sha, "size_bytes": size}), encoding="utf-8"
    )


def test_sha_do_manifesto_evita_reler_o_zip(
    raw: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from quantilica.core.files import sha256_file

    for zip_ in raw.rglob("*.zip"):
        _manifesto(zip_, sha=sha256_file(zip_), size=zip_.stat().st_size)
    chamadas: list[str] = []
    original = lake_mod.sha256_file
    monkeypatch.setattr(
        lake_mod,
        "sha256_file",
        lambda p, *a, **k: chamadas.append(p.name) or original(p, *a, **k),
    )
    lake = tmp_path / "lake"

    res = converter.convert(raw, lake)

    assert not res.errors and chamadas == []
    arquivo = lake / SOURCE_ID / "socios/ano=2026/mes=10/socios_202610.parquet"
    shas = {m["origin_sha256"] for m in _members(arquivo).values()}
    assert shas == {
        sha256_file(raw / f"2026-10/socios/Socios{i}@20261012.zip") for i in (0, 1)
    }
    assert converter.convert(raw, lake).skipped == 13 and chamadas == []


def test_manifesto_que_nao_bate_com_o_arquivo_e_ignorado(
    raw: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    zip_ = raw / "2026-10/simples/Simples@20261012.zip"
    _manifesto(zip_, sha="0" * 64, size=zip_.stat().st_size + 1)  # tamanho errado
    sem_tamanho = raw / "2026-10/cnaes/Cnaes@20261012.zip"
    _manifesto(sem_tamanho, sha="1" * 64, size=0)
    chamadas: list[str] = []
    original = lake_mod.sha256_file
    monkeypatch.setattr(
        lake_mod,
        "sha256_file",
        lambda p, *a, **k: chamadas.append(p.name) or original(p, *a, **k),
    )

    converter.convert(raw, tmp_path / "lake")

    assert "Simples@20261012.zip" in chamadas and "Cnaes@20261012.zip" in chamadas
    assert lake_mod.known_sha256(zip_) is None


def test_csv_solto_com_byte_c1_e_transcodificado(tmp_path: Path) -> None:
    raw = tmp_path / "raw" / "2026-10" / "cnaes"
    raw.mkdir(parents=True)
    (raw / "Cnaes@20261012.csv").write_bytes(b'"6201500";"DESCRI\x85AO"\n')

    res = converter.convert(tmp_path / "raw", tmp_path / "lake")

    assert not res.errors and res.converted == 1
    df = scan_dataset(tmp_path / "lake" / SOURCE_ID / "cnaes").collect()
    assert df["descricao"].to_list() == ["DESCRI\x85AO"]


def test_pasta_de_extracao_tem_o_prefixo_e_o_dono_do_analytics(
    raw: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    vistas: list[dict] = []
    original = lake_mod._Extractions.source

    def espiar(self, path, names):
        saida = original(self, path, names)
        pasta = next(self.base.glob("lake-work-*"))
        vistas.append(json.loads((pasta / "owner.json").read_text()))
        return saida

    monkeypatch.setattr(lake_mod._Extractions, "source", espiar)
    converter.convert(raw, tmp_path / "lake")

    import os

    assert vistas and all(v["pid"] == os.getpid() and v["hostname"] for v in vistas)
