"""Textual dashboard."""

from __future__ import annotations

import asyncio
from collections import deque
from datetime import datetime, timedelta

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.reactive import reactive
from textual.screen import ModalScreen
from textual.widgets import Button, Checkbox, Footer, Header, Input, Label, Select, Static

from .booksy import BooksyClient
from .config import Config
from .i18n import LANGUAGES, LANGUAGE_LABELS, set_language, t
from .notify import desktop_notify, play_sound
from .watcher import EventKind, WatchEvent, Watcher

KIND_STYLE = {
    EventKind.FIRST: ("▼", "bold yellow"),
    EventKind.EARLIER: ("▲", "bold green"),
    EventKind.SAME: ("·", "dim"),
    EventKind.TAKEN: ("✗", "bold red"),
    EventKind.NONE: ("∅", "dim yellow"),
    EventKind.ERROR: ("!", "bold red"),
}


class TargetPanel(Static):
    target: reactive[datetime | None] = reactive(None)
    next_check: reactive[datetime | None] = reactive(None)
    paused: reactive[bool] = reactive(False)

    def render(self) -> str:
        if self.target:
            target_line = f"[bold green]{self.target:%Y-%m-%d %H:%M}[/bold green]"
        else:
            target_line = f"[dim]{t('panel_no_slot')}[/dim]"
        if self.paused:
            next_line = f"[bold yellow]{t('panel_paused')}[/bold yellow]"
        elif self.next_check:
            remaining = max(0, int((self.next_check - datetime.now()).total_seconds()))
            mm, ss = divmod(remaining, 60)
            next_line = f"{t('panel_next_in')} [bold]{mm:02d}:{ss:02d}[/bold]"
        else:
            next_line = t("panel_starting")
        return f"\n  {t('panel_target')}:  {target_line}\n  {next_line}\n"


class History(Static):
    def __init__(self) -> None:
        super().__init__()
        self.events: deque[WatchEvent] = deque(maxlen=200)

    def add(self, ev: WatchEvent) -> None:
        self.events.appendleft(ev)
        self.refresh_render()

    def refresh_render(self) -> None:
        lines: list[str] = []
        for ev in list(self.events)[:20]:
            sym, style = KIND_STYLE[ev.kind]
            ts = ev.ts.strftime("%H:%M:%S")
            lines.append(f"[dim]{ts}[/dim]  [{style}]{sym} {ev.kind.value:<7}[/{style}]  {ev.message}")
        self.update("\n".join(lines) if lines else "[dim]—[/dim]")


