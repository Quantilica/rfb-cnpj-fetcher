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
gerado com o conversor de um Parquet por ZIP, antes do agrupamento:

    uv run --no-sync python -m tests.lake_fixtures --escrever-golden
"""

from __future__ import annotations

import json
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import Any

from rfb_cnpj_fetcher.reader import LAYOUTS

GOLDEN = Path(__file__).parent / "golden" / "lake_antes_do_agrupamento.json"

# (pasta do mês, dataset, partes). ``None`` é o arquivo único, sem número.
PLANO: list[tuple[str, str, list[int | None]]] = [
    ("2026-09", "empresas", [0, 1]),
    ("2026-09", "cnaes", [None]),
    ("2026-10", "empresas", [0, 1, 2]),
    ("2026-10", "estabelecimentos", [0, 1]),
    ("2026-10", "socios", [0, 1]),
    ("2026-10", "simples", [None]),
    ("2026-10", "cnaes", [None]),
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


def build_raw(root: Path) -> list[Path]:
    """Cria os ZIPs sob ``root/<AAAA-MM>/<dataset>/`` e devolve os caminhos."""
    caminhos = []
    for mes, dataset, partes in PLANO:
        for parte in partes:
            n = 4 + (parte or 0) * 3
            conteudo = "\n".join(_linhas(dataset, parte, mes, n)).encode("latin-1")
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


def _escrever_golden() -> None:
    from rfb_cnpj_fetcher.lake import converter

    with tempfile.TemporaryDirectory(prefix="rfb-golden-") as tmp:
        raiz = Path(tmp)
        build_raw(raiz / "raw")
        resultado = converter.convert(raiz / "raw", raiz / "lake")
        assert not resultado.errors, resultado.errors
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
