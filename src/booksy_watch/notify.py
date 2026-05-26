"""Sound + macOS desktop notifications."""

from __future__ import annotations

import shlex
import subprocess
from pathlib import Path

SOUND_PATH = Path("/System/Library/Sounds/Glass.aiff")


def play_sound() -> None:
    if not SOUND_PATH.exists():
        return
    subprocess.Popen(
        ["afplay", str(SOUND_PATH)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def desktop_notify(title: str, message: str) -> None:
    # osascript: avoid injecting quotes by using shell-escaped applescript string
    script = (
        f'display notification {shlex.quote(message)} '
        f'with title {shlex.quote(title)} sound name "Glass"'
    )
    subprocess.Popen(
        ["osascript", "-e", script],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
