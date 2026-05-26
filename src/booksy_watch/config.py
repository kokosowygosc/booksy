"""Config + state persistence at ~/.config/booksy-watch/."""

from __future__ import annotations

import json
import os
import tomllib
from dataclasses import asdict, dataclass, field
from pathlib import Path

import tomli_w


def config_dir() -> Path:
    base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    p = base / "booksy-watch"
    p.mkdir(parents=True, exist_ok=True)
    return p


def config_path() -> Path:
    return config_dir() / "config.toml"


def state_path() -> Path:
    return config_dir() / "state.json"


@dataclass(slots=True)
class SalonConfig:
    url: str
    business_id: int
    country: str = "pl"


@dataclass(slots=True)
class WatchConfig:
    service_variant_id: int
    staffer_id: int | None = None
    interval_minutes: int = 10
    date_range_days: int = 90


@dataclass(slots=True)
class NotifyConfig:
    sound: bool = True
    desktop: bool = True


@dataclass(slots=True)
class Config:
    salon: SalonConfig
    watch: WatchConfig
    notify: NotifyConfig = field(default_factory=NotifyConfig)
    language: str = "en"  # "en" | "pl"

    def save(self) -> None:
        with config_path().open("wb") as f:
            tomli_w.dump(
                {
                    "salon": asdict(self.salon),
                    "watch": {k: v for k, v in asdict(self.watch).items() if v is not None},
                    "notify": asdict(self.notify),
                    "ui": {"language": self.language},
                },
                f,
            )

    @staticmethod
    def load() -> "Config | None":
        p = config_path()
        if not p.exists():
            return None
        with p.open("rb") as f:
            data = tomllib.load(f)
        return Config(
            salon=SalonConfig(**data["salon"]),
            watch=WatchConfig(**data["watch"]),
            notify=NotifyConfig(**data.get("notify", {})),
            language=data.get("ui", {}).get("language", "en"),
        )


@dataclass(slots=True)
class State:
    """Persisted watcher state."""

    target_slot_iso: str | None = None  # earliest known slot as ISO datetime
    last_check_iso: str | None = None
    last_error: str | None = None

    def save(self) -> None:
        with state_path().open("w") as f:
            json.dump(asdict(self), f, indent=2)

    @staticmethod
    def load() -> "State":
        p = state_path()
        if not p.exists():
            return State()
        with p.open() as f:
            return State(**json.load(f))
