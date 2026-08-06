"""Typer plugin for quantilica-cli integration."""

# ruff: noqa: B023
from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Annotated

import typer
from quantilica.core.cli import (
    get_console,
    make_batch_progress,
    make_download_progress,
    setup_rich_logging,
)
from rich.console import Group
from rich.live import Live
from rich.table import Table

from .catalog import GROUPS, latest_competencia, list_competencias, list_files
from .download import download_entry
from .storage import DataRepository

app = typer.Typer(help="Dados públicos de CNPJ da Receita Federal do Brasil.")
console = get_console()

_DEFAULT_OUTPUT = Path("/data/rfb-cnpj")


@app.command("sync")
def cmd_sync(
    groups: Annotated[
        list[str] | None,
        typer.Argument(
            help=(f"Grupos a baixar: {', '.join(GROUPS)}. Padrão: todos os grupos."),
        ),
    ] = None,
    output: Annotated[
        Path,
        typer.Option("-o", "--output", help="Diretório de saída"),
    ] = _DEFAULT_OUTPUT,
    competencia: Annotated[
        str | None,
        typer.Option(
            "--competencia",
            metavar="YYYY-MM",
            help="Competência específica a baixar (ex: 2026-07).",
        ),
    ] = None,
    latest: Annotated[
        bool,
        typer.Option("--latest", help="Baixar apenas a competência mais recente."),
    ] = False,
    all_competencias: Annotated[
        bool,
        typer.Option("--all", help="Baixar todas as competências disponíveis."),
    ] = False,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Listar arquivos sem baixar."),
    ] = False,
    verbose: Annotated[
        bool,
        typer.Option("--verbose", help="Exibir logs detalhados."),
    ] = False,
    workers: Annotated[
        int,
        typer.Option("--workers", help="Número de downloads paralelos."),
    ] = 4,
) -> None:
    """Sincronizar dados públicos de CNPJ da Receita Federal."""
    setup_rich_logging(verbose, console=console)

    target_groups = groups or GROUPS
    invalid = [g for g in target_groups if g not in GROUPS]
    if invalid:
        console.print(f"[red]Grupos desconhecidos: {', '.join(invalid)}[/red]")
        console.print(f"Grupos válidos: {', '.join(GROUPS)}")
        raise typer.Exit(1)

    with console.status("[cyan]Consultando competências disponíveis...[/cyan]"):
        if competencia:
            competencias = [competencia]
        elif latest:
            competencias = [latest_competencia()]
        else:
            competencias = list_competencias()

    for comp in competencias:
        console.rule(f"[bold]Competência {comp}[/bold]")

        with console.status(f"[cyan]Listando arquivos de {comp}...[/cyan]"):
            entries = list_files(comp, groups=target_groups)

        if not entries:
            console.print(
                "[yellow]Nenhum arquivo encontrado para os grupos "
                "selecionados.[/yellow]"
            )
            continue

        if dry_run:
            table = Table(
                "Grupo",
                "Arquivo",
                "URL",
                title=f"Arquivos ({comp}) — dry-run",
            )
            for e in entries:
                table.add_row(e["group"], e["filename"], e["url"])
            console.print(table)
            console.print(f"[bold]{len(entries)}[/bold] arquivo(s) listado(s).")
            continue

        total = len(entries)
        repo = DataRepository(output)
        overall = make_batch_progress(console)
        file_prog = make_download_progress(console)
        overall_task = overall.add_task("[cyan]Iniciando...[/cyan]", total=total)

        worker_task_ids = [
            file_prog.add_task("[dim]Inativo[/dim]", total=1) for _ in range(workers)
        ]
        available_tasks = worker_task_ids.copy()

        downloaded = 0
        errors: list[tuple[str, str]] = []
        disk_full = False
        lock = threading.Lock()

        def _job(entry: dict) -> None:  # noqa: B023
            nonlocal downloaded, disk_full
            if disk_full:
                return

            with lock:
                task_id = available_tasks.pop(0)

            def cb(downloaded_bytes: int, total_bytes: int) -> None:
                if downloaded_bytes == 0 and total_bytes == 0:  # retry signal
                    file_prog.update(task_id, completed=0)
                    return
                file_prog.update(
                    task_id,
                    description=f"[cyan]{entry['filename']}[/cyan]",
                    completed=downloaded_bytes,
                    total=total_bytes or None,
                )

            try:
                download_entry(entry, repo, progress=cb)
                with lock:
                    downloaded += 1
            except Exception as exc:  # noqa: BLE001
                msg = str(exc)
                with lock:
                    errors.append((entry["filename"], msg))
                    if "Insufficient disk space" in msg or "No space left" in msg:
                        disk_full = True
            finally:
                overall.update(overall_task, advance=1)
                with lock:
                    file_prog.update(
                        task_id, description="[dim]Inativo[/dim]", completed=0, total=1
                    )
                    available_tasks.append(task_id)

        try:
            with Live(
                Group(overall, file_prog),
                console=console,
                refresh_per_second=10,
            ):
                with ThreadPoolExecutor(max_workers=workers) as executor:
                    futures = [executor.submit(_job, entry) for entry in entries]
                    for future in as_completed(futures):
                        future.result()
        except KeyboardInterrupt:
            console.print("\n[yellow]Interrompido.[/yellow]")
            raise typer.Exit(130) from None

        if errors:
            console.print(
                f"\n[yellow]⚠[/yellow]  {downloaded} OK · "
                f"[red]{len(errors)} falha(s)[/red]"
            )
            for fname, msg in errors:
                console.print(f"  [dim]{fname}:[/dim] {msg}")
        else:
            console.print(
                f"\n[green]✓[/green]  [bold]{downloaded}[/bold] arquivo(s) baixado(s) "
                f"em [dim]{output / comp}[/dim]."
            )

        if disk_full:
            console.print(
                "\n[bold red]⚠ Espaço em disco insuficiente. "
                "Sincronização interrompida.[/bold red]"
            )
            break


@app.command("list")
def cmd_list(
    verbose: Annotated[
        bool,
        typer.Option("--verbose", help="Exibir logs detalhados."),
    ] = False,
) -> None:
    """Listar competências disponíveis no portal da RFB."""
    setup_rich_logging(verbose, console=console)

    with console.status("[cyan]Consultando portal da RFB...[/cyan]"):
        comps = list_competencias()

    table = Table(
        "Competência",
        title="Competências disponíveis — RFB CNPJ",
        show_header=True,
        header_style="bold",
    )
    for c in comps:
        table.add_row(c)
    console.print(table)
    console.print(f"\n[bold]{len(comps)}[/bold] competência(s) disponível(eis).")
    console.print(f"Grupos: [dim]{', '.join(GROUPS)}[/dim]")
