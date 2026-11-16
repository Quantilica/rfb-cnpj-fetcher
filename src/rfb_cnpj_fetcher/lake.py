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

import json
import os
import re
import shutil
import socket
import tempfile
import zipfile
import zlib
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Any

try:
    import duckdb
    import pyarrow.parquet as pq
    from quantilica.analytics.lake import (
        META_MEMBERS,
        OWNER_FILE,
        WORK_PREFIX,
        DuckSource,
        GroupMember,
        LakeError,
        LakeWriter,
    )
    from quantilica.core.exceptions import StorageError
    from quantilica.core.files import sha256_file
    from quantilica.core.lake import (
        DatasetDescriptor,
        file_key,
        partition_dir,
        partition_types_for,
    )
    from quantilica.core.logging import get_logger
    from quantilica.core.manifests import manifest_sidecar_path
except ImportError as exc:
    raise ImportError(
        "rfb_cnpj_fetcher.lake requer o extra 'analysis': "
        "uv add 'rfb-cnpj-fetcher[analysis]' "
        "--index https://index.quantilica.com/simple/"
    ) from exc

from rfb_cnpj_fetcher import __version__
from rfb_cnpj_fetcher.catalog import _GROUP_PATTERNS
from rfb_cnpj_fetcher.reader import LAYOUTS

logger = get_logger(__name__)

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
# Failures that spoil one month, not the run: a damaged ZIP, an unreadable or
# unhashable file, a DuckDB or lake error.
_MONTH_ERRORS = (
    LakeError,
    OSError,
    ValueError,
    EOFError,
    zlib.error,
    zipfile.BadZipFile,
    StorageError,
    duckdb.Error,
)
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
    """The DuckDB ``SELECT`` that reads the files of one raw ZIP, all as text.

    Only the ``names`` columns are selected, never ``*``: a line with more fields
    than the layout would otherwise add ``column7``... to the Parquet (and a line
    with fewer is padded with nulls), as ``write_duckdb`` already did.
    """
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
    columns = ", ".join('"' + n.replace('"', '""') + '"' for n in names)
    return f"SELECT {columns} FROM read_csv({', '.join(args)})"


class _Extractions:
    """Extracts one raw file at a time into a folder of its own, removed after use.

    ``write_group`` stages the members in sequence (it calls a member's function
    and reads the returned :class:`DuckSource` before asking for the next), so the
    extraction of the previous member is removed when the next one is requested
    and, at the latest, by :meth:`close`: the disk holds the CSV of one ZIP, not of
    ten (``estabelecimentos`` has about 15 GB of CSV a month).

    The folder carries the analytics' work prefix and an ``owner.json`` (pid and
    host), so the analytics' scratch cleanup recognises it as a work directory of
    a live process, or of a dead one that can be swept.
    """

    def __init__(self, base: Path) -> None:
        self.base = base
        self._current: Path | None = None

    def _folder(self) -> Path:
        self.base.mkdir(parents=True, exist_ok=True)
        folder = Path(tempfile.mkdtemp(prefix=WORK_PREFIX, dir=self.base))
        (folder / OWNER_FILE).write_text(
            json.dumps({"pid": os.getpid(), "hostname": socket.gethostname()})
        )
        self._current = folder
        return folder

    def source(self, path: Path, names: tuple[str, ...]) -> DuckSource:
        self._drop()
        suffix = path.suffix.lower()
        if suffix in _TEXT_SUFFIXES:
            files = [path]
        elif suffix == ".zip":
            folder = self._folder()
            with zipfile.ZipFile(path) as archive:
                chosen = _data_members([m.filename for m in archive.infolist()])
                if not chosen:
                    raise LakeError(f"{path.name}: o ZIP não tem arquivo de dados")
                files = [Path(archive.extract(name, folder / "raw")) for name in chosen]
        else:
            raise LakeError(f"{path.name}: formato não suportado")
        encoding = "latin-1"
        if any(map(_has_c1_bytes, files)):
            folder = self._current or self._folder()
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


_PART = re.compile(
    r"^(?P<ds>empresas|estabelecimentos|socios)[_-]?(?P<n>\d+)(?P<rest>.*)$",
    re.IGNORECASE,
)
_COMPETENCIA_IN_KEY = re.compile(r"_\d{4}-\d{2}")
_STAMP_IN_NAME = re.compile(r"@(?P<stamp>[0-9T]+)")


def member_identity(group: str, path: Path) -> tuple[int | None, str, str]:
    """``(part number, variant, canonical member key)`` of a raw ZIP.

    The two raw layouts name the same ZIP differently (``2026-10/empresas/
    Empresas0@...zip`` and ``empresas/empresas_0_2026-10@...zip``); both are part 0
    of ``empresas``. A correction file (``Estabelecimentos6-RF0819...zip``) has
    the same part and a *variant* (``RF0819...``), so it is kept as another member
    and never replaces the original, whose rows it may not repeat. The canonical
    key is the current layout's name (``Empresas0``, ``Estabelecimentos6-RF...``,
    ``Simples``), stable whichever layout the file came from.
    """
    key = _COMPETENCIA_IN_KEY.sub("", file_key(path))
    match = _PART.match(key)
    if match and match["ds"].lower() == group:
        number = int(match["n"])
        variant = match["rest"].strip("_-")
        name = f"{group.capitalize()}{number}"
    elif key.lower().startswith(group):
        number, variant = None, key[len(group) :].strip("_-")
        name = group.capitalize()
    else:  # a name from no known layout: its own member, never merged
        return None, "", file_key(path)
    canonical = f"{name}-{variant}" if variant else name
    return number, variant, canonical


