"""Local path management for rfb-cnpj-fetcher.

Files are stored as:
    <root>/<competencia>/<group>/<basename>@<YYYYMMDD>.zip

Examples:
    /data/rfb-cnpj/2025-07/empresas/Empresas0@20250710.zip
    /data/rfb-cnpj/2025-07/simples/Simples@20250710.zip
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path

from quantilica.core.storage import BaseDataRepository, stamp_filename

from .catalog import FileEntry


class DataRepository(BaseDataRepository):
    """Manages local storage for rfb-cnpj-fetcher files."""

    def __init__(self, root: Path | str):
        super().__init__(root)

    def path_for_entry(
        self,
        entry: FileEntry,
        *,
        last_modified: dt.date | None = None,
    ) -> Path:
        """Compute local path for a FileEntry.

        Returns <root>/<competencia>/<group>/<stamped_basename>.zip
        """
        base = Path(entry["filename"]).stem  # "Empresas0" or "Simples"
        filename = stamp_filename(base, "zip", last_modified)
        return self.storage.path_for(
            f"{entry['competencia']}/{entry['group']}/{filename}"
        )
