"""Standalone command-line interface for rfb-cnpj-fetcher."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from quantilica.core.logging import configure_cli_logging

from . import __version__
from .catalog import GROUPS, latest_competencia, list_competencias, list_files
from .download import download_entry
from .storage import DataRepository

_DEFAULT_OUTPUT = Path("/data/rfb-cnpj")


def get_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="rfb-cnpj-fetcher",
        description="Download dos dados públicos de CNPJ da Receita Federal do Brasil.",
    )
    parser.add_argument(
        "--version", action="version", version=f"%(prog)s {__version__}"
    )
    subparsers = parser.add_subparsers(dest="command", metavar="COMMAND")

    # --- sync ---
    sync_p = subparsers.add_parser(
        "sync",
        help="Sincronizar dados de CNPJ da RFB.",
    )
    sync_p.add_argument(
        "groups",
        nargs="*",
        metavar="GRUPO",
        help=(f"Grupos a baixar: {', '.join(GROUPS)}. Padrão: todos os grupos."),
    )
    sync_p.add_argument(
        "-o",
        "--output",
        type=Path,
        default=_DEFAULT_OUTPUT,
        metavar="DIR",
        help="Diretório de saída (padrão: /data/rfb-cnpj).",
    )
    sync_p.add_argument(
        "--competencia",
        metavar="YYYY-MM",
        default=None,
        help="Competência a baixar (padrão: mais recente).",
    )
    sync_p.add_argument(
        "--all",
        dest="all_competencias",
        action="store_true",
        default=False,
        help="Baixar todas as competências disponíveis (histórico completo).",
    )
    sync_p.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="Listar arquivos sem baixar.",
    )
    sync_p.add_argument(
        "--verbose",
        action="store_true",
        default=False,
        help="Exibir logs detalhados em vez de saída limpa.",
    )

    # --- list ---
    list_p = subparsers.add_parser(
        "list",
        help="Listar competências disponíveis no portal da RFB.",
    )
    list_p.add_argument(
        "--verbose",
        action="store_true",
        default=False,
        help="Exibir logs detalhados.",
    )

    return parser


def _resolve_groups(raw: list[str]) -> list[str]:
    """Validate and return the requested groups, or all groups if empty."""
    if not raw:
        return GROUPS
    invalid = [g for g in raw if g not in GROUPS]
    if invalid:
        print(
            f"Erro: grupos desconhecidos: {', '.join(invalid)}\n"
            f"Grupos válidos: {', '.join(GROUPS)}",
            file=sys.stderr,
        )
        sys.exit(1)
    return raw


def _handle_sync(args: argparse.Namespace) -> None:
    configure_cli_logging(args.verbose)
    if not args.verbose:
        logging.getLogger("quantilica.core").setLevel(logging.WARNING)
        logging.getLogger("rfb_cnpj_fetcher").setLevel(logging.WARNING)

    groups = _resolve_groups(args.groups)

    if args.all_competencias:
        competencias = list_competencias()
    elif args.competencia:
        competencias = [args.competencia]
    else:
        competencias = [latest_competencia()]

    for comp in competencias:
        print(f"\nCompetência: {comp}")
        entries = list_files(comp, groups=groups)

        if args.dry_run:
            for e in entries:
                print(f"  {e['group']}\t{e['filename']}\t{e['url']}")
            print(f"  {len(entries)} arquivo(s) listado(s).")
            continue

        repo = DataRepository(args.output)
        ok = 0
        errors: list[tuple[str, str]] = []
        for entry in entries:
            try:
                download_entry(entry, repo)
                ok += 1
            except Exception as exc:  # noqa: BLE001
                errors.append((entry["filename"], str(exc)))

        print(f"  {ok}/{len(entries)} arquivo(s) baixado(s).")
        if errors:
            for fname, msg in errors:
                print(f"  ERRO: {fname}: {msg}", file=sys.stderr)

    if any(True for _ in []):  # unreachable — keeps exit code clean
        sys.exit(1)


def _handle_list(args: argparse.Namespace) -> None:
    configure_cli_logging(args.verbose)
    if not args.verbose:
        logging.getLogger("quantilica.core").setLevel(logging.WARNING)
        logging.getLogger("rfb_cnpj_fetcher").setLevel(logging.WARNING)

    comps = list_competencias()
    print(f"{len(comps)} competência(s) disponível(eis):")
    for c in comps:
        print(f"  {c}")
    print(f"\nGrupos: {', '.join(GROUPS)}")


def main(argv: list[str] | None = None) -> None:
    parser = get_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "sync":
            _handle_sync(args)
        elif args.command == "list":
            _handle_list(args)
        else:
            parser.print_help()
            sys.exit(1)
    except KeyboardInterrupt:
        sys.exit(130)
