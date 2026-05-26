"""First-run interactive setup using rich.prompt."""

from __future__ import annotations

from rich.console import Console
from rich.prompt import IntPrompt, Prompt
from rich.table import Table

from .booksy import BooksyClient, Business, parse_business_id, parse_country
from .config import Config, NotifyConfig, SalonConfig, WatchConfig


def _ask_salon_url(console: Console) -> tuple[str, int, str]:
    while True:
        url = Prompt.ask("[bold cyan]Salon URL from booksy.com")
        try:
            bid = parse_business_id(url)
            country = parse_country(url)
            return url, bid, country
        except ValueError as e:
            console.print(f"[red]{e}[/red] — try again, expected e.g. https://booksy.com/pl-pl/21431_...")


def _pick_service(console: Console, biz: Business) -> tuple[int, int | None]:
    """Returns (service_variant_id, staffer_id|None). One row per variant."""
    rows: list[tuple[int, int, int | None, str, float, int]] = []  # (idx, variant_id, staffer_id, name, price, duration)
    idx = 1
    for svc in biz.services:
        for v in svc.variants:
            sid = v.staffer_ids[0] if len(v.staffer_ids) == 1 else None
            rows.append((idx, v.variant_id, sid, svc.name, v.price, v.duration))
            idx += 1

    table = Table(title=f"Services at {biz.name}", show_lines=False)
    table.add_column("#", justify="right")
    table.add_column("Service")
    table.add_column("Staffer")
    table.add_column("Price", justify="right")
    table.add_column("Dur", justify="right")
    for n, _vid, sid, name, price, dur in rows:
        table.add_row(str(n), name, biz.staffer_name(sid), f"{price:.0f} zł", f"{dur}min")
    console.print(table)

    choice = IntPrompt.ask("Pick service #", choices=[str(r[0]) for r in rows], show_choices=False)
    _, variant_id, staffer_id, _, _, _ = rows[choice - 1]
    return variant_id, staffer_id


def run_wizard() -> Config:
    console = Console()
    console.rule("[bold magenta]booksy-watch setup")

    url, bid, country = _ask_salon_url(console)
    console.print(f"[green]✓[/green] business_id={bid}, country={country}")

    with BooksyClient(country=country) as client:
        biz = client.get_business(bid)
    console.print(f"[green]✓[/green] {biz.name}  ({len(biz.services)} services)")

    variant_id, staffer_id = _pick_service(console, biz)

    interval = IntPrompt.ask("Polling interval (minutes)", default=10)
    days = IntPrompt.ask("How many days ahead to scan", default=90)
    sound = Prompt.ask("Sound on alert? [y/n]", default="y", choices=["y", "n"]) == "y"
    desktop = Prompt.ask("macOS notification on alert? [y/n]", default="y", choices=["y", "n"]) == "y"

    cfg = Config(
        salon=SalonConfig(url=url, business_id=bid, country=country),
        watch=WatchConfig(
            service_variant_id=variant_id,
            staffer_id=staffer_id,
            interval_minutes=max(1, interval),
            date_range_days=max(1, days),
        ),
        notify=NotifyConfig(sound=sound, desktop=desktop),
    )
    cfg.save()
    console.print(f"[green]✓ Saved config to[/green] [dim]{cfg.salon.url}[/dim]")
    return cfg
