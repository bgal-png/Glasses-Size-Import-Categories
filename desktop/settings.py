# -*- coding: utf-8 -*-
"""Persisted user settings (QSettings → Windows registry, per user).

Credentials policy: no token is ever baked into a build. `update_token` is a
fine-grained PAT with read access to this private repo's Releases, pasted by
the user in ⚙️ Settings; without it the update check simply reports that it is
not configured.
"""
from __future__ import annotations

from PySide6.QtCore import QSettings

from version import APP_NAME, ORG_NAME


class Settings:
    def __init__(self) -> None:
        self._s = QSettings(ORG_NAME, APP_NAME)

    @property
    def dark_mode(self) -> bool:
        return str(self._s.value("dark_mode", "false")).lower() in ("1", "true", "yes")

    @dark_mode.setter
    def dark_mode(self, value: bool) -> None:
        self._s.setValue("dark_mode", bool(value))

    @property
    def update_token(self) -> str:
        return str(self._s.value("update_token", "")).strip()

    @update_token.setter
    def update_token(self, value: str) -> None:
        self._s.setValue("update_token", (value or "").strip())

    @property
    def last_refresh_report(self) -> str:
        """JSON of the last refresh report, shown on the Data tab."""
        return str(self._s.value("last_refresh_report", "")).strip()

    @last_refresh_report.setter
    def last_refresh_report(self, value: str) -> None:
        self._s.setValue("last_refresh_report", value or "")

    def last_dir(self, key: str) -> str:
        return str(self._s.value(f"last_dir/{key}", "")).strip()

    def set_last_dir(self, key: str, path: str) -> None:
        self._s.setValue(f"last_dir/{key}", path or "")
