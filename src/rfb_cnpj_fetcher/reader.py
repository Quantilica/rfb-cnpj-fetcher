"""Parsing of the RFB CNPJ open-data CSV files.

Every downloaded ZIP holds one CSV without header: Latin-1, ``;`` separator and
every field quoted (fields may contain ``;``, ``"`` and line breaks). The
column layout per group follows the Receita Federal metadata document
("Dados Abertos CNPJ - Metadados").

Conversions are strict. Codes (CNPJ parts, CNAE, natureza, município, país...)
stay as text, keeping their leading zeros. ``capital_social`` becomes an exact
``Decimal``. Dates (``AAAAMMDD``) become ``Date``; only the sentinels used by
the Receita for "no date" (``0``, ``00000000`` and empty) become null, and any
other invalid value raises. A row with a field count different from the
layout also raises, instead of shifting the columns.

Requires the ``analysis`` extra (``polars``).
"""

from __future__ import annotations

import io
import tempfile
import zipfile
from pathlib import Path

try:
    import polars as pl
    from quantilica.analytics.writer import to_parquet
except ImportError as exc:
    raise ImportError(
        "rfb_cnpj_fetcher.reader requer o extra 'analysis'. "
        "Instale com: uv add 'rfb-cnpj-fetcher[analysis]' "
        "--index https://index.quantilica.com/simple/"
    ) from exc

from quantilica.core.logging import get_logger

logger = get_logger(__name__)

ENCODING = "latin-1"
SEPARATOR = ";"
QUOTE_CHAR = '"'
# Valores que a Receita usa para "sem data"; qualquer outro valor fora de
# AAAAMMDD é erro de leitura, não nulo.
DATE_NULL_SENTINELS = ("", "0", "00000000")
CAPITAL_SOCIAL_DTYPE = pl.Decimal(precision=20, scale=2)

_DOMAIN_LAYOUT = ("codigo", "descricao")

LAYOUTS: dict[str, tuple[str, ...]] = {
    "empresas": (
        "cnpj_basico",
        "razao_social",
        "natureza_juridica",
        "qualificacao_responsavel",
        "capital_social",
        "porte_empresa",
        "ente_federativo_responsavel",
    ),
    "estabelecimentos": (
        "cnpj_basico",
        "cnpj_ordem",
        "cnpj_dv",
        "identificador_matriz_filial",
        "nome_fantasia",
        "situacao_cadastral",
        "data_situacao_cadastral",
        "motivo_situacao_cadastral",
        "nome_cidade_exterior",
        "pais",
        "data_inicio_atividade",
        "cnae_fiscal_principal",
        "cnae_fiscal_secundaria",
        "tipo_logradouro",
        "logradouro",
        "numero",
        "complemento",
        "bairro",
        "cep",
        "uf",
        "municipio",
        "ddd1",
        "telefone1",
        "ddd2",
        "telefone2",
        "ddd_fax",
        "fax",
        "correio_eletronico",
        "situacao_especial",
        "data_situacao_especial",
    ),
    "socios": (
        "cnpj_basico",
        "identificador_socio",
        "nome_socio",
        "cnpj_cpf_socio",
        "qualificacao_socio",
        "data_entrada_sociedade",
        "pais",
        "representante_legal",
        "nome_representante_legal",
        "qualificacao_representante_legal",
        "faixa_etaria",
    ),
    "simples": (
        "cnpj_basico",
        "opcao_simples",
        "data_opcao_simples",
        "data_exclusao_simples",
        "opcao_mei",
        "data_opcao_mei",
        "data_exclusao_mei",
    ),
    "cnaes": _DOMAIN_LAYOUT,
    "naturezas": _DOMAIN_LAYOUT,
    "qualificacoes": _DOMAIN_LAYOUT,
    "municipios": _DOMAIN_LAYOUT,
    "paises": _DOMAIN_LAYOUT,
    "motivos": _DOMAIN_LAYOUT,
}

DATE_COLUMNS: dict[str, tuple[str, ...]] = {
    "estabelecimentos": (
        "data_situacao_cadastral",
        "data_inicio_atividade",
        "data_situacao_especial",
    ),
    "socios": ("data_entrada_sociedade",),
    "simples": (
        "data_opcao_simples",
        "data_exclusao_simples",
        "data_opcao_mei",
        "data_exclusao_mei",
    ),
}

DECIMAL_COLUMNS: dict[str, dict[str, pl.Decimal]] = {
    "empresas": {"capital_social": CAPITAL_SOCIAL_DTYPE},
}


def group_from_path(path: Path) -> str:
    """Infer the group from the local layout ``<competencia>/<group>/<file>.zip``.

    Args:
        path: Path of a downloaded ZIP.

    Returns:
        str: The canonical group name (ex: ``"empresas"``).

    Raises:
        ValueError: If the parent directory is not a known group.
    """
    group = Path(path).parent.name
    if group not in LAYOUTS:
        raise ValueError(
            f"Grupo desconhecido '{group}' para {path}; informe group= "
            f"({', '.join(LAYOUTS)})"
        )
    return group


