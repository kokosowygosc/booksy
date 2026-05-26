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
from textual.widgets import Button, Checkbox, Footer, Header, Input, Label, Static

from .booksy import BooksyClient
from .config import Config
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
            target_line = "[dim](no slot yet — waiting for first check)[/dim]"
        if self.paused:
            next_line = "[bold yellow]PAUSED[/bold yellow]"
        elif self.next_check:
            remaining = max(0, int((self.next_check - datetime.now()).total_seconds()))
            mm, ss = divmod(remaining, 60)
            next_line = f"next check in [bold]{mm:02d}:{ss:02d}[/bold]"
        else:
            next_line = "starting..."
        return f"\n  TARGET SLOT:  {target_line}\n  {next_line}\n"


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
            t = ev.ts.strftime("%H:%M:%S")
            lines.append(f"[dim]{t}[/dim]  [{style}]{sym} {ev.kind.value:<7}[/{style}]  {ev.message}")
        self.update("\n".join(lines) if lines else "[dim](no events yet)[/dim]")


class SettingsScreen(ModalScreen[dict | None]):
    """In-app settings: tweak polling interval, lookahead, notifications.

    Returns a dict of new values on save, or None on cancel.
    """

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
    ]

    CSS = """
    SettingsScreen {
        align: center middle;
    }
    #settings-dialog {
        width: 60;
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
        width: 28;
        content-align: left middle;
        height: 3;
    }
    #settings-dialog Input {
        width: 1fr;
    }
    #settings-dialog Checkbox {
        width: 1fr;
    }
    #buttons {
        height: 3;
        align: right middle;
    }
    #buttons Button {
        margin-left: 1;
    }
    #error {
        color: $error;
        height: auto;
        margin-bottom: 1;
    }
    """

    def __init__(self, cfg: Config) -> None:
        super().__init__()
        self.cfg = cfg

    def compose(self) -> ComposeResult:
        with Vertical(id="settings-dialog"):
            yield Label("Settings", classes="title")
            yield Static("", id="error")
            with Horizontal(classes="row"):
                yield Label("Polling interval (min)", classes="field")
                yield Input(
                    value=str(self.cfg.watch.interval_minutes),
                    id="interval",
                    type="integer",
                    restrict=r"[0-9]*",
                )
            with Horizontal(classes="row"):
                yield Label("Lookahead window (days)", classes="field")
                yield Input(
                    value=str(self.cfg.watch.date_range_days),
                    id="days",
                    type="integer",
                    restrict=r"[0-9]*",
                )
            with Horizontal(classes="row"):
                yield Label("Sound on alert", classes="field")
                yield Checkbox(value=self.cfg.notify.sound, id="sound")
            with Horizontal(classes="row"):
                yield Label("Desktop notification", classes="field")
                yield Checkbox(value=self.cfg.notify.desktop, id="desktop")
            with Horizontal(id="buttons"):
                yield Button("Cancel", id="cancel", variant="default")
                yield Button("Save", id="save", variant="primary")

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
            err.update("Interval and days must be integers.")
            return
        if interval < 1:
            err.update("Interval must be ≥ 1 minute.")
            return
        if days < 1:
            err.update("Lookahead must be ≥ 1 day.")
            return
        self.dismiss({
            "interval_minutes": interval,
            "date_range_days": days,
            "sound": self.query_one("#sound", Checkbox).value,
            "desktop": self.query_one("#desktop", Checkbox).value,
        })


class BooksyWatchApp(App):
    CSS = """
    Screen { layout: vertical; }
    #salon { padding: 0 1; color: $accent; }
    #target { height: 7; border: round $primary; padding: 1 2; }
    #history { border: round $secondary; padding: 1 2; }
    """

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
        # Fetch business details for header (best-effort).
        try:
            with BooksyClient(country=self.cfg.salon.country) as c:
                biz = c.get_business(self.cfg.salon.business_id)
            self._biz_name = biz.name
            svc = biz.service_by_variant(self.cfg.watch.service_variant_id)
            self._svc_name = svc.name if svc else f"variant {self.cfg.watch.service_variant_id}"
            self._staffer_name = biz.staffer_name(self.cfg.watch.staffer_id)
        except Exception as e:  # noqa: BLE001
            self._biz_name = f"business {self.cfg.salon.business_id}"
            self._svc_name = f"variant {self.cfg.watch.service_variant_id}"
            self._staffer_name = f"(failed to load: {e})"
        self._render_salon_line()

        history = self.query_one(History)
        if self.watcher.target:
            history.add(WatchEvent(
                ts=datetime.now(),
                kind=EventKind.SAME,
                target=self.watcher.target,
                message=f"resumed with target {self.watcher.target:%Y-%m-%d %H:%M}",
            ))

        # Background tasks
        self.run_worker(self._consume_events(), name="events", exclusive=False)
        self.run_worker(self.watcher.run(), name="watcher", exclusive=False)
        self.set_interval(1.0, self._tick)

    def _render_salon_line(self) -> None:
        self.query_one("#salon", Static).update(
            f"[bold]{self._biz_name}[/bold]\n"
            f"[cyan]{self._svc_name}[/cyan]  ·  {self._staffer_name}  "
            f"·  every [bold]{self.cfg.watch.interval_minutes}min[/bold]  "
            f"·  scanning [bold]{self.cfg.watch.date_range_days}d[/bold] ahead"
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
        history = self.query_one(History)
        history.add(WatchEvent(
            ts=datetime.now(), kind=EventKind.SAME, target=None,
            message="target reset by user — next check sets new target",
        ))

    def action_check_now(self) -> None:
        # Force loop to exit its sleep immediately.
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
        try:
            self.cfg.save()
        except OSError as e:
            self.query_one(History).add(WatchEvent(
                ts=datetime.now(), kind=EventKind.ERROR, target=self.watcher.target,
                message=f"failed to save config: {e}",
            ))
            return

        self._render_salon_line()

        # If new interval is shorter than remaining wait, pull next check sooner.
        new_interval = self.cfg.watch.interval_minutes
        if self.watcher.next_check_at is not None and new_interval < old_interval:
            soonest = datetime.now() + timedelta(minutes=new_interval)
            if soonest < self.watcher.next_check_at:
                self.watcher.next_check_at = soonest

        self.query_one(History).add(WatchEvent(
            ts=datetime.now(), kind=EventKind.SAME, target=self.watcher.target,
            message=(
                f"settings updated: interval={new_interval}min, "
                f"lookahead={self.cfg.watch.date_range_days}d, "
                f"sound={'on' if self.cfg.notify.sound else 'off'}, "
                f"desktop={'on' if self.cfg.notify.desktop else 'off'}"
            ),
        ))
