"""Brutos sintéticos da Receita e retrato do lake, para as provas de equivalência.

``build_raw`` monta, em dois meses, ZIPs no formato real (CSV sem cabeçalho,
Latin-1, ``;``, todos os campos entre aspas, membro sem extensão ``.csv``) com
partes numeradas (``Empresas0``, ``Empresas1``...) e datasets de um arquivo só.
O conteúdo é determinístico e inclui o que costuma quebrar um leitor: apóstrofo,
aspas dobradas, quebra de linha entre aspas, ponto e vírgula dentro do campo,
acentos Latin-1 e um byte C1 (0x85) que o DuckDB não decodifica como Latin-1.

``snapshot`` descreve o lake lido por ``scan_dataset``: por dataset e período, o
número de linhas, as colunas com tipo e o conteúdo ordenado (sem ``_origem``,
que só existe no layout agrupado). ``golden/lake_antes_do_agrupamento.json`` foi
gerado com o conversor de um Parquet por ZIP, antes do agrupamento (o código é
extraído do commit ``COMMIT_ANTES`` e roda em outro processo):

    uv run --no-sync python -m tests.lake_fixtures --escrever-golden
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import Any

from rfb_cnpj_fetcher.reader import LAYOUTS

GOLDEN = Path(__file__).parent / "golden" / "lake_antes_do_agrupamento.json"
RAIZ_DO_REPO = Path(__file__).parents[1]
# Último commit com o conversor de um Parquet por ZIP (``main`` antes do agrupamento).
COMMIT_ANTES = "c593e2249c0feb9d6915bf97984ad63d7d1446d4"

# (pasta do mês, dataset, partes). ``None`` é o arquivo único, sem número.
PLANO: list[tuple[str, str, list[int | None]]] = [
    ("2026-09", "empresas", [0, 1]),
    ("2026-09", "cnaes", [None]),
    ("2026-10", "empresas", [0, 1, 2]),
    ("2026-10", "estabelecimentos", [0, 1]),
    ("2026-10", "socios", [0, 1]),
    ("2026-10", "simples", [None]),
    ("2026-10", "cnaes", [None]),
    ("2026-08", "empresas", [0]),  # com linhas irregulares (ver ``_irregulares``)
]

NOME = {
    "empresas": "Empresas",
    "estabelecimentos": "Estabelecimentos",
    "socios": "Socios",
    "simples": "Simples",
    "cnaes": "Cnaes",
}

# Campos que quebram leitores ingênuos, sorteados por linha.
_ESPECIAIS = [
    "D'AGUA COMERCIO LTDA",
    'BAR "DO ZE" O\'NEIL',
    "RUA A;B (ponto e vírgula)",
    "LINHA UM\nLINHA DOIS",
    "AÇÚCAR E ÁLCOOL S/A",
    "CTRL\x85C1",
    "",
]


def _linha(*campos: str) -> str:
    return ";".join('"' + c.replace('"', '""') + '"' for c in campos)


def _linhas(dataset: str, parte: int | None, mes: str, n: int) -> list[str]:
    colunas = LAYOUTS[dataset]
    saida = []
    for i in range(n):
        campos = []
        for j, nome in enumerate(colunas):
            if j == 0:
                campos.append(f"{(parte or 0) * 1000 + i:08d}")
            elif (i + j) % 5 == 0:
                campos.append(_ESPECIAIS[(i * 3 + j + (parte or 0)) % len(_ESPECIAIS)])
            else:
                campos.append(f"{nome[:6]}-{mes}-{parte}-{i}")
        saida.append(_linha(*campos))
    return saida


def _irregulares() -> list[str]:
    """Linhas fora do padrão que a Receita já publicou ou pode publicar."""
    return [
        # Sem aspas em nenhum campo.
        "00000010;SEM ASPAS LTDA;2062;49;1000,00;01;",
        # Aspas só em alguns campos.
        '00000011;"MISTA SA";2062;49;"5,00";01;',
        # Linha curta: faltam campos.
        _linha("00000012", "LINHA CURTA", "2062"),
        # Linha longa: campos a mais além dos sete do layout.
        _linha("00000013", "LINHA LONGA", "2062", "49", "1,00", "01", "", "EXTRA", "X"),
        _linha("00000014", "NORMAL", "2062", "49", "1,00", "01", ""),
    ]


def build_raw(root: Path) -> list[Path]:
    """Cria os ZIPs sob ``root/<AAAA-MM>/<dataset>/`` e devolve os caminhos."""
    caminhos = []
    for mes, dataset, partes in PLANO:
        for parte in partes:
            n = 4 + (parte or 0) * 3
            linhas = _linhas(dataset, parte, mes, n)
            if mes == "2026-08":
                linhas = _irregulares()
            conteudo = "\n".join(linhas).encode("latin-1")
            nome = f"{NOME[dataset]}{'' if parte is None else parte}@{mes[:4]}{mes[5:]}12.zip"
            path = root / mes / dataset / nome
            path.parent.mkdir(parents=True, exist_ok=True)
            with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as arquivo:
                # Como no download real: o membro não termina em .csv/.txt.
                arquivo.writestr(
                    f"K3241.K03200Y0.D60911.{dataset[:5].upper()}CSV", conteudo
                )
            caminhos.append(path)
    return caminhos


def snapshot(lake_dir: Path) -> dict[str, Any]:
    """Retrato do lake por dataset e período, independente do layout dos arquivos."""
    import polars as pl
    from quantilica.analytics.lake import ORIGIN_COLUMN, scan_dataset

    saida: dict[str, Any] = {}
    base = lake_dir / "rfb-cnpj"
    for dataset in sorted(p.name for p in base.iterdir() if p.is_dir()):
        frame = scan_dataset(base / dataset).collect()
        if ORIGIN_COLUMN in frame.columns:
            frame = frame.drop(ORIGIN_COLUMN)
        periodos: dict[str, Any] = {}
        for (ano, mes), parte in frame.group_by(["ano", "mes"], maintain_order=True):
            dados = parte.drop(["ano", "mes"])
            linhas = sorted(
                (["" if v is None else str(v) for v in row] for row in dados.rows()),
            )
            periodos[f"{ano}-{mes}"] = {
                "linhas": dados.height,
                "colunas": [[c, str(t)] for c, t in dados.schema.items()],
                "conteudo": linhas,
            }
        saida[dataset] = {
            "colunas": [
                [c, str(t)] for c, t in frame.schema.items() if c not in ("ano", "mes")
            ]
            + [[c, str(frame.schema[c])] for c in ("ano", "mes")],
            "periodos": dict(sorted(periodos.items())),
        }
        assert all(isinstance(t, pl.DataType) for t in frame.schema.values())
    return saida


def contagem_de_arquivos(lake_dir: Path) -> dict[str, dict[str, int]]:
    """Parquets por dataset e mês (``AAAA-MM``): o que a mudança reduz."""
    base = lake_dir / "rfb-cnpj"
    saida: dict[str, dict[str, int]] = {}
    for dataset in sorted(p.name for p in base.iterdir() if p.is_dir()):
        meses: dict[str, int] = {}
        for arquivo in sorted((base / dataset).rglob("*.parquet")):
            ano = arquivo.parent.parent.name.split("=")[1]
            mes = arquivo.parent.name.split("=")[1]
            meses[f"{ano}-{mes}"] = meses.get(f"{ano}-{mes}", 0) + 1
        saida[dataset] = meses
    return saida


def conversor_antigo(destino: Path) -> Path | None:
    """Extrai de ``COMMIT_ANTES`` o código do conversor de um Parquet por ZIP.

    Devolve o ``src`` extraído, ou ``None`` se o commit não existe neste clone
    (clone raso, por exemplo): os testes que dependem dele são pulados.
    """
    git = subprocess.run(
        ["git", "-C", str(RAIZ_DO_REPO), "archive", COMMIT_ANTES, "src"],
        capture_output=True,
    )
    if git.returncode != 0:
        return None
    destino.mkdir(parents=True, exist_ok=True)
    tar = subprocess.run(["tar", "-x", "-C", str(destino)], input=git.stdout)
    return destino / "src" if tar.returncode == 0 else None


def converter_com_o_antigo(src_antigo: Path, raw: Path, lake: Path) -> list[str]:
    """Roda o conversor ANTIGO (por caminho, em outro processo) e devolve os erros."""
    codigo = (
        "import sys, json, rfb_cnpj_fetcher as m\n"
        f"assert m.__file__.startswith({str(src_antigo)!r}), m.__file__\n"
        "from pathlib import Path\n"
        "from rfb_cnpj_fetcher.lake import converter\n"
        f"r = converter.convert(Path({str(raw)!r}), Path({str(lake)!r}))\n"
        "print(json.dumps(r.errors))\n"
    )
    env = {**os.environ, "PYTHONPATH": str(src_antigo)}
    saida = subprocess.run(
        [sys.executable, "-c", codigo],
        capture_output=True,
        text=True,
        env=env,
        cwd=src_antigo.parent,
        check=True,
    )
    return json.loads(saida.stdout.strip().splitlines()[-1])


def _escrever_golden() -> None:
    with tempfile.TemporaryDirectory(prefix="rfb-golden-") as tmp:
        raiz = Path(tmp)
        src = conversor_antigo(raiz / "antigo")
        assert src is not None, f"commit {COMMIT_ANTES} ausente neste clone"
        build_raw(raiz / "raw")
        erros = converter_com_o_antigo(src, raiz / "raw", raiz / "lake")
        assert not erros, erros
        GOLDEN.parent.mkdir(parents=True, exist_ok=True)
        GOLDEN.write_text(
            json.dumps(
                {
                    "contagem_de_arquivos": contagem_de_arquivos(raiz / "lake"),
                    "lake": snapshot(raiz / "lake"),
                },
                ensure_ascii=False,
                indent=1,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
    print(f"golden escrito em {GOLDEN}")


if __name__ == "__main__":
    if "--escrever-golden" not in sys.argv:
        raise SystemExit(__doc__)
    _escrever_golden()
