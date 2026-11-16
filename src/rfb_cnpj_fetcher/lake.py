"""Convert raw RFB CNPJ ZIP archives into the Hive-partitioned lake.

The ZIPs of one dataset and month (``Empresas0`` to ``Empresas9``, or the single
``Simples``) become ONE Parquet, ``<lake>/rfb-cnpj/<dataset>/ano=<ano>/mes=<mes>/
<dataset>_<AAAAMM>.parquet`` (e.g. ``empresas_202610.parquet``). The part of the
ZIP has no business meaning, so there is no column for it: each row carries only
``_origem`` (the file key of its ZIP, e.g. ``Empresas3``) and the footer lists
every ZIP with its sha256 and row count (``quantilica.members``). Files have no
header and are encoded in Latin-1 with ``;`` delimiter; column names come from the
official Receita Federal layout (``rfb_cnpj_fetcher.reader.LAYOUTS``).

A month is written in a single streaming pass (``estabelecimentos`` is about 3 GB
of Parquet): each ZIP is extracted, read by DuckDB straight from the CSV and
staged as Parquet, and its extraction is removed before the next one starts.
"""

from __future__ import annotations

import os
import re
import shutil
import tempfile
import zipfile
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Any

try:
    import duckdb
    from quantilica.analytics.lake import (
        DuckSource,
        GroupMember,
        LakeError,
        LakeWriter,
    )
    from quantilica.core.files import sha256_file
    from quantilica.core.lake import DatasetDescriptor, file_key, partition_types_for
except ImportError as exc:
    raise ImportError(
        "rfb_cnpj_fetcher.lake requer o extra 'analysis': "
        "uv add 'rfb-cnpj-fetcher[analysis]' "
        "--index https://index.quantilica.com/simple/"
    ) from exc

from rfb_cnpj_fetcher import __version__
from rfb_cnpj_fetcher.catalog import _GROUP_PATTERNS
from rfb_cnpj_fetcher.reader import LAYOUTS

SOURCE_ID = "rfb-cnpj"
PARTITION_KEYS = ["ano", "mes"]
PARTITION_TYPES = partition_types_for(PARTITION_KEYS)

# Versions recorded in each member's entry of the footer. The month is
# reconverted when either changes: bump CONTRACT_VERSION when LAYOUTS change
# (names, order) and CONVERTER_VERSION when the way the CSV is read changes.
CONTRACT_VERSION = 1
CONVERTER_VERSION = "1"

LAKE_SCRATCH_ENV = "QUANTILICA_LAKE_SCRATCH"
_TEXT_SUFFIXES = {".csv", ".txt"}
# Members of a ZIP that are not data (the real ZIPs hold a single CSV-like file).
_NOT_DATA_SUFFIXES = {
    ".pdf", ".doc", ".docx", ".md", ".html", ".htm", ".xml", ".json", ".xls", ".xlsx",
    ".png", ".jpg", ".jpeg",
}  # fmt: skip
_NOT_DATA_NAME = re.compile(r"^(leia-?me|readme|licen[cs]e)", re.IGNORECASE)
_C1_BYTES = re.compile(rb"[\x80-\x9f]")

_COMPETENCIA = re.compile(r"^\d{4}-\d{2}$")
_COMPETENCIA_IN_FILENAME = re.compile(r"_(?P<ano>\d{4})-(?P<mes>\d{2})(?:@|$)")
_STAMP = re.compile(r"@(?P<ano>\d{4})(?P<mes>\d{2})\d{2}")


@dataclass
class ConvertResult:
    """Counts of a conversion run; ``errors`` holds one message per failure."""

    converted: int = 0
    skipped: int = 0
    errors: list[str] = field(default_factory=list)


def infer_group(path: Path) -> str | None:
    """Infer group from parent folder or filename."""
    parent_name = path.parent.name.lower()
    if parent_name in LAYOUTS:
        return parent_name
    for group, pattern in _GROUP_PATTERNS.items():
        if pattern.search(path.name):
            return group
    # Check if slug before competencia matches a layout (e.g. empresas_0_2025-07)
    clean = re.sub(r"_\d{4}-\d{2}(?:@\d+)?.*$", "", path.name.lower())
    clean_no_idx = re.sub(r"_\d+$", "", clean)
    if clean_no_idx in LAYOUTS:
        return clean_no_idx
    return None


def infer_partitions(path: Path) -> dict[str, Any] | None:
    """Infer ``ano`` and ``mes`` partition values from folder structure or filename."""
    # Check filename for _YYYY-MM
    match = _COMPETENCIA_IN_FILENAME.search(path.name)
    if match:
        return {"ano": int(match["ano"]), "mes": match["mes"]}
    # Check parent and grandparent for YYYY-MM
    for parent in (path.parent, path.parent.parent):
        if _COMPETENCIA.match(parent.name):
            ano, mes = parent.name.split("-")
            return {"ano": int(ano), "mes": mes}
    # Check @YYYYMMDD stamp in filename
    match = _STAMP.search(path.name)
    if match:
        return {"ano": int(match["ano"]), "mes": match["mes"]}
    return None