def _transcode_member(archive: zipfile.ZipFile, member: str, target: Path) -> None:
    """Stream a Latin-1 ZIP member into a UTF-8 file (Polars reads only UTF-8)."""
    with archive.open(member) as raw, target.open("wb") as out:
        text = io.TextIOWrapper(raw, encoding=ENCODING, newline="")
        while chunk := text.read(1 << 24):
            out.write(chunk.encode("utf-8"))


def _read_text_frame(path: Path, columns: tuple[str, ...]) -> pl.DataFrame:
    """Read the single CSV of a ZIP with every column as text."""
    with zipfile.ZipFile(path) as archive:
        members = [info.filename for info in archive.infolist() if not info.is_dir()]
        if len(members) != 1:
            raise ValueError(f"Esperado um único arquivo em {path}, achados {members}")
        with tempfile.TemporaryDirectory(prefix="rfb-cnpj-") as tmp:
            utf8 = Path(tmp) / "data.csv"
            _transcode_member(archive, members[0], utf8)
            # Ler por handle aberto, não por caminho: pelo caminho o Polars mapeia
            # o arquivo em memória e, no Windows, o temporário não pode ser
            # apagado enquanto o DataFrame existir.
            try:
                with utf8.open("rb") as handle:
                    df = pl.read_csv(
                        handle,
                        separator=SEPARATOR,
                        quote_char=QUOTE_CHAR,
                        has_header=False,
                        new_columns=list(columns),
                        schema=dict.fromkeys(columns, pl.Utf8),
                        encoding="utf8",
                    )
            except (pl.exceptions.SchemaError, pl.exceptions.ComputeError) as exc:
                raise ValueError(
                    f"{path}: linha com mais de {len(columns)} campos: {exc}"
                ) from exc
    # Todo campo vem entre aspas, então campo vazio é "" e nunca nulo: um nulo
    # aqui só aparece em linha com menos campos que o layout.
    short = df.filter(pl.any_horizontal(pl.all().is_null()))
    if short.height:
        raise ValueError(
            f"{path}: {short.height} linha(s) com menos de {len(columns)} campos"
        )
    return df


def _date_expr(column: str) -> pl.Expr:
    col = pl.col(column)
    return (
        pl.when(col.is_in(DATE_NULL_SENTINELS))
        .then(None)
        .otherwise(col)
        .str.to_date("%Y%m%d", strict=True)
        .alias(column)
    )


def _decimal_expr(column: str, dtype: pl.Decimal) -> pl.Expr:
    col = pl.col(column)
    return (
        pl.when(col == "")
        .then(None)
        .otherwise(col.str.replace(",", ".", literal=True))
        .cast(dtype, strict=True)
        .alias(column)
    )


def read_file(path: Path, group: str | None = None) -> pl.DataFrame:
    """Parse one downloaded CNPJ ZIP into a typed Polars DataFrame.

    Args:
        path: Path to a downloaded ``.zip`` (ex: ``Empresas0@20251012.zip``).
        group: Canonical group name; inferred from the parent directory when
            omitted.

    Returns:
        pl.DataFrame: One row per CSV record, columns named per ``LAYOUTS``.
        Codes are text, ``capital_social`` is ``Decimal(20, 2)``, date
        columns are ``Date`` and empty text fields are null.

    Raises:
        ValueError: On an unknown group, a ZIP with more than one file, a row
            with a field count different from the layout, a date that is
            neither ``AAAAMMDD`` nor a no-date sentinel, or a capital value
            that is not a number.
    """
    path = Path(path)
    group = group or group_from_path(path)
    if group not in LAYOUTS:
        raise ValueError(f"Grupo desconhecido: {group}")
    columns = LAYOUTS[group]
    df = _read_text_frame(path, columns)

    dates = DATE_COLUMNS.get(group, ())
    decimals = DECIMAL_COLUMNS.get(group, {})
    sentinels = {c: int(df[c].is_in(DATE_NULL_SENTINELS[1:]).sum() or 0) for c in dates}
    exprs = []
    for column in columns:
        if column in dates:
            exprs.append(_date_expr(column))
        elif column in decimals:
            exprs.append(_decimal_expr(column, decimals[column]))
        else:
            col = pl.col(column)
            exprs.append(pl.when(col == "").then(None).otherwise(col).alias(column))
    try:
        out = df.select(exprs)
    except (pl.exceptions.InvalidOperationError, pl.exceptions.ComputeError) as exc:
        raise ValueError(f"{path}: valor fora do layout de {group}: {exc}") from exc
    if any(sentinels.values()):
        logger.info("%s: datas sentinela anuladas %s", path.name, sentinels)
    return out


def write_parquet(
    df: pl.DataFrame,
    target: Path,
    *,
    source_path: Path | None = None,
) -> Path:
    """Write a DataFrame as Parquet (zstd) with optional provenance.

    Delegates to the canonical ``to_parquet`` from ``quantilica.analytics.writer``
    (atomic write-temp-rename); when the raw source file has a
    ``.manifest.json`` sidecar, the ``quantilica.*`` metadata are injected
    into the Parquet and a provenance sidecar is written next to the target.

    Args:
        df: The DataFrame to write.
        target: Destination path of the Parquet file.
        source_path: Optional raw source file, used to inject the manifest
            sidecar metadata.

    Returns:
        Path: The path of the written Parquet file.
    """
    return to_parquet(df, target, source_path=source_path)
