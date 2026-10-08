"""Tests for rfb_cnpj_fetcher.cli — import guard without the CLI host."""

from __future__ import annotations

import importlib
import sys
import types

import pytest


@pytest.fixture
def cli_without_host() -> object:
    """Reloads ``rfb_cnpj_fetcher.cli`` with the host marked unavailable.

    Yields:
        object: The reloaded ``rfb_cnpj_fetcher.cli`` module in guarded state.

    Restores ``sys.modules`` and the original module state afterwards so
    other tests are not contaminated.

    The plugin imports the host via ``quantilica.cli.sdk`` (no direct
    ``import typer``), so both ``typer`` and ``quantilica.cli.sdk`` are
    blocked — blocking ``typer`` alone would not break the reimport because
    the SDK is already cached in ``sys.modules``.
    """
    saved_host = {key: sys.modules.get(key) for key in ("typer", "quantilica.cli.sdk")}
    saved_plugin = sys.modules.get("rfb_cnpj_fetcher.plugin")
    saved_cli = sys.modules.get("rfb_cnpj_fetcher.cli")
    sys.modules["typer"] = None
    sys.modules["quantilica.cli.sdk"] = None
    sys.modules.pop("rfb_cnpj_fetcher.plugin", None)  # forcar reimport do plugin
    try:
        cli = importlib.reload(importlib.import_module("rfb_cnpj_fetcher.cli"))
        yield cli
    finally:
        for key, saved in saved_host.items():
            if saved is None:
                sys.modules.pop(key, None)
            else:
                sys.modules[key] = saved
        if saved_plugin is None:
            sys.modules.pop("rfb_cnpj_fetcher.plugin", None)
        else:
            sys.modules["rfb_cnpj_fetcher.plugin"] = saved_plugin
        if saved_cli is None:
            sys.modules.pop("rfb_cnpj_fetcher.cli", None)
        else:
            importlib.reload(saved_cli)


def test_import_does_not_raise_without_host(cli_without_host) -> None:
    """Importing cli without the host must not raise ModuleNotFoundError.

    Args:
        cli_without_host (object): The reloaded cli module in guarded state.
    """
    assert cli_without_host.app is None
    assert cli_without_host._PLUGIN_ERROR is not None


def test_main_without_host_exits_1(cli_without_host, capsys) -> None:
    """main() exits 1 and prints an actionable message without the host.

    Args:
        cli_without_host (object): The reloaded cli module in guarded state.
        capsys (object): pytest fixture capturing stdout/stderr.
    """
    with pytest.raises(SystemExit) as excinfo:
        cli_without_host.main(["list"])
    assert excinfo.value.code == 1
    stderr = capsys.readouterr().err
    assert "Erro: CLI requer 'typer' e 'rich' (via quantilica-cli)." in stderr
    assert 'Instale via "quantilica install rfb-cnpj".' in stderr
    assert "Detalhe:" in stderr


def test_internal_plugin_import_error_propagates() -> None:
    """ImportError from a non-host module inside the plugin must propagate.

    A broken internal import (``exc.name`` outside the host modules) must not
    be masked as a missing host — it raises instead of exiting 1.
    """
    import rfb_cnpj_fetcher.cli as cli_module

    plugin_key = "rfb_cnpj_fetcher.plugin"
    saved = sys.modules.get(plugin_key)
    stub = types.ModuleType(plugin_key)

    def __getattr__(name):
        raise ModuleNotFoundError("No module named 'outro_modulo'", name="outro_modulo")

    stub.__getattr__ = __getattr__
    sys.modules[plugin_key] = stub
    try:
        with pytest.raises(ModuleNotFoundError):
            importlib.reload(cli_module)
    finally:
        if saved is None:
            sys.modules.pop(plugin_key, None)
        else:
            sys.modules[plugin_key] = saved
        importlib.reload(cli_module)