class SettingsScreen(ModalScreen[dict | None]):
    BINDINGS = [Binding("escape", "cancel", "Cancel")]

    CSS = """
    SettingsScreen { align: center middle; }
    #settings-dialog {
        width: 64;
        height: auto;
        padding: 1 2;
        border: round $primary;
        background: $surface;
    }
    #settings-dialog Label.title {
        text-style: bold;
        color: $accent;
        margin-bottom: 1;
    }
    #settings-dialog .row {
        height: 3;
        margin-bottom: 1;
    }
    #settings-dialog Label.field {
        width: 30;
        content-align: left middle;
        height: 3;
    }
    #settings-dialog Input { width: 1fr; }
    #settings-dialog Checkbox { width: 1fr; }
    #settings-dialog Select { width: 1fr; }
    #buttons { height: 3; align: right middle; }
    #buttons Button { margin-left: 1; }
    #error { color: $error; height: auto; margin-bottom: 1; }
    """

    def __init__(self, cfg: Config) -> None:
        super().__init__()
        self.cfg = cfg

    def compose(self) -> ComposeResult:
        with Vertical(id="settings-dialog"):
            yield Label(t("settings_title"), classes="title")
            yield Static("", id="error")
            with Horizontal(classes="row"):
                yield Label(t("settings_interval"), classes="field")
                yield Input(
                    value=str(self.cfg.watch.interval_minutes),
                    id="interval",
                    type="integer",
                    restrict=r"[0-9]*",
                )
            with Horizontal(classes="row"):
                yield Label(t("settings_lookahead"), classes="field")
                yield Input(
                    value=str(self.cfg.watch.date_range_days),
                    id="days",
                    type="integer",
                    restrict=r"[0-9]*",
                )
            with Horizontal(classes="row"):
                yield Label(t("settings_sound"), classes="field")
                yield Checkbox(value=self.cfg.notify.sound, id="sound")
            with Horizontal(classes="row"):
                yield Label(t("settings_desktop"), classes="field")
                yield Checkbox(value=self.cfg.notify.desktop, id="desktop")
            with Horizontal(classes="row"):
                yield Label(t("settings_language"), classes="field")
                yield Select(
                    [(LANGUAGE_LABELS[code], code) for code in LANGUAGES],
                    value=self.cfg.language if self.cfg.language in LANGUAGES else "en",
                    id="language",
                    allow_blank=False,
                )
            with Horizontal(id="buttons"):
                yield Button(t("btn_cancel"), id="cancel", variant="default")
                yield Button(t("btn_save"), id="save", variant="primary")

    def on_mount(self) -> None:
        self.query_one("#interval", Input).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "cancel":
            self.action_cancel()
        elif event.button.id == "save":
            self._save()

    def action_cancel(self) -> None:
        self.dismiss(None)

    def _save(self) -> None:
        err = self.query_one("#error", Static)
        try:
            interval = int(self.query_one("#interval", Input).value or "0")
            days = int(self.query_one("#days", Input).value or "0")
        except ValueError:
            err.update(t("err_int"))
            return
        if interval < 1:
            err.update(t("err_interval_min"))
            return
        if days < 1:
            err.update(t("err_lookahead_min"))
            return
        lang_value = self.query_one("#language", Select).value
        if lang_value is Select.BLANK:
            lang_value = self.cfg.language
        self.dismiss({
            "interval_minutes": interval,
            "date_range_days": days,
            "sound": self.query_one("#sound", Checkbox).value,
            "desktop": self.query_one("#desktop", Checkbox).value,
            "language": str(lang_value),
        })