def select_members(group: str, paths: list[Path]) -> list[tuple[Path, str]]:
    """One raw ZIP per ``(part, variant)``: ``[(path, canonical key)]``.

    The same ZIP can be in the input twice (both raw layouts, several ``@date``
    versions). The newest ``@date`` stamp wins; on a tie, the current layout (a
    name with no ``_AAAA-MM`` competence), then the last path. A group whose
    chosen ZIPs have different stamps (parts of different harvests) is logged.
    """
    best: dict[str, tuple[tuple, Path]] = {}
    for path in sorted(paths):
        _, _, canonical = member_identity(group, path)
        stamp = _STAMP_IN_NAME.search(path.name)
        rank = (
            stamp["stamp"] if stamp else "",
            not _COMPETENCIA_IN_KEY.search(file_key(path)),
            str(path),
        )
        if canonical not in best or rank > best[canonical][0]:
            best[canonical] = (rank, path)
    chosen = [(entry[1], canonical) for canonical, entry in sorted(best.items())]
    stamps = {entry[0][0] for entry in best.values() if entry[0][0]}
    if len(stamps) > 1:
        logger.warning(
            "%s: parts from different harvests (stamps %s)", group, sorted(stamps)
        )
    return chosen


def known_sha256(path: Path) -> str | None:
    """The ZIP's sha256 from its manifest sidecar, when it can be trusted.

    Trusted only if the manifest records a size equal to the file's and the file
    was not modified after the manifest was written (``mtime``); otherwise
    ``None`` and the caller hashes the file. ``RFB_CNPJ_FETCHER_REHASH=1`` turns
    the shortcut off. Rehashing ~190 GB of ZIPs on every run is what it avoids; the
    lake audit (``rehash=True``) still checks the digests against the bytes.
    """
    if os.environ.get("RFB_CNPJ_FETCHER_REHASH"):
        return None
    sidecar = manifest_sidecar_path(path)
    try:
        recorded = json.loads(sidecar.read_text(encoding="utf-8"))
        size = int(recorded.get("size_bytes") or 0)
        sha = str(recorded.get("sha256") or "").lower()
        stat, sidecar_stat = path.stat(), sidecar.stat()
    except (OSError, ValueError, TypeError, AttributeError):
        return None
    if not size or not re.fullmatch(r"[0-9a-f]{64}", sha):
        return None
    if size != stat.st_size or stat.st_mtime > sidecar_stat.st_mtime + 2:
        return None
    return sha


def _published_members(
    writer: LakeWriter, group_key: str, partitions: dict[str, Any]
) -> set[str] | None:
    """Keys of the members in the footer of the month's published file, if any."""
    path = partition_dir(writer.dataset_dir, partitions) / f"{group_key}.parquet"
    if not path.is_file():
        return None
    try:
        footer = pq.ParquetFile(path).metadata.metadata or {}
        return set(json.loads(footer[META_MEMBERS.encode()]))
    except Exception:  # noqa: BLE001 - a damaged footer is write_group's to judge
        return None


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
                writers[group], group, ano, mes, select_members(group, paths), result
            )
        return result

    @staticmethod
    def _convert_group(
        writer: LakeWriter,
        group: str,
        ano: int,
        mes: str,
        chosen: list[tuple[Path, str]],
        result: ConvertResult,
    ) -> None:
        group_key = f"{group}_{ano}{mes}"
        partitions = {"ano": ano, "mes": mes}
        names = LAYOUTS[group]
        scratch = os.environ.get(LAKE_SCRATCH_ENV)
        extractions = _Extractions(
            Path(scratch) if scratch else writer.dataset_dir / ".tmp"
        )

        def member(path: Path, key: str) -> GroupMember:
            # The function runs only for a ZIP that has to be written.
            return GroupMember(
                path,
                lambda: extractions.source(path, names),
                key=key,
                sha256=known_sha256(path) or sha256_file(path),
            )

        try:
            members = [member(path, key) for path, key in chosen]
            options = {
                "partitions": partitions,
                "contract_version": CONTRACT_VERSION,
                "converter_version": CONVERTER_VERSION,
            }
            # Um ZIP que sumiu da visão não pode levar suas linhas junto: o mês só
            # é reescrito com todos os membros que o arquivo publicado já tem.
            published = _published_members(writer, group_key, partitions)
            missing = sorted((published or set()) - {m.key for m in members})
            if missing:
                result.errors.append(
                    f"{group_key}: mês incompleto: faltam {', '.join(missing)} "
                    "no bruto; o mês não foi reescrito. Se o ZIP saiu de propósito, "
                    "apague o Parquet do mês e reconverta"
                )
                return
            current = writer.is_current_group(
                group_key, members, prune=False, **options
            )
            written = writer.write_group(
                group_key,
                members,
                converter=f"rfb-cnpj-fetcher {__version__}",
                prune=False,
                # Os Parquets antigos (um por ZIP) do mês saem depois que o novo
                # é publicado; só os que o grupo cobre por sha256.
                replace_partition=True,
                **options,
            )
        except _MONTH_ERRORS as exc:
            message = str(exc).strip()
            first_line = message.splitlines()[0] if message else repr(exc)
            result.errors.append(f"{group_key}: {first_line}")
            return
        finally:
            extractions.close()

        for kept in written.not_replaced:
            result.errors.append(
                f"{group_key}: Parquet antigo mantido, de origem que não é ZIP do "
                f"grupo: {kept}; as linhas dele estão duplicadas no mês até você "
                "removê-lo (apague-o se o ZIP não existe mais no bruto)"
            )
        if written.status == "skipped" or current:
            result.skipped += len(chosen)
        else:
            result.converted += len(written.written)
            result.skipped += len(written.kept)


converter = LakeConverter()
