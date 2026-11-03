"""Local path management for rfb-cnpj-fetcher.

Files are stored as:
    <root>/<competencia>/<group>/<basename>@<YYYYMMDD>.zip

Examples:
    /data/rfb-cnpj/2025-07/empresas/Empresas0@20250710.zip
    /data/rfb-cnpj/2025-07/simples/Simples@20250710.zip
"""

from __future__ import annotations

import datetime as dt
import re
from pathlib import Path

from quantilica.core.storage import BaseDataRepository, build_stamped_filename

from .catalog import FileEntry


class DataRepository(BaseDataRepository):
    """Manages local storage for rfb-cnpj-fetcher files."""

    def __init__(self, root: Path | str):
        """Initialize the data repository.

        Args:
            root (Path | str): The base path where files will be stored.
        """
        super().__init__(root)

    def path_for_entry(
        self,
        entry: FileEntry,
        *,
        last_modified: dt.date | dt.datetime | None = None,
    ) -> Path:
        """Compute local path for a FileEntry.

        Returns <root>/<group>/<slug>_<competencia>@<YYYYMMDD>.zip

        Args:
            entry (FileEntry): The file entry specifying group, filename, etc.
            last_modified (dt.date | dt.datetime | None, optional): Optional
                last modified date to stamp on the filename.

        Returns:
            Path: The resolved target local path for the given file entry.
        """
        timestamp = last_modified or dt.date.today()
        base = Path(entry["filename"]).stem  # "Empresas0" or "Simples"
        slug = re.sub(r"(?<=[a-zA-Z])(?=\d)", "_", base).lower()
        competencia = entry.get("competencia", "")
        group = entry.get("group", "datasets")
        filename = build_stamped_filename(
            slug,
            competencia if competencia else None,
            ext="zip",
            timestamp=timestamp,
            precision="date",
        )
        return self.dataset_path(group, filename)
