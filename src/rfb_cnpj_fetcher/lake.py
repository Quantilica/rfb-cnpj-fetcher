"""Convert raw RFB CNPJ ZIP archives into the Hive-partitioned lake.

Each raw ZIP lands in ``<lake>/rfb-cnpj/<dataset>/ano=<ano>/mes=<mes>/`` as
``<file_key>.parquet`` (e.g. ``empresas0.parquet``). Files have no header and are
encoded in Latin-1 with ``;`` delimiter; column names come from the official
Receita Federal layout (``rfb_cnpj_fetcher.reader.LAYOUTS``).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

try:
    import duckdb
    from quantilica.analytics.lake import LakeError, LakeWriter
    from quantilica.core.lake import DatasetDescriptor
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
PARTITION_TYPES = {"ano": "varchar", "mes": "varchar"}

_COMPETENCIA = re.compile(r"^\d{4}-\d{2}$")
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
    return None


def infer_partitions(path: Path) -> dict[str, str] | None:
    """Infer ``ano`` and ``mes`` partition values from folder structure or filename."""
    # Check parent and grandparent for YYYY-MM
    for parent in (path.parent, path.parent.parent):
        if _COMPETENCIA.match(parent.name):
            ano, mes = parent.name.split("-")
            return {"ano": ano, "mes": mes}
    # Check @YYYYMMDD stamp in filename
    match = _STAMP.search(path.name)
    if match:
        return {"ano": match["ano"], "mes": match["mes"]}
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
        """Convert raw ZIP archives into ``lake_dir``.

        Args:
            input_dir: Root directory containing raw files.
            lake_dir: Root of the lake.
            datasets: Optional list of dataset/group names to filter.
            force: Reconvert even when the raw file's sha256 is already in the lake.

        Returns:
            ConvertResult: Files converted, skipped, and error messages.
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

        writers: dict[str, LakeWriter] = {}

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

            writer = writers[group]
            names = LAYOUTS[group]

            try:
                written = writer.write_duckdb(
                    path,
                    partitions=partitions,
                    separator=";",
                    encoding="latin-1",
                    header=False,
                    names=names,
                    converter=f"rfb-cnpj-fetcher {__version__}",
                )
            except (LakeError, OSError, duckdb.Error) as exc:
                message = str(exc).strip()
                first_line = message.splitlines()[0] if message else repr(exc)
                result.errors.append(f"{path.name}: {first_line}")
                continue

            if written.status == "skipped":
                result.skipped += 1
            else:
                result.converted += 1

        return result


converter = LakeConverter()
