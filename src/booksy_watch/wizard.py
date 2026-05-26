"""First-run interactive setup using rich.prompt."""

from __future__ import annotations

from rich.console import Console
from rich.prompt import Confirm, IntPrompt, Prompt
from rich.table import Table

from .booksy import BooksyClient, Business, parse_business_id, parse_country
from .config import Config, NotifyConfig, SalonConfig, WatchConfig
from .i18n import LANGUAGE_LABELS, LANGUAGES, set_language, t


def _ask_language(console: Console, default: str) -> str:
    labels = " / ".join(f"[bold]{c}[/bold]={LANGUAGE_LABELS[c]}" for c in LANGUAGES)
    console.print(f"Language / Język  ({labels})  [dim]\\[default: {default}][/dim]")
    code = Prompt.ask(
        "Language / Język",
        choices=list(LANGUAGES),
        default=default if default in LANGUAGES else "en",
        show_choices=False,
        show_default=False,
    )
    set_language(code)
    return code


def _ask_salon_url(console: Console, default_url: str | None) -> tuple[str, int, str]:
    while True:
        url = Prompt.ask(f"[bold cyan]{t('wiz_url')}", default=default_url)
        try:
            bid = parse_business_id(url)
            country = parse_country(url)
            return url, bid, country
        except ValueError as e:
            console.print(f"[red]{t('wiz_url_bad', err=str(e))}[/red]")


def _pick_service(
    console: Console,
    biz: Business,
    default_variant_id: int | None,
) -> tuple[int, int | None]:
    """Returns (service_variant_id, staffer_id|None). One row per variant."""
    rows: list[tuple[int, int, int | None, str, float, int]] = []  # (idx, variant_id, staffer_id, name, price, duration)
    idx = 1
    default_idx: int | None = None
    for svc in biz.services:
        for v in svc.variants:
            sid = v.staffer_ids[0] if len(v.staffer_ids) == 1 else None
            rows.append((idx, v.variant_id, sid, svc.name, v.price, v.duration))
            if default_variant_id is not None and v.variant_id == default_variant_id:
                default_idx = idx
            idx += 1

    table = Table(title=t("wiz_services_title", name=biz.name), show_lines=False)
    table.add_column(t("col_num"), justify="right")
    table.add_column(t("col_service"))
    table.add_column(t("col_staffer"))
    table.add_column(t("col_price"), justify="right")
    table.add_column(t("col_duration"), justify="right")
    for n, _vid, sid, name, price, dur in rows:
        marker = " ◀" if n == default_idx else ""
        staffer_label = biz.staffer_name(sid) if sid is not None else t("staffer_any")
        table.add_row(
            str(n),
            name + marker,
            staffer_label,
            f"{price:.0f} zł",
            f"{dur}min",
        )
    console.print(table)

    choice = IntPrompt.ask(
        t("wiz_pick_service"),
        choices=[str(r[0]) for r in rows],
        show_choices=False,
        default=default_idx,
        show_default=default_idx is not None,
    )
    _, variant_id, staffer_id, _, _, _ = rows[choice - 1]
    return variant_id, staffer_id


def run_wizard(existing: Config | None = None) -> Config:
    """Interactive setup. If `existing` is given, every prompt is pre-filled."""
    console = Console()
    console.rule(f"[bold magenta]{t('wiz_title')}")

    # Language: default English unless existing config says otherwise.
    default_lang = existing.language if existing else "en"
    lang = _ask_language(console, default_lang)
    console.rule(f"[bold magenta]{t('wiz_title')}")

    url, bid, country = _ask_salon_url(console, existing.salon.url if existing else None)
    console.print(f"[green]✓[/green] " + t("wiz_business_ok", bid=bid, country=country))

    with BooksyClient(country=country) as client:
        biz = client.get_business(bid)
    console.print(f"[green]✓[/green] " + t("wiz_loaded", name=biz.name, n=len(biz.services)))

    default_variant = existing.watch.service_variant_id if existing else None
    variant_id, staffer_id = _pick_service(console, biz, default_variant)

    interval = IntPrompt.ask(
        t("wiz_interval"),
        default=existing.watch.interval_minutes if existing else 10,
    )
    days = IntPrompt.ask(
        t("wiz_days"),
        default=existing.watch.date_range_days if existing else 90,
    )
    sound = Confirm.ask(
        t("wiz_sound"),
        default=existing.notify.sound if existing else True,
    )
    desktop = Confirm.ask(
        t("wiz_desktop"),
        default=existing.notify.desktop if existing else True,
    )

    cfg = Config(
        salon=SalonConfig(url=url, business_id=bid, country=country),
        watch=WatchConfig(
            service_variant_id=variant_id,
            staffer_id=staffer_id,
            interval_minutes=max(1, interval),
            date_range_days=max(1, days),
        ),
        notify=NotifyConfig(sound=sound, desktop=desktop),
        language=lang,
    )
    cfg.save()
    console.print(f"[green]✓ {t('wiz_saved')}[/green]")
    return cfg
