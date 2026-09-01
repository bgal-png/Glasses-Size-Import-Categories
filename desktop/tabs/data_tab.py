# -*- coding: utf-8 -*-
"""Data — which snapshot is loaded, how old it is, and what the last refresh
dropped. Empty or surprising results must explain themselves, so the six junk
category rows stay visible rather than being summarised away.
"""
from __future__ import annotations

import json

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QPlainTextEdit, QVBoxLayout

import theme
from tabs.base import BaseTab


class DataTab(BaseTab):
    TITLE = "🗄 Data"

    def __init__(self, settings, parent=None):
        super().__init__(settings, parent)
        layout = QVBoxLayout(self)

        self.status = QLabel("No snapshot loaded.")
        self.status.setStyleSheet(theme.status_style("loading"))
        self.status.setTextInteractionFlags(Qt.TextSelectableByMouse)
        layout.addWidget(self.status)

        self.details = QLabel("")
        self.details.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.details.setWordWrap(True)
        layout.addWidget(self.details)

        layout.addWidget(QLabel("Last refresh report"))
        self.report = QPlainTextEdit()
        self.report.setReadOnly(True)
        layout.addWidget(self.report, 1)

        self._render_report()

    def on_snapshot(self, snapshot) -> None:
        if snapshot is None:
            self.status.setText("No snapshot loaded.")
            self.status.setStyleSheet(theme.status_style("error"))
            return
        if snapshot.source == "mixed":
            def _label(part_source):
                return "refreshed locally" if part_source == "local" else "bundled with the app"

            origin = (
                f"catalogue {_label(snapshot.catalogue_source)}, "
                f"categories {_label(snapshot.categories_source)}"
            )
        else:
            origin = "refreshed locally" if snapshot.source == "local" else "bundled with the app"
        self.status.setText(
            f"Snapshot ready — {origin}, {len(snapshot.catalogue):,} products, "
            f"{sum(len(v) for v in snapshot.lookup.values())} categories"
        )
        self.status.setStyleSheet(theme.status_style("ready"))
        self.details.setText(
            f"Catalogue: {snapshot.catalogue_path}\n"
            f"Categories: {snapshot.categories_path}\n"
            f"Updated: {snapshot.updated_at:%Y-%m-%d %H:%M}"
        )
        self._render_report()

    def show_report(self, report: dict) -> None:
        self.settings.last_refresh_report = json.dumps(report, default=str)
        self._render_report()

    def _render_report(self) -> None:
        raw = self.settings.last_refresh_report
        if not raw:
            self.report.setPlainText(
                "No refresh run on this machine yet — the bundled snapshot is in use.\n"
                "Use 🔁 Refresh from Excel after re-exporting Main catalogue.xlsx."
            )
            return
        try:
            report = json.loads(raw)
        except ValueError:
            self.report.setPlainText(raw)
            return

        lines = []
        catalogue = report.get("catalogue")
        if catalogue:
            lines.append(f"catalogue: {catalogue['products']} products")
            lines.append(f"catalogue: {catalogue['skipped']} rows skipped (no name or no globalId)")
        categories = report.get("categories")
        if categories:
            lines.append(f"categories: {categories['rows']} rows read")
            lines.append(
                f"categories: {categories['collapsed']} duplicates collapsed (lowest ID kept)"
            )
            lines.append(f"categories: {len(categories['dropped'])} rows dropped:")
            for row in categories["dropped"]:
                lines.append(f"  - id={row[0]} name={row[1]!r} value={row[2]!r}")
            lines.append(f"categories: {categories['kept']} usable categories")
        self.report.setPlainText("\n".join(lines) or "Nothing recorded.")
