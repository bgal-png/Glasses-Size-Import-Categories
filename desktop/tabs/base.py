# -*- coding: utf-8 -*-
"""Common contract for every tab.

Tabs are plain QWidgets. The main window owns the toolbar and the right dock;
it asks the current tab for its control panel and hides the dock entirely on
tabs that return None.
"""
from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QWidget


class BaseTab(QWidget):
    TITLE = "Tab"

    status_message = Signal(str)
    busy = Signal(bool)

    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.snapshot = None

    def set_snapshot(self, snapshot) -> None:
        self.snapshot = snapshot
        self.on_snapshot(snapshot)

    def on_snapshot(self, snapshot) -> None:
        """Called whenever a snapshot is loaded or refreshed."""

    def control_panel(self) -> QWidget | None:
        return None

    def has_unsaved_changes(self) -> bool:
        return False
