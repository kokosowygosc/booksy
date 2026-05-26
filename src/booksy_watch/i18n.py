"""Tiny i18n. Two locales: en, pl. Lookup with t('key', **fmt)."""

from __future__ import annotations

LANGUAGES = ("en", "pl")
LANGUAGE_LABELS = {"en": "English", "pl": "Polski"}

_STRINGS: dict[str, dict[str, str]] = {
    "en": {
        # wizard
        "wiz_title": "booksy-watch setup",
        "wiz_lang": "Language",
        "wiz_url": "Salon URL from booksy.com",
        "wiz_url_bad": "{err} — expected e.g. https://booksy.com/pl-pl/21431_...",
        "wiz_business_ok": "business_id={bid}, country={country}",
        "wiz_loaded": "{name}  ({n} services)",
        "wiz_services_title": "Services at {name}",
        "wiz_pick_service": "Pick service #",
        "wiz_interval": "Polling interval (minutes)",
        "wiz_days": "How many days ahead to scan",
        "wiz_sound": "Sound on alert?",
        "wiz_desktop": "macOS notification on alert?",
        "wiz_saved": "Saved config",
        # service table columns
        "col_num": "#",
        "col_service": "Service",
        "col_staffer": "Staffer",
        "col_price": "Price",
        "col_duration": "Dur",
        "staffer_any": "any staffer",
        # bindings (Footer)
        "bind_quit": "Quit",
        "bind_pause": "Pause/Resume",
        "bind_reset": "Reset target",
        "bind_check": "Check now",
        "bind_settings": "Settings",
        # target panel
        "panel_target": "TARGET SLOT",
        "panel_no_slot": "(no slot yet — waiting for first check)",
        "panel_paused": "PAUSED",
        "panel_next_in": "next check in",
        "panel_starting": "starting...",
        # salon header
        "header_every": "every",
        "header_scanning": "scanning",
        "header_ahead": "ahead",
        "header_min": "min",
        "header_days": "d",
        # settings modal
        "settings_title": "Settings",
        "settings_interval": "Polling interval (min)",
        "settings_lookahead": "Lookahead window (days)",
        "settings_sound": "Sound on alert",
        "settings_desktop": "Desktop notification",
        "settings_language": "Language",
        "btn_cancel": "Cancel",
        "btn_save": "Save",
        "err_int": "Interval and days must be integers.",
        "err_interval_min": "Interval must be at least 1 minute.",
        "err_lookahead_min": "Lookahead must be at least 1 day.",
        # event messages
        "ev_watching_from": "watching from {ts}",
        "ev_earlier": "earlier slot: {new} (was {old})",
        "ev_taken": "target {old} taken — new earliest: {new}",
        "ev_unchanged": "unchanged: {ts}",
        "ev_no_slots": "no available slots in window",
        "ev_resumed": "resumed with target {ts}",
        "ev_reset": "target reset by user — next check sets new target",
        "ev_settings_updated": (
            "settings updated: interval={i}min, lookahead={d}d, "
            "sound={s}, desktop={dt}"
        ),
        "ev_save_failed": "failed to save config: {e}",
        # toggles
        "on": "on",
        "off": "off",
    },
    "pl": {
        # wizard
        "wiz_title": "konfiguracja booksy-watch",
        "wiz_lang": "Język",
        "wiz_url": "URL salonu z booksy.com",
        "wiz_url_bad": "{err} — np. https://booksy.com/pl-pl/21431_...",
        "wiz_business_ok": "business_id={bid}, kraj={country}",
        "wiz_loaded": "{name}  ({n} serwisów)",
        "wiz_services_title": "Serwisy w {name}",
        "wiz_pick_service": "Wybierz serwis #",
        "wiz_interval": "Interwał sprawdzania (minuty)",
        "wiz_days": "Na ile dni do przodu skanować",
        "wiz_sound": "Dźwięk przy alercie?",
        "wiz_desktop": "Powiadomienie macOS przy alercie?",
        "wiz_saved": "Zapisano konfigurację",
        # service table columns
        "col_num": "#",
        "col_service": "Serwis",
        "col_staffer": "Pracownik",
        "col_price": "Cena",
        "col_duration": "Czas",
        "staffer_any": "dowolny pracownik",
        # bindings (Footer)
        "bind_quit": "Wyjdź",
        "bind_pause": "Pauza/Wznów",
        "bind_reset": "Reset celu",
        "bind_check": "Sprawdź teraz",
        "bind_settings": "Ustawienia",
        # target panel
        "panel_target": "DOCELOWY TERMIN",
        "panel_no_slot": "(brak terminu — czekam na pierwsze sprawdzenie)",
        "panel_paused": "PAUZA",
        "panel_next_in": "następne sprawdzenie za",
        "panel_starting": "uruchamiam...",
        # salon header
        "header_every": "co",
        "header_scanning": "skanuję",
        "header_ahead": "do przodu",
        "header_min": "min",
        "header_days": "d",
        # settings modal
        "settings_title": "Ustawienia",
        "settings_interval": "Interwał sprawdzania (min)",
        "settings_lookahead": "Okno wyszukiwania (dni)",
        "settings_sound": "Dźwięk przy alercie",
        "settings_desktop": "Powiadomienie systemowe",
        "settings_language": "Język",
        "btn_cancel": "Anuluj",
        "btn_save": "Zapisz",
        "err_int": "Interwał i dni muszą być liczbami całkowitymi.",
        "err_interval_min": "Interwał musi być co najmniej 1 minuta.",
        "err_lookahead_min": "Okno musi być co najmniej 1 dzień.",
        # event messages
        "ev_watching_from": "obserwuję od {ts}",
        "ev_earlier": "szybszy termin: {new} (był {old})",
        "ev_taken": "termin {old} zajęty — nowy najwcześniejszy: {new}",
        "ev_unchanged": "bez zmian: {ts}",
        "ev_no_slots": "brak dostępnych terminów w oknie",
        "ev_resumed": "wznowiono z celem {ts}",
        "ev_reset": "cel zresetowany — następne sprawdzenie ustawi nowy",
        "ev_settings_updated": (
            "ustawienia zaktualizowane: interwał={i}min, okno={d}d, "
            "dźwięk={s}, powiadomienia={dt}"
        ),
        "ev_save_failed": "nie udało się zapisać konfiguracji: {e}",
        # toggles
        "on": "wł.",
        "off": "wył.",
    },
}

_lang: str = "en"


def set_language(code: str) -> None:
    global _lang
    _lang = code if code in _STRINGS else "en"


def get_language() -> str:
    return _lang


def t(key: str, /, **fmt: object) -> str:
    table = _STRINGS.get(_lang, _STRINGS["en"])
    text = table.get(key) or _STRINGS["en"].get(key) or key
    return text.format(**fmt) if fmt else text
