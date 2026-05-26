"""Entry point: `uv run booksy-watch` or `python -m booksy_watch`."""

from __future__ import annotations

import sys

from rich.console import Console

from .config import Config, config_path
from .tui import BooksyWatchApp
from .wizard import run_wizard


def main() -> int:
    console = Console()
    args = sys.argv[1:]

    if "--help" in args or "-h" in args:
        console.print(
            "[bold]booksy-watch[/bold] — watch Booksy for earlier appointment slots\n"
            "\n"
            "Usage:\n"
            "  booksy-watch              # run TUI (runs wizard on first launch)\n"
            "  booksy-watch reconfigure  # re-run setup wizard\n"
            "  booksy-watch path         # print config file path\n"
            "\n"
            "Keys in TUI: q=quit  p=pause  r=reset target  c=check now\n"
        )
        return 0

    if args and args[0] == "path":
        print(config_path())
        return 0

    if args and args[0] == "reconfigure":
        cfg = run_wizard()
    else:
        cfg = Config.load()
        if cfg is None:
            console.print("[yellow]No config found — starting setup wizard.[/yellow]")
            cfg = run_wizard()

    BooksyWatchApp(cfg).run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