def _lit(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def _data_members(names: list[str]) -> list[str]:
    """Members of a ZIP that hold data: text files if any, else all but documents."""
    candidates = [
        n
        for n in names
        if not n.endswith("/")
        and not PurePosixPath(n).name.startswith(".")
        and "__MACOSX" not in PurePosixPath(n).parts
    ]
    text = [n for n in candidates if PurePosixPath(n).suffix.lower() in _TEXT_SUFFIXES]
    if text:
        return sorted(text)
    return sorted(
        n
        for n in candidates
        if PurePosixPath(n).suffix.lower() not in _NOT_DATA_SUFFIXES
        and not _NOT_DATA_NAME.match(PurePosixPath(n).name)
    )


def _has_c1_bytes(path: Path) -> bool:
    """Whether ``path`` has a byte in 0x80-0x9F, which DuckDB's Latin-1 rejects."""
    with open(path, "rb") as fh:
        while chunk := fh.read(1 << 24):
            if _C1_BYTES.search(chunk):
                return True
    return False


def _to_utf8(files: list[Path], folder: Path) -> list[Path]:
    """UTF-8 copies of Latin-1 ``files`` (Python maps every byte; DuckDB does not)."""
    folder.mkdir(parents=True, exist_ok=True)
    out = []
    for i, src in enumerate(files):
        dst = folder / f"{i:04d}-{src.name}"
        with (
            open(src, encoding="latin-1", newline="") as reader,
            open(dst, "w", encoding="utf-8", newline="") as writer,
        ):
            shutil.copyfileobj(reader, writer, 1 << 24)
        out.append(dst)
    return out


def read_csv_sql(files: list[Path], names: tuple[str, ...], encoding: str) -> str:
    """The DuckDB ``SELECT`` that reads the files of one raw ZIP, all as text."""
    args = [
        "[" + ", ".join(_lit(str(f)) for f in files) + "]",
        "delim=';'",
        "header=false",
        "all_varchar=true",
        f"encoding={_lit(encoding)}",
        "null_padding=true",
        "strict_mode=false",
        "comment=''",
        # Campos entre aspas duplas; sem isto o DuckDB pode detectar o apóstrofo
        # de uma razão social como escape e abortar.
        "quote='\"'",
        "escape='\"'",
        # Há complementos de endereço com quebra de linha entre aspas, que o
        # leitor paralelo do DuckDB não aceita.
        "parallel=false",
        "names=[" + ", ".join(_lit(n) for n in names) + "]",
    ]
    return f"SELECT * FROM read_csv({', '.join(args)})"


class _Extractions:
    """Extracts one raw file at a time into a folder of its own, removed after use.

    ``write_group`` stages the members in sequence (it calls a member's function
    and reads the returned :class:`DuckSource` before asking for the next), so the
    extraction of the previous member is removed when the next one is requested
    and, at the latest, by :meth:`close`: the disk holds the CSV of one ZIP, not of
    ten (``estabelecimentos`` has about 15 GB of CSV a month).
    """

    def __init__(self, base: Path) -> None:
        self.base = base
        self._current: Path | None = None

    def source(self, path: Path, names: tuple[str, ...]) -> DuckSource:
        self._drop()
        if path.suffix.lower() in _TEXT_SUFFIXES:
            return DuckSource(read_csv_sql([path], names, "latin-1"))
        if path.suffix.lower() != ".zip":
            raise LakeError(f"{path.name}: formato não suportado")
        self.base.mkdir(parents=True, exist_ok=True)
        folder = Path(tempfile.mkdtemp(prefix="rfb-cnpj-", dir=self.base))
        self._current = folder
        with zipfile.ZipFile(path) as archive:
            chosen = _data_members([m.filename for m in archive.infolist()])
            if not chosen:
                raise LakeError(f"{path.name}: o ZIP não tem arquivo de dados")
            files = [Path(archive.extract(name, folder)) for name in chosen]
        encoding = "latin-1"
        if any(map(_has_c1_bytes, files)):
            files = _to_utf8(files, folder / "utf8")
            encoding = "utf-8"
        return DuckSource(read_csv_sql(files, names, encoding))

    def _drop(self) -> None:
        if self._current is not None:
            shutil.rmtree(self._current, ignore_errors=True)
            self._current = None

    def close(self) -> None:
        self._drop()
        try:
            self.base.rmdir()  # only if nobody else left anything there
        except OSError:
            pass


def _latest_per_key(paths: list[Path]) -> list[Path]:
    """One raw file per file key: the last by name, i.e. the latest ``@date``."""
    chosen: dict[str, Path] = {}
    for path in sorted(paths):
        chosen[file_key(path)] = path
    return list(chosen.values())


class LakeConverter:
    """Converter registered under the ``quantilica.lake`` entry point."""

    source_id = SOURCE_ID

    def datasets(self) -> list[str]:
        """Dataset ids this converter writes to the lake."""
        return sorted(LAYOUTS)

    def convert(
        self,
        input_dir: Path,
        lake_dir: Path,
        *,
        datasets: list[str] | None = None,
        force: bool = False,
    ) -> ConvertResult:
        """Convert raw ZIPs into ``lake_dir``: one Parquet per dataset and month.

        The ZIPs found for a dataset and month are the complete list of its
        parts: the month's Parquet is rewritten when any of them is new or
        changed, and a ZIP that is no longer in ``input_dir`` leaves the file.
        The Parquets of the previous layout (one per ZIP) in that month are
        removed once the new one is published.

        Args:
            input_dir: Root directory containing raw files.
            lake_dir: Root of the lake.
            datasets: Optional list of dataset/group names to filter.
            force: Reconvert even when the raw file's sha256 is already in the lake.

        Returns:
            ConvertResult: ZIPs converted, ZIPs skipped (already in the lake) and
            error messages (one per dataset and month that failed).
        """
        input_dir = Path(input_dir)
        lake_dir = Path(lake_dir)
        result = ConvertResult()
        if not input_dir.is_dir():
            result.errors.append(f"diretório '{input_dir}' não existe")
            return result

        allowed = set(datasets) if datasets else set(LAYOUTS)
        unknown = allowed - set(LAYOUTS)
        if unknown:
            for u in sorted(unknown):
                result.errors.append(f"dataset desconhecido: {u}")
            return result

        # Scan for .zip archives (or .csv/.txt for unpacked fixtures/debug)
        candidates = sorted(
            p
            for p in input_dir.rglob("*")
            if p.is_file() and p.suffix.lower() in {".zip", ".csv", ".txt"}
        )

        groups: dict[tuple[str, int, str], list[Path]] = defaultdict(list)
        for path in candidates:
            group = infer_group(path)
            if not group or group not in allowed:
                continue
            partitions = infer_partitions(path)
            if not partitions:
                result.errors.append(
                    f"{path.name}: não foi possível inferir competência (ano/mês)"
                )
                continue
            groups[(group, partitions["ano"], partitions["mes"])].append(path)

        writers: dict[str, LakeWriter] = {}
        for (group, ano, mes), paths in sorted(groups.items()):
            if group not in writers:
                writers[group] = LakeWriter(
                    lake_dir / SOURCE_ID / group,
                    DatasetDescriptor(
                        source_id=SOURCE_ID,
                        dataset_id=group,
                        alias=group,
                        partition_keys=PARTITION_KEYS,
                        partition_types=PARTITION_TYPES,
                    ),
                    force=force,
                )
            self._convert_group(
                writers[group], group, ano, mes, _latest_per_key(paths), result
            )
        return result

    @staticmethod
    def _convert_group(
        writer: LakeWriter,
        group: str,
        ano: int,
        mes: str,
        paths: list[Path],
        result: ConvertResult,
    ) -> None:
        group_key = f"{group}_{ano}{mes}"
        partitions = {"ano": ano, "mes": mes}
        names = LAYOUTS[group]
        scratch = os.environ.get(LAKE_SCRATCH_ENV)
        extractions = _Extractions(
            Path(scratch) if scratch else writer.dataset_dir / ".tmp"
        )

        def member(path: Path, digest: str) -> GroupMember:
            # The function runs only for a ZIP that has to be written.
            return GroupMember(
                path,
                lambda: extractions.source(path, names),
                sha256=digest,
            )

        try:
            members = [member(p, sha256_file(p)) for p in paths]
            options = {
                "partitions": partitions,
                "contract_version": CONTRACT_VERSION,
                "converter_version": CONVERTER_VERSION,
            }
            current = writer.is_current_group(group_key, members, **options)
            written = writer.write_group(
                group_key,
                members,
                converter=f"rfb-cnpj-fetcher {__version__}",
                # Os Parquets antigos (um por ZIP) do mês saem depois que o novo
                # é publicado; só os que o grupo cobre por sha256.
                replace_partition=True,
                **options,
            )
        except (LakeError, OSError, ValueError, duckdb.Error) as exc:
            message = str(exc).strip()
            first_line = message.splitlines()[0] if message else repr(exc)
            result.errors.append(f"{group_key}: {first_line}")
            return
        finally:
            extractions.close()

        if written.status == "skipped" or current:
            result.skipped += len(paths)
        else:
            result.converted += len(written.written)
            result.skipped += len(written.kept)


converter = LakeConverter()
