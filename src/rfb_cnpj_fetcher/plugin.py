"""Typer plugin for quantilica-cli integration."""

from __future__ import annotations

import datetime as dt
from pathlib import Path
from typing import Any

from quantilica.cli.sdk import FetcherApp

from .catalog import GROUP_ALIASES, GROUPS, FileEntry, list_datasets
from .storage import DataRepository


def path_builder(
    output_dir: Path, entry: dict[str, Any], last_modified: dt.date | None
) -> Path:
    """Build the target download path for a given file entry.

    Args:
        output_dir (Path): The root output directory.
        entry (dict[str, Any]): Dictionary containing metadata like 'group',
            'filename', 'url', and 'competencia'.
        last_modified (dt.date | None): Optional last modified date to stamp on the
            filename.

    Returns:
        Path: The constructed path for saving the downloaded file.
    """
    file_entry = FileEntry(
        group=entry["group"],
        filename=entry["filename"],
        url=entry["url"],
        competencia=entry["competencia"],
    )
    return DataRepository(output_dir).path_for_entry(
        file_entry, last_modified=last_modified
    )


fetcher = FetcherApp(
    name="rfb-cnpj-fetcher",
    help="Dados públicos de CNPJ da Receita Federal do Brasil.",
    groups_dict=GROUPS,
    aliases_dict=GROUP_ALIASES,
    list_datasets=list_datasets,
    path_builder=path_builder,
)

app = fetcher.app
