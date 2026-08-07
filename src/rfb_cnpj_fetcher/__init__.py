"""rfb-cnpj-fetcher — Download dos dados públicos de CNPJ da Receita Federal."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("rfb-cnpj-fetcher")
except PackageNotFoundError:
    __version__ = "0.0.0"

from .catalog import (
    GROUPS,
    FileEntry,
    latest_competencia,
    list_competencias,
    list_files,
)
from .storage import DataRepository

__all__ = [
    "__version__",
    "GROUPS",
    "FileEntry",
    "DataRepository",
    "latest_competencia",
    "list_competencias",
    "list_files",
]