class BooksyWatchApp(App):
    CSS = """
    Screen { layout: vertical; }
    #salon { padding: 0 1; color: $accent; }
    #target { height: 7; border: round $primary; padding: 1 2; }
    #history { border: round $secondary; padding: 1 2; }
    """

    # Static EN descriptions: Textual reads BINDINGS at class load time, so any
    # dynamic per-language rebuild can race with the Footer. PL users still get
    # the working keys; only the footer captions stay English.
    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("p", "pause", "Pause/Resume"),
        Binding("r", "reset", "Reset target"),
        Binding("c", "check_now", "Check now"),
        Binding("s", "settings", "Settings"),
    ]

    def __init__(self, cfg: Config) -> None:
        super().__init__()
        self.cfg = cfg
        self.queue: asyncio.Queue[WatchEvent] = asyncio.Queue()
        self.watcher = Watcher(cfg, self.queue)
        self._biz_name = ""
        self._svc_name = ""
        self._staffer_name = ""

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield Static("", id="salon")
        yield TargetPanel(id="target")
        yield History()
        yield Footer()

    async def on_mount(self) -> None:
        try:
            with BooksyClient(country=self.cfg.salon.country) as c:
                biz = c.get_business(self.cfg.salon.business_id)
            self._biz_name = biz.name
            svc = biz.service_by_variant(self.cfg.watch.service_variant_id)
            self._svc_name = svc.name if svc else f"variant {self.cfg.watch.service_variant_id}"
            self._staffer_name = (
                biz.staffer_name(self.cfg.watch.staffer_id)
                if self.cfg.watch.staffer_id is not None
                else t("staffer_any")
            )
        except Exception as e:  # noqa: BLE001
            self._biz_name = f"business {self.cfg.salon.business_id}"
            self._svc_name = f"variant {self.cfg.watch.service_variant_id}"
            self._staffer_name = f"(error: {e})"
        self._render_salon_line()

        history = self.query_one(History)
        if self.watcher.target:
            history.add(WatchEvent(
                ts=datetime.now(),
                kind=EventKind.SAME,
                target=self.watcher.target,
                message=t("ev_resumed", ts=self.watcher.target.strftime("%Y-%m-%d %H:%M")),
            ))

        self.run_worker(self._consume_events(), name="events", exclusive=False)
        self.run_worker(self.watcher.run(), name="watcher", exclusive=False)
        self.set_interval(1.0, self._tick)

    def _render_salon_line(self) -> None:
        self.query_one("#salon", Static).update(
            f"[bold]{self._biz_name}[/bold]\n"
            f"[cyan]{self._svc_name}[/cyan]  ·  {self._staffer_name}  "
            f"·  {t('header_every')} [bold]{self.cfg.watch.interval_minutes}{t('header_min')}[/bold]  "
            f"·  {t('header_scanning')} [bold]{self.cfg.watch.date_range_days}{t('header_days')}[/bold] {t('header_ahead')}"
        )

    def _tick(self) -> None:
        panel = self.query_one(TargetPanel)
        panel.target = self.watcher.target
        panel.next_check = self.watcher.next_check_at
        panel.paused = self.watcher._pause.is_set()  # noqa: SLF001
        panel.refresh()

    async def _consume_events(self) -> None:
        history = self.query_one(History)
        while True:
            ev = await self.queue.get()
            history.add(ev)
            if ev.kind in (EventKind.EARLIER, EventKind.FIRST, EventKind.TAKEN):
                if self.cfg.notify.sound:
                    play_sound()
                if self.cfg.notify.desktop:
                    desktop_notify(f"Booksy · {self._biz_name}", ev.message)

    def action_pause(self) -> None:
        self.watcher.toggle_pause()

    def action_reset(self) -> None:
        self.watcher.reset_target()
        self.query_one(History).add(WatchEvent(
            ts=datetime.now(), kind=EventKind.SAME, target=None,
            message=t("ev_reset"),
        ))

    def action_check_now(self) -> None:
        self.watcher.next_check_at = datetime.now()

    def action_settings(self) -> None:
        self.push_screen(SettingsScreen(self.cfg), self._on_settings_saved)

    def _on_settings_saved(self, result: dict | None) -> None:
        if result is None:
            return
        old_interval = self.cfg.watch.interval_minutes
        self.cfg.watch.interval_minutes = result["interval_minutes"]
        self.cfg.watch.date_range_days = result["date_range_days"]
        self.cfg.notify.sound = result["sound"]
        self.cfg.notify.desktop = result["desktop"]
        self.cfg.language = result["language"]
        # Switch language live — affects all subsequent t() calls. Footer
        # bindings are class-level English and stay that way; everything
        # else (panel, header, new events) is re-rendered in the new lang.
        set_language(self.cfg.language)
        try:
            self.cfg.save()
        except OSError as e:
            self.query_one(History).add(WatchEvent(
                ts=datetime.now(), kind=EventKind.ERROR, target=self.watcher.target,
                message=t("ev_save_failed", e=str(e)),
            ))
            return

        self._render_salon_line()

        new_interval = self.cfg.watch.interval_minutes
        if self.watcher.next_check_at is not None and new_interval < old_interval:
            soonest = datetime.now() + timedelta(minutes=new_interval)
            if soonest < self.watcher.next_check_at:
                self.watcher.next_check_at = soonest

        self.query_one(History).add(WatchEvent(
            ts=datetime.now(), kind=EventKind.SAME, target=self.watcher.target,
            message=t(
                "ev_settings_updated",
                i=new_interval,
                d=self.cfg.watch.date_range_days,
                s=t("on") if self.cfg.notify.sound else t("off"),
                dt=t("on") if self.cfg.notify.desktop else t("off"),
            ),
        ))
