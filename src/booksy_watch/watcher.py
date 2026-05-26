"""Polling + state machine.

Emits events through an async queue so the TUI can render them live.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from enum import Enum

import httpx

from .booksy import BooksyClient, Slot
from .config import Config, State
from .i18n import t


def _fmt(ts: datetime) -> str:
    return ts.strftime("%Y-%m-%d %H:%M")


class EventKind(str, Enum):
    FIRST = "FIRST"          # initial target seen
    EARLIER = "EARLIER"      # found slot earlier than target
    SAME = "SAME"            # no change
    TAKEN = "TAKEN"          # target disappeared, new target may be later
    NONE = "NONE"            # no slots at all
    ERROR = "ERROR"


@dataclass(slots=True)
class WatchEvent:
    ts: datetime
    kind: EventKind
    target: datetime | None
    prev_target: datetime | None = None
    message: str = ""


class Watcher:
    def __init__(self, cfg: Config, queue: asyncio.Queue[WatchEvent]) -> None:
        self.cfg = cfg
        self.queue = queue
        self.state = State.load()
        self._stop = asyncio.Event()
        self._pause = asyncio.Event()
        self.next_check_at: datetime | None = None

    @property
    def target(self) -> datetime | None:
        if not self.state.target_slot_iso:
            return None
        return datetime.fromisoformat(self.state.target_slot_iso)

    @target.setter
    def target(self, value: datetime | None) -> None:
        self.state.target_slot_iso = value.isoformat() if value else None
        self.state.save()

    def stop(self) -> None:
        self._stop.set()

    def toggle_pause(self) -> bool:
        if self._pause.is_set():
            self._pause.clear()
            return False
        self._pause.set()
        return True

    def reset_target(self) -> None:
        """Forget the current target — next poll starts fresh."""
        self.target = None

    async def run(self) -> None:
        client = BooksyClient(country=self.cfg.salon.country)
        try:
            while not self._stop.is_set():
                if self._pause.is_set():
                    await asyncio.sleep(1)
                    continue
                await self._check_once(client)
                # sleep with interrupt support
                self.next_check_at = datetime.now() + timedelta(
                    minutes=self.cfg.watch.interval_minutes
                )
                while datetime.now() < self.next_check_at:
                    if self._stop.is_set():
                        return
                    if self._pause.is_set():
                        break
                    await asyncio.sleep(1)
        finally:
            client.close()

    async def _check_once(self, client: BooksyClient) -> None:
        start = date.today()
        end = start + timedelta(days=self.cfg.watch.date_range_days)
        try:
            slots = await asyncio.to_thread(
                client.get_time_slots,
                self.cfg.salon.business_id,
                self.cfg.watch.service_variant_id,
                start,
                end,
                self.cfg.watch.staffer_id,
            )
        except (httpx.HTTPError, ValueError) as e:
            self.state.last_error = str(e)
            self.state.save()
            await self.queue.put(
                WatchEvent(ts=datetime.now(), kind=EventKind.ERROR, target=self.target, message=str(e))
            )
            return

        self.state.last_check_iso = datetime.now().isoformat()
        self.state.last_error = None
        self.state.save()

        if not slots:
            await self.queue.put(
                WatchEvent(ts=datetime.now(), kind=EventKind.NONE, target=self.target,
                           message=t("ev_no_slots"))
            )
            return

        earliest = slots[0].when
        prev = self.target

        if prev is None:
            self.target = earliest
            await self.queue.put(
                WatchEvent(ts=datetime.now(), kind=EventKind.FIRST, target=earliest,
                           message=t("ev_watching_from", ts=_fmt(earliest)))
            )
            return

        if earliest < prev:
            self.target = earliest
            await self.queue.put(
                WatchEvent(ts=datetime.now(), kind=EventKind.EARLIER,
                           target=earliest, prev_target=prev,
                           message=t("ev_earlier", new=_fmt(earliest), old=_fmt(prev)))
            )
            return

        # Same or later: check if prev still present.
        prev_still_there = any(s.when == prev for s in slots)
        if not prev_still_there:
            self.target = earliest
            await self.queue.put(
                WatchEvent(ts=datetime.now(), kind=EventKind.TAKEN,
                           target=earliest, prev_target=prev,
                           message=t("ev_taken", old=_fmt(prev), new=_fmt(earliest)))
            )
            return

        await self.queue.put(
            WatchEvent(ts=datetime.now(), kind=EventKind.SAME, target=prev,
                       message=t("ev_unchanged", ts=_fmt(prev)))
        )
